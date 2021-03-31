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
from craft_providers.bases import craft_config
from craft_providers.bases.errors import BaseConfigurationError


@pytest.fixture
def mock_executor():
    executor_mock = mock.Mock(spec=Executor)
    yield executor_mock


def test_save(mock_executor):
    config = craft_config.CraftBaseConfig(compatibility_tag="tag-foo-v1")
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    craft_config.save(executor=mock_executor, config=config, config_path=config_path)

    assert mock_executor.mock_calls == [
        mock.call.create_file(
            destination=config_path, content=mock.ANY, file_mode="0644"
        )
    ]

    assert (
        mock_executor.mock_calls[0].kwargs["content"].read()
        == b"compatibility_tag: tag-foo-v1\n"
    )


def test_load(mock_executor):
    mock_executor.execute_run.side_effect = [
        None,
        mock.Mock(stdout=b"compatibility_tag: tag-foo-v1\n"),
    ]
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    config = craft_config.load(executor=mock_executor, config_path=config_path)

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

    assert config == craft_config.CraftBaseConfig(compatibility_tag="tag-foo-v1")


def test_load_no_file(mock_executor):
    error = subprocess.CalledProcessError(
        -1, ["test", "-f", "/etc/craft-crafty.conf"], "", ""
    )
    mock_executor.execute_run.side_effect = [error]

    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    config = craft_config.load(executor=mock_executor, config_path=config_path)

    assert config is None


def test_load_invalid_data(mock_executor):
    mock_executor.execute_run.side_effect = [
        None,
        mock.Mock(stdout=b"invalid: data"),
    ]
    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    with pytest.raises(BaseConfigurationError) as exc_info:
        craft_config.load(executor=mock_executor, config_path=config_path)

    assert exc_info.value == BaseConfigurationError(
        brief="Invalid craft config data.",
        details="Craft configuration data: {'invalid': 'data'}",
    )


def test_load_error(mock_executor):
    error = subprocess.CalledProcessError(-1, ["cat", "/etc/craft-crafty.conf"], "", "")
    mock_executor.execute_run.side_effect = [None, error]

    config_path = pathlib.Path("/etc/crafty-crafty.conf")

    with pytest.raises(BaseConfigurationError) as exc_info:
        craft_config.load(executor=mock_executor, config_path=config_path)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to read craft config in environment at /etc/crafty-crafty.conf",
        details=errors.details_from_called_process_error(error),
    )
