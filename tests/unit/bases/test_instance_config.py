#
# Copyright 2021 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import pathlib
import textwrap
from unittest import mock

import pytest
from pydantic import ValidationError

from craft_providers import Executor
from craft_providers.bases.errors import BaseConfigurationError, ProviderError
from craft_providers.bases.instance_config import InstanceConfiguration


@pytest.fixture
def mock_executor():
    executor_mock = mock.Mock(spec=Executor)
    yield executor_mock


@pytest.fixture()
def config_fixture(mocker, tmpdir):
    """Creates an instance config file containing data passed to the fixture."""

    def _config_fixture(**kwargs):
        temp_path = pathlib.Path(tmpdir)

        config_file = temp_path / "craft-instance.conf"
        config_file.write_text(**kwargs)

        mocker.patch(
            "craft_providers.bases.instance_config.temp_paths.home_temporary_file",
            return_value=config_file,
        )

        return config_file

    yield _config_fixture


@pytest.fixture()
def config_fixture_default(config_fixture):
    """Creates an instance config file containing default data."""

    def _config_fixture_default():
        data = textwrap.dedent(
            """\
            compatibility_tag: tag-foo-v1
            snaps:
              charmcraft:
                revision: 834
            """
        )
        my_config_fixture = config_fixture(data=data)
        return my_config_fixture

    yield _config_fixture_default()


def test_save(mock_executor):
    config = InstanceConfiguration(compatibility_tag="tag-foo-v1")
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    config.save(executor=mock_executor, config_path=config_path)

    assert mock_executor.mock_calls == [
        mock.call.push_file_io(
            destination=config_path, content=mock.ANY, file_mode="0644"
        )
    ]

    assert (
        mock_executor.mock_calls[0].kwargs["content"].read()
        == b"compatibility_tag: tag-foo-v1\n"
    )


def test_load_missing_config_returns_none(mock_executor):
    mock_executor.pull_file.side_effect = [FileNotFoundError]
    config_path = pathlib.Path("/test/foo")
    config_instance = InstanceConfiguration.load(
        executor=mock_executor, config_path=config_path
    )

    assert config_instance is None


def test_load_empty_config_returns_none(mock_executor, config_fixture):
    config_fixture(data="")
    config_path = pathlib.Path("/etc/crafty-crafty.conf")
    config_instance = InstanceConfiguration.load(
        executor=mock_executor, config_path=config_path
    )

    assert config_instance is None


def test_load_with_valid_config(mock_executor, config_fixture_default):
    config_file = config_fixture_default
    config_path = pathlib.Path("/etc/crafty-crafty.conf")
    config_instance = InstanceConfiguration.load(
        executor=mock_executor, config_path=config_path
    )

    assert mock_executor.mock_calls == [
        mock.call.pull_file(
            source=config_path,
            destination=config_file,
        ),
    ]

    assert config_instance == {
        "compatibility_tag": "tag-foo-v1",
        "snaps": {"charmcraft": {"revision": 834}},
    }


def test_load_with_invalid_config_raises_error(mock_executor, config_fixture):
    config_fixture(data="invalid: data")

    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    with pytest.raises(ValidationError) as exc_info:
        InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    error = exc_info.value.errors()
    assert len(error) == 1
    assert error[0]["loc"] == ("invalid",)
    assert error[0]["type"] == "value_error.extra"


def test_load_failure_to_pull_file_raises_error(mock_executor):
    mock_executor.pull_file.side_effect = [ProviderError(brief="foo")]

    config_path = pathlib.Path("/test/foo")

    with pytest.raises(BaseConfigurationError) as exc_info:
        InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    assert exc_info.value == BaseConfigurationError(
        brief=f"Failed to read instance config in environment at {config_path}",
    )
