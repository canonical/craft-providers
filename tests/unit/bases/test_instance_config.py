# Copyright 2021 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import pathlib
import subprocess
from unittest import mock

import pytest

from craft_providers import Executor, errors
from craft_providers.bases.errors import BaseConfigurationError
from craft_providers.bases.instance_config import InstanceConfiguration


@pytest.fixture
def mock_executor():
    executor_mock = mock.Mock(spec=Executor)
    yield executor_mock


def test_save(mock_executor):
    config = InstanceConfiguration(compatibility_tag="tag-foo-v1")
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    config.save(executor=mock_executor, config_path=config_path)

    assert mock_executor.mock_calls == [
        mock.call.create_file(
            destination=config_path, content=mock.ANY, file_mode="0644"
        )
    ]

    assert (
        mock_executor.mock_calls[0].kwargs["content"].read()
        == b"compatibility_tag: tag-foo-v1\n"
    )


def test_load_no_config_returns_none(mock_executor):
    error = subprocess.CalledProcessError(
        -1, ["test", "-f", "/etc/craft-crafty.conf"], "", ""
    )
    mock_executor.execute_run.side_effect = [error]

    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    config = InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    assert config is None


def test_load_with_valid_config(mock_executor):
    mock_executor.execute_run.side_effect = [
        None,
        mock.Mock(stdout=b"compatibility_tag: foo\n"),
    ]
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    config = InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    assert mock_executor.mock_calls == [
        mock.call.execute_run(
            command=["test", "-f", "/etc/crafty-crafty.conf"],
            capture_output=True,
            check=True,
        ),
        mock.call.execute_run(
            command=["cat", "/etc/crafty-crafty.conf"],
            capture_output=True,
            check=True,
            text=True,
        ),
    ]

    assert config == InstanceConfiguration(compatibility_tag="foo")


def test_load_with_invalid_config_raises_error(mock_executor):
    mock_executor.execute_run.side_effect = [
        None,
        mock.Mock(stdout=b"invalid: data"),
    ]
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    with pytest.raises(BaseConfigurationError) as exc_info:
        InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    assert exc_info.value == BaseConfigurationError(
        brief="Invalid instance config data.",
        details="Instance configuration data: {'invalid': 'data'}",
    )


def test_load_failure_to_pull_file_raises_error(mock_executor):
    error = subprocess.CalledProcessError(-1, ["cat", "/etc/craft-crafty.conf"], "", "")
    mock_executor.execute_run.side_effect = [None, error]

    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    with pytest.raises(BaseConfigurationError) as exc_info:
        InstanceConfiguration.load(executor=mock_executor, config_path=config_path)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to read instance config in environment at /etc/crafty-crafty.conf",
        details=errors.details_from_called_process_error(error),
    )
