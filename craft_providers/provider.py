# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022-2023 Canonical Ltd.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Abstract base class for Providers.

The Provider, LXDProvider, and MultipassProvider classes are not stable and are
likely to change. These classes will be stable and recommended for use in the release
of craft-providers 2.0.
"""

import contextlib
import logging
import pathlib
from abc import ABC, abstractmethod
from typing import Generator

from .base import Base
from .executor import Executor

logger = logging.getLogger(__name__)


class Provider(ABC):
    """Build environment provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""

    @property
    @abstractmethod
    def install_recommendation(self) -> str:
        """Recommended way to install the provider."""

    def clean_project_environments(self, *, instance_name: str) -> None:
        """Clean the provider environment.

        :param instance_name: name of the instance to clean
        """
        # Nothing to do if provider is not installed.
        if not self.is_provider_installed():
            logger.debug(
                "Not cleaning environment because the provider is not installed."
            )
            return

        environment = self.create_environment(instance_name=instance_name)
        if environment.exists():
            environment.delete()

    @classmethod
    @abstractmethod
    def ensure_provider_is_available(cls) -> None:
        """Ensure provider is available, prompting the user to install it if required.

        :raises ProviderError: if provider is not available.
        """

    @classmethod
    @abstractmethod
    def is_provider_installed(cls) -> bool:
        """Check if provider is installed.

        :returns: True if installed.
        """

    @abstractmethod
    def create_environment(self, *, instance_name: str) -> Executor:
        """Create a bare environment for specified base.

        No initializing, launching, or cleaning up of the environment occurs.

        :param instance_name: name of the instance to create
        """

    @abstractmethod
    @contextlib.contextmanager
    def launched_environment(
        self,
        *,
        project_name: str,
        project_path: pathlib.Path,
        base_configuration: Base,
        instance_name: str,
        allow_unstable: bool = False,
    ) -> Generator[Executor, None, None]:
        """Configure and launch environment for specified base.

        When this method loses context, all directories are unmounted and the
        environment is stopped. For more control of environment setup and teardown,
        use `create_environment()` instead.

        :param project_name: Name of project.
        :param project_path: Path to project.
        :param base_configuration: Base configuration to apply to instance.
        :param instance_name: Name of the instance to launch.
        :param allow_unstable: If true, allow unstable images to be launched.
        """
