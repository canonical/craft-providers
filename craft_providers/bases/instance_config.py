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

"""Persistent instance config / datastore resident in provided environment."""

import io
import logging
import pathlib
import subprocess
from typing import Dict, Optional

import pydantic
import yaml

from craft_providers import Executor, errors

from .errors import BaseConfigurationError

logger = logging.getLogger(__name__)


class InstanceConfiguration(pydantic.BaseModel):
    """Instance configuration datastore.

    :param compatibility_tag: Compatibility tag for instance.
    """

    compatibility_tag: str

    @classmethod
    def unmarshal(cls, data: Dict[str, str]) -> "InstanceConfiguration":
        """Unmarshal data dictionary.

        :param data: Dictionary to unmarshal.

        :returns: InstanceConfiguration.
        """
        return cls(compatibility_tag=data["compatibility_tag"])  # type: ignore

    @classmethod
    def load(
        cls, *, executor: Executor, config_path: pathlib.Path
    ) -> Optional["InstanceConfiguration"]:
        """Load instance configuration from executed environment.

        :param executor: Executor for instance.
        :param config_path: Path to configuration file.

        :returns: InstanceConfiguration object.
        """
        # TODO: Replace test / cat usage with an improved
        # Executor.pull_file_io() once available.
        try:
            proc = executor.execute_run(
                command=["test", "-f", config_path.as_posix()],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return None

        try:
            proc = executor.execute_run(
                command=["cat", config_path.as_posix()],
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief=f"Failed to read instance config in environment at {config_path.as_posix()}",
                details=errors.details_from_called_process_error(error),
            ) from error

        data = yaml.safe_load(proc.stdout)

        try:
            return cls.unmarshal(data)
        except (pydantic.ValidationError, KeyError) as error:
            raise BaseConfigurationError(
                brief="Invalid instance config data.",
                details=f"Instance configuration data: {data!r}",
            ) from error

    def save(self, *, executor: Executor, config_path: pathlib.Path) -> None:
        """Save instance configuration in executed environment.

        :param executor: Executor for instance.
        :param config_path: Path to configuration file.
        """
        data = self.dict()

        executor.push_file_io(
            destination=config_path,
            content=io.BytesIO(yaml.dump(data).encode()),
            file_mode="0644",
        )
