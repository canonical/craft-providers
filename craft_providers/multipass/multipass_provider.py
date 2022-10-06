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

"""Multipass Provider class."""

import contextlib
import logging
import pathlib
from typing import Generator

from craft_providers import Executor, Provider, base, bases

from ._launch import launch
from ._ready import ensure_multipass_is_ready
from .errors import MultipassError
from .installer import install, is_installed
from .multipass import Multipass
from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


PROVIDER_BASE_TO_MULTIPASS_BASE = {
    bases.BuilddBaseAlias.BIONIC.value: "snapcraft:18.04",
    bases.BuilddBaseAlias.FOCAL.value: "snapcraft:20.04",
    bases.BuilddBaseAlias.JAMMY.value: "snapcraft:22.04",
}


class MultipassProvider(Provider):
    """Multipass build environment provider.

    This class is not stable and is likely to change. This class will be stable and
    recommended for use in the release of craft-providers 2.0.

    :param multipass: Optional Multipass client to use.
    """

    def __init__(self, instance: Multipass = Multipass()) -> None:
        self.multipass = instance

    @classmethod
    def ensure_provider_is_available(cls) -> None:
        """Ensure provider is available, prompting the user to install it if required.

        :raises MultipassError: if provider is not available.
        """
        if not is_installed():
            install()
        ensure_multipass_is_ready()

    def create_environment(self, *, instance_name: str) -> Executor:
        """Create a bare environment for specified base.

        No initializing, launching, or cleaning up of the environment occurs.

        :param name: Name of the instance.
        """
        return MultipassInstance(name=instance_name)

    @classmethod
    def is_provider_installed(cls) -> bool:
        """Check if provider is installed.

        :returns: True if installed.
        """
        return is_installed()

    @contextlib.contextmanager
    def launched_environment(
        self,
        *,
        project_name: str,
        project_path: pathlib.Path,
        base_configuration: base.Base,
        build_base: str,
        instance_name: str,
    ) -> Generator[Executor, None, None]:
        """Configure and launch environment for specified base.

        When this method loses context, all directories are unmounted and the
        environment is stopped. For more control of environment setup and teardown,
        use `create_environment()` instead.

        :param project_name: Name of the project.
        :param project_path: Path to project.
        :param base_configuration: Base configuration to apply to instance.
        :param build_base: Base to build from.
        :param instance_name: Name of the instance to launch.
        """
        try:
            instance = launch(
                name=instance_name,
                base_configuration=base_configuration,
                image_name=PROVIDER_BASE_TO_MULTIPASS_BASE[build_base],
                cpus=2,
                disk_gb=64,
                mem_gb=2,
                auto_clean=True,
            )
        except (bases.BaseConfigurationError) as error:
            raise MultipassError(str(error)) from error

        try:
            yield instance
        finally:
            # Ensure to unmount everything and stop instance upon completion.
            instance.unmount_all()
            instance.stop()
