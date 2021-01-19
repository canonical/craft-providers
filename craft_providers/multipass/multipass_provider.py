# Copyright (C) 2021 Canonical Ltd
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

"""Multipass Provider."""

import logging
import sys

from craft_providers import images

from . import multipass_installer
from .multipass import Multipass
from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


class MultipassProviderError(Exception):
    """Multipass provider error.

    :param msg: Reason for provider error.
    """

    def __init__(self, msg: str) -> None:
        super().__init__()

        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class MultipassProvider:
    """Multipass Provider."""

    def __init__(
        self,
        *,
        platform: str = sys.platform,
    ) -> None:
        self._platform = platform

    def _configure_instance(
        self,
        *,
        instance: MultipassInstance,
        auto_clean: bool,
        image_configuration: images.Image,
    ) -> None:
        """Configure instance.

        Start to instance first to ensure it is started, as well as to cancel
        any outstanding delay-shtudown request.  Automatically clean image if
        auto_clean is True.

        :param instance: Instance to configure.
        :param auto_clean: Automatically clean incompatible instances.
        :param image_configuration: Image configuration.
        """
        instance.start()

        try:
            image_configuration.setup(executor=instance)
        except images.CompatibilityError as error:
            if auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    instance.name,
                    error.reason,
                )
                instance.delete(purge=True)
            else:
                raise error

    def create_instance(
        self,
        *,
        image_configuration: images.Image,
        image_name: str,
        name: str,
        auto_clean: bool,
        cpus: int = 2,
        disk_gb: int = 256,
        mem_gb: int = 2,
    ) -> MultipassInstance:
        """Create, start, and configure instance.

        Re-use existing instances, but ensure compatibility with specified image
        configuration.  If incompatible, automatically clean image if auto_clean
        is enabled.

        :param name: Name of instance.
        :param auto_clean: Automatically clean instances if required (e.g. if
            incompatible).
        :param image_name: Multipass image to use [[<remote:>]<image> | <url>].
        :param name: Name of instance to use/create.  e.g. "snapcraft:core20"
        :param cpus: Number of CPUs.
        :param disk_gb: Disk allocation in gigabytes.
        :param mem_gb: Memory allocation in gigabytes.

        :returns: Multipass instance.
        """
        # Update API object to utilize discovered path.
        multipass_path = multipass_installer.find_multipass()
        if multipass_path is None:
            raise MultipassProviderError("Multipass not found.")

        multipass = Multipass(multipass_path=multipass_path)

        instance = MultipassInstance(
            name=name,
            multipass=multipass,
        )

        if instance.exists():
            self._configure_instance(
                instance=instance,
                auto_clean=auto_clean,
                image_configuration=image_configuration,
            )

        # Re-check if instance exists as it may been cleaned.
        # If it doesn't exist, launch a fresh instance.
        if not instance.exists():
            instance.launch(
                cpus=cpus,
                disk_gb=disk_gb,
                mem_gb=mem_gb,
                image=image_name,
            )

        self._configure_instance(
            instance=instance,
            auto_clean=False,
            image_configuration=image_configuration,
        )
        return instance

    def is_installed(self) -> bool:
        """Check if Multipass is installed."""
        return multipass_installer.is_installed()

    def install(self) -> None:
        """Install Multipass."""
        multipass_installer.install(platform=self._platform)
