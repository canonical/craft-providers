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

"""Multipass Provider."""

import logging
import shutil
import subprocess
import sys

from craft_providers import Base
from craft_providers.bases.errors import BaseCompatibilityError
from craft_providers.errors import details_from_called_process_error

from . import errors
from .multipass import Multipass
from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


def _install_darwin() -> None:
    try:
        subprocess.run(["brew", "cask", "install", "multipass"], check=True)
    except subprocess.CalledProcessError as error:
        raise errors.MultipassInstallationError(
            "error during brew installation",
            details=details_from_called_process_error(error),
        ) from error


def _install_linux() -> None:
    try:
        subprocess.run(["sudo", "snap", "install", "multipass"], check=True)
    except subprocess.CalledProcessError as error:
        raise errors.MultipassInstallationError(
            "error during snap installation",
            details=details_from_called_process_error(error),
        ) from error


def _install_windows() -> None:
    raise errors.MultipassInstallationError(
        "automated installation not yet supported for Windows"
    )


class MultipassProvider:  # pylint: disable=no-self-use
    """Multipass Provider."""

    def _configure_instance(
        self,
        *,
        instance: MultipassInstance,
        auto_clean: bool,
        base_configuration: Base,
    ) -> None:
        """Configure instance.

        Start to instance first to ensure it is started, as well as to cancel
        any outstanding delay-shtudown request.  Automatically clean image if
        auto_clean is True.

        :param instance: Instance to configure.
        :param auto_clean: Automatically clean incompatible instances.
        :param base_configuration: Base configuration to apply.

        :raises BaseCompatibilityError: If image is incompatible and auto_clean
            is disabled.
        """
        instance.start()

        try:
            base_configuration.setup(executor=instance)
        except BaseCompatibilityError as error:
            if auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    instance.name,
                    error.reason,
                )
                instance.delete()
            else:
                raise error

    def create_instance(
        self,
        *,
        auto_clean: bool,
        base_configuration: Base,
        cpus: int = 2,
        disk_gb: int = 256,
        image_name: str,
        mem_gb: int = 2,
        name: str,
    ) -> MultipassInstance:
        """Create, start, and configure instance.

        Re-use existing instances, but ensure compatibility with specified image
        configuration.  If incompatible, automatically clean instance if
        auto_clean is enabled.

        :param name: Name of instance.
        :param auto_clean: Automatically clean instances if required (e.g. if
            incompatible).
        :param base_configuration: Base configuration to apply to instance.
        :param cpus: Number of CPUs.
        :param disk_gb: Disk allocation in gigabytes.
        :param image_name: Multipass image to use, e.g. snapcraft:core20.
        :param mem_gb: Memory allocation in gigabytes.

        :returns: Multipass instance.
        """
        multipass = Multipass()
        instance = MultipassInstance(
            name=name,
            multipass=multipass,
        )

        if instance.exists():
            self._configure_instance(
                instance=instance,
                auto_clean=auto_clean,
                base_configuration=base_configuration,
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
            base_configuration=base_configuration,
        )
        return instance

    def install(self) -> str:
        """Install Multipass.

        :returns: Multipass version.

        :raises MultipassInstallationError: on error.
        """
        if sys.platform == "darwin":
            _install_darwin()
        elif sys.platform == "linux":
            _install_linux()
        elif sys.platform == "win32":
            _install_windows()
        else:
            raise errors.MultipassInstallationError(
                f"unsupported platform {sys.platform!r}"
            )

        multipass_version, _ = Multipass().wait_until_ready()
        return multipass_version

    def is_installed(self) -> bool:
        """Check if Multipass is installed (and found on PATH).

        :returns: Bool if multipass is installed.
        """
        return not shutil.which("multipass") is None
