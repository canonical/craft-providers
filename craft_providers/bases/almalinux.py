#
# Copyright 2023 Canonical Ltd.
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

"""Almalinux image(s)."""
import enum
import logging
import subprocess
from typing import Dict, List, Optional

from craft_providers.actions.snap_installer import Snap
from craft_providers.base import Base
from craft_providers.const import TIMEOUT_COMPLEX, TIMEOUT_UNPREDICTABLE
from craft_providers.errors import (
    BaseCompatibilityError,
    BaseConfigurationError,
    details_from_called_process_error,
)

logger = logging.getLogger(__name__)


class AlmaLinuxBaseAlias(enum.Enum):
    """Mappings for supported AlmaLinux images."""

    NINE = "9"


class AlmaLinuxBase(Base):
    """Support for AlmaLinux images.

    :cvar compatibility_tag: Tag/Version for variant of build configuration and
        setup.  Any change to this version would indicate that prior [versioned]
        instances are incompatible and must be cleaned.  As such, any new value
        should be unique to old values (e.g. incrementing).  It is suggested to
        extend this tag, not overwrite it, e.g.: compatibility_tag =
        f"{appname}-{BuildBase.compatibility_tag}.{apprevision}" to ensure base
        compatibility levels are maintained.
    :cvar instance_config_path: Path to persistent environment configuration
        used for compatibility checks (or other data).  Set to
        /etc/craft-instance.conf, but may be overridden for application-specific
        reasons.
    :cvar instance_config_class: Class defining instance configuration.  May be
        overridden with an application-specific subclass of InstanceConfiguration
        to enable application-specific extensions.

    :param alias: Base alias / version.
    :param environment: Environment to set in /etc/environment.
    :param hostname: Hostname to configure.
    :param snaps: Optional list of snaps to install on the base image.
    :param packages: Optional list of system packages to install on the base image.
    """

    compatibility_tag: str = f"almalinux-{Base.compatibility_tag}"

    def __init__(
        self,
        *,
        alias: AlmaLinuxBaseAlias,
        compatibility_tag: Optional[str] = None,
        environment: Optional[Dict[str, Optional[str]]] = None,
        hostname: str = "craft-almalinux-instance",
        snaps: Optional[List[Snap]] = None,
        packages: Optional[List[str]] = None,
    ) -> None:
        self.alias: AlmaLinuxBaseAlias = alias

        if environment is None:
            self.environment = self.default_command_environment()
        else:
            self.environment = environment

        if compatibility_tag:
            self.compatibility_tag = compatibility_tag

        self._set_hostname(hostname)
        self.snaps = snaps
        self.packages = [
            "autoconf",
            "automake",
            "gcc",
            "gcc-c++",
            "git",
            "make",
            "patch",
            "python3",
            "python3-devel",
            "python3-pip",
            "python3-pip-wheel",
            "python3-setuptools",
        ]

        if packages:
            self.packages.extend(packages)

    def _ensure_os_compatible(self) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        os_release = self._get_os_release()

        os_id = os_release.get("ID")
        if os_id != "almalinux":
            raise BaseCompatibilityError(
                reason=f"Expected OS 'almalinux', found {os_id!r}"
            )

        compat_version_id = self.alias.value
        version_id = os_release.get("VERSION_ID", "")
        version_id = version_id.split(".")[0]

        if version_id != compat_version_id:
            raise BaseCompatibilityError(
                reason=(
                    f"Expected OS version {compat_version_id!r},"
                    f" found {version_id!r}"
                )
            )

    def _setup_resolved(self) -> None:
        """Empty, AlmaLinux does not use systemd-resolved."""

    def _setup_networkd(self) -> None:
        """Empty, AlmaLinux does not use systemd-networkd."""

    def _enable_dnf_extra_repos(self) -> None:
        """Configure special OS extra repos.

        Enable "epel-release" repo for snapd.
        """
        try:
            command = ["dnf", "install", "-y", "epel-release"]
            self._execute_run(command, verify_network=True, timeout=TIMEOUT_COMPLEX)
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to enable extra repos.",
                details=details_from_called_process_error(error),
            ) from error

    def _pre_setup_packages(self) -> None:
        """Configure dnf package manager."""
        self._enable_dnf_extra_repos()

    def _setup_packages(self) -> None:
        """Install needed packages using dnf."""
        # update system
        try:
            self._execute_run(
                ["dnf", "update", "-y"],
                verify_network=True,
                timeout=TIMEOUT_UNPREDICTABLE,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update system using dnf.",
                details=details_from_called_process_error(error),
            ) from error

        # install required packages and user-defined packages
        if not self.packages:
            return
        try:
            command = ["dnf", "install", "-y"] + self.packages
            self._execute_run(
                command,
                verify_network=True,
                timeout=TIMEOUT_UNPREDICTABLE,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to install packages.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_snapd(self) -> None:
        """Install snapd and dependencies and wait until ready."""
        try:
            self._execute_run(
                ["dnf", "install", "-y", "snapd"],
                verify_network=True,
                timeout=TIMEOUT_COMPLEX,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup snapd.",
                details=details_from_called_process_error(error),
            ) from error

    def _clean_up(self) -> None:
        self._execute_run(["dnf", "autoremove", "-y"], timeout=TIMEOUT_COMPLEX)
        self._execute_run(["dnf", "clean", "packages", "-y"], timeout=TIMEOUT_COMPLEX)
