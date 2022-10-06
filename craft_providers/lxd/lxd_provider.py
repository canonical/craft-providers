# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022 Canonical Ltd.
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

"""LXD Provider class."""

import contextlib
import logging
import pathlib
from typing import Generator

from craft_providers import Executor, Provider
from craft_providers.base import Base
from craft_providers.bases import BaseConfigurationError, BuilddBaseAlias

from .errors import LXDError
from .installer import ensure_lxd_is_ready, install, is_installed
from .launcher import launch
from .lxc import LXC
from .lxd_instance import LXDInstance
from .remotes import configure_buildd_image_remote

logger = logging.getLogger(__name__)


PROVIDER_BASE_TO_LXD_BASE = {
    BuilddBaseAlias.BIONIC.value: "core18",
    BuilddBaseAlias.FOCAL.value: "core20",
    BuilddBaseAlias.JAMMY.value: "core22",
}


class LXDProvider(Provider):
    """LXD build environment provider.

    This class is not stable and is likely to change. This class will be stable and
    recommended for use in the release of craft-providers 2.0.

    :param lxc: Optional lxc client to use.
    :param lxd_project: LXD project to use (default is default).
    :param lxd_remote: LXD remote to use (default is local).
    """

    def __init__(
        self,
        *,
        lxc: LXC = LXC(),
        lxd_project: str = "default",
        lxd_remote: str = "local",
    ) -> None:
        self.lxc = lxc
        self.lxd_project = lxd_project
        self.lxd_remote = lxd_remote

    @classmethod
    def ensure_provider_is_available(cls) -> None:
        """Ensure provider is available and ready, installing if required.

        :raises LXDInstallationError: if LXD cannot be installed
        :raises LXDError: if provider is not available
        """
        if not is_installed():
            install()
        ensure_lxd_is_ready()

    @classmethod
    def is_provider_installed(cls) -> bool:
        """Check if provider is installed.

        :returns: True if installed.
        """
        return is_installed()

    def create_environment(self, *, instance_name: str) -> Executor:
        """Create a bare environment for specified base.

        No initializing, launching, or cleaning up of the environment occurs.

        :param instance_name: Name of the instance.
        """
        return LXDInstance(
            name=instance_name,
            project=self.lxd_project,
            remote=self.lxd_remote,
        )

    @contextlib.contextmanager
    def launched_environment(
        self,
        *,
        project_name: str,
        project_path: pathlib.Path,
        base_configuration: Base,
        build_base: str,
        instance_name: str,
    ) -> Generator[Executor, None, None]:
        """Configure and launch environment for specified base.

        When this method loses context, all directories are unmounted and the
        environment is stopped. For more control of environment setup and teardown,
        use `create_environment()` instead.

        :param project_name: Name of project.
        :param project_path: Path to project.
        :param base_configuration: Base configuration to apply to instance.
        :param build_base: Base to build from.
        :param instance_name: Name of the instance to launch.

        :raises LXDError: if instance cannot be configured and launched
        """
        image_remote = configure_buildd_image_remote()

        try:
            instance = launch(
                name=instance_name,
                base_configuration=base_configuration,
                image_name=PROVIDER_BASE_TO_LXD_BASE[build_base],
                image_remote=image_remote,
                auto_clean=True,
                auto_create_project=True,
                map_user_uid=True,
                uid=project_path.stat().st_uid,
                use_snapshots=True,
                project=self.lxd_project,
                remote=self.lxd_remote,
            )
        except (BaseConfigurationError) as error:
            raise LXDError(str(error)) from error

        try:
            yield instance
        finally:
            # Ensure to unmount everything and stop instance upon completion.
            instance.unmount_all()
            instance.stop()
