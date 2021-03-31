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

"""Persistent craft config / datastore."""

import io
import logging
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Optional

import yaml
from dataclasses_json import dataclass_json

from craft_providers import Executor, errors

from .errors import BaseConfigurationError

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class CraftBaseConfig:
    """Craft configuration properties."""

    compatibility_tag: str


def load(
    *, executor: Executor, config_path: pathlib.Path, **kwargs
) -> Optional[CraftBaseConfig]:
    """Load craft configuration.

    :param executor: Executor for instance.
    :param config_path: Path to configuration file.
    :param kwargs: Extra kwargs for execute_run().

    :returns: CraftBaseConfig object.
    """
    try:
        proc = executor.execute_run(
            command=["test", "-f", config_path.as_posix()],
            capture_output=True,
            check=True,
            **kwargs,
        )
    except subprocess.CalledProcessError:
        return None

    try:
        proc = executor.execute_run(
            command=["cat", config_path.as_posix()],
            capture_output=True,
            check=True,
            text=True,
            **kwargs,
        )
    except subprocess.CalledProcessError as error:
        raise BaseConfigurationError(
            brief=f"Failed to read craft config in environment at {config_path.as_posix()}",
            details=errors.details_from_called_process_error(error),
        ) from error

    data = yaml.safe_load(proc.stdout)

    try:
        return CraftBaseConfig.from_dict(data)  # type: ignore # pylint:disable=no-member
    except KeyError as error:
        raise BaseConfigurationError(
            brief="Invalid craft config data.",
            details=f"Craft configuration data: {data!r}",
        ) from error


def save(
    *, executor: Executor, config: CraftBaseConfig, config_path: pathlib.Path
) -> None:
    """Save craft image config.

    :param executor: Executor for instance.
    :param config: Configuration object to write.
    :param config_path: Path to configuration file.
    """
    data = config.to_dict()  # type: ignore
    executor.create_file(
        destination=config_path,
        content=io.BytesIO(yaml.dump(data).encode()),
        file_mode="0644",
    )
