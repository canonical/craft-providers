#
# Copyright 2021-2023 Canonical Ltd.
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
from unittest import mock

import pytest
import yaml
from craft_providers import Executor
from craft_providers.errors import BaseConfigurationError, ProviderError
from craft_providers.instance_config import InstanceConfiguration
from pydantic import ValidationError


@pytest.fixture
def default_config_data():
    return {
        "compatibility_tag": "tag-foo-v2",
        "setup": True,
        "snaps": {
            "charmcraft": {"revision": 834},
            "core22": {"revision": 147},
        },
    }


@pytest.fixture
def mock_executor():
    executor_mock = mock.Mock(spec=Executor)
    return executor_mock


@pytest.fixture
def config_fixture(fake_home_temporary_file):
    """Creates an instance config file containing data passed to the fixture."""

    def _config_fixture(**kwargs):
        fake_home_temporary_file.write_text(**kwargs)

        return fake_home_temporary_file

    return _config_fixture


def test_instance_config_defaults():
    """Verify default values for instance configuration objects."""
    config = InstanceConfiguration()

    assert config.setup is None
    assert config.compatibility_tag is None
    assert config.snaps is None


def test_save(mock_executor):
    config = InstanceConfiguration(compatibility_tag="tag-foo-v2")
    config_path = pathlib.PurePosixPath("/etc/crafty-crafty.conf")

    config.save(executor=mock_executor, config_path=config_path)

    assert mock_executor.mock_calls == [
        mock.call.push_file_io(
            destination=config_path, content=mock.ANY, file_mode="0644"
        )
    ]

    assert (
        mock_executor.mock_calls[0].kwargs["content"].read()
        == b"compatibility_tag: tag-foo-v2\n"
    )


def test_load_missing_config_returns_none(mock_executor):
    mock_executor.pull_file.side_effect = [FileNotFoundError]
    config_path = pathlib.PurePosixPath("/test/foo")
    config_instance = InstanceConfiguration.load(
        executor=mock_executor, config_path=config_path
    )

    assert config_instance is None


def test_load_empty_config_returns_none(mock_executor, config_fixture):
    config_fixture(data="")
    config_path = pathlib.PurePosixPath("/etc/crafty-crafty.conf")
    config_instance = InstanceConfiguration.load(
        executor=mock_executor, config_path=config_path
    )

    assert config_instance is None


def test_load_with_valid_config(mock_executor, config_fixture, default_config_data):
    config_file = config_fixture(data=yaml.dump(default_config_data))
    config_path = pathlib.PurePosixPath("/etc/crafty-crafty.conf")
    config_instance = InstanceConfiguration.load(
        executor=mock_executor, config_path=config_path
    )

    assert mock_executor.mock_calls == [
        mock.call.pull_file(
            source=config_path,
            destination=config_file,
        ),
    ]

    assert config_instance is not None
    assert dict(config_instance) == {
        "compatibility_tag": "tag-foo-v2",
        "setup": True,
        "snaps": {"charmcraft": {"revision": 834}, "core22": {"revision": 147}},
    }


def test_load_with_invalid_config_raises_error(mock_executor, config_fixture):
    config_fixture(data="invalid: data")

    config_path = pathlib.PurePosixPath("/etc/crafty-crafty.conf")

    with pytest.raises(ValidationError) as exc_info:
        InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    error = exc_info.value.errors()
    assert len(error) == 1
    assert error[0]["loc"] == ("invalid",)
    assert error[0]["type"] in ("value_error.extra", "extra_forbidden")


def test_load_failure_to_pull_file_raises_error(mock_executor):
    mock_executor.pull_file.side_effect = [ProviderError(brief="foo")]

    config_path = pathlib.PurePosixPath("/test/foo")

    with pytest.raises(BaseConfigurationError) as exc_info:
        InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    assert exc_info.value == BaseConfigurationError(
        brief=f"Failed to read instance config in environment at {config_path}",
    )


def test_update_single_value(default_config_data, mock_executor, mocker, tmpdir):
    """Test that a single value in a config is properly updated."""
    mocker.patch(
        "craft_providers.instance_config.InstanceConfiguration.load",
        return_value=InstanceConfiguration(**default_config_data),
    )

    updated_config = InstanceConfiguration.update(
        executor=mock_executor,
        data={"compatibility_tag": "updated-tag-value"},
        config_path=pathlib.Path(tmpdir / "crafty-crafty.conf"),
    )

    assert updated_config.compatibility_tag == "updated-tag-value"


def test_update_update_nested_values(
    default_config_data, mock_executor, mocker, tmpdir
):
    """Test updating a config by updating an existing nested value."""
    mocker.patch(
        "craft_providers.instance_config.InstanceConfiguration.load",
        return_value=InstanceConfiguration(**default_config_data),
    )

    updated_config = InstanceConfiguration.update(
        executor=mock_executor,
        data={
            "snaps": {
                "charmcraft": {"revision": 835},
            }
        },
        config_path=pathlib.Path(tmpdir / "crafty-crafty.conf"),
    )

    assert updated_config.snaps == {
        "charmcraft": {"revision": 835},
        "core22": {"revision": 147},
    }


def test_update_add_nested_values(default_config_data, mock_executor, mocker, tmpdir):
    """Test updating a config by adding a new nested value."""
    mocker.patch(
        "craft_providers.instance_config.InstanceConfiguration.load",
        return_value=InstanceConfiguration(**default_config_data),
    )

    updated_config = InstanceConfiguration.update(
        executor=mock_executor,
        data={
            "snaps": {
                "new-test-snap": {"revision": 1},
            }
        },
        config_path=pathlib.Path(tmpdir / "crafty-crafty.conf"),
    )

    assert updated_config.snaps == {
        "charmcraft": {"revision": 834},
        "core22": {"revision": 147},
        "new-test-snap": {"revision": 1},
    }
