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
import pathlib
import subprocess
from typing import Dict, List, Optional

from craft_providers.actions.snap_installer import Snap
from craft_providers.base import Base
from craft_providers.errors import (
    BaseCompatibilityError,
    BaseConfigurationError,
    details_from_called_process_error,
)
from craft_providers.executor import Executor

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
    :param use_default_packages: Optional bool to enable/disable default packages.
    :param cache_path: (Optional) Path to the shared cache directory. If this is
        provided, shared cache directories will be mounted as appropriate.
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
        use_default_packages: bool = True,
        cache_path: Optional[pathlib.Path] = None,
    ) -> None:
        self._cache_path = cache_path

        # ignore enum subclass (see https://github.com/microsoft/pyright/issues/6750)
        self.alias: AlmaLinuxBaseAlias = alias  # pyright: ignore

        if environment is None:
            self._environment = self.default_command_environment()
        else:
            self._environment = environment

        if compatibility_tag:
            self.compatibility_tag = compatibility_tag

        self._set_hostname(hostname)

        self._packages: Optional[List[str]] = []
        if use_default_packages:
            self._packages.extend(
                [
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
            )

        if packages:
            self._packages.extend(packages)

        self._snaps = snaps

    def _ensure_os_compatible(self, executor: Executor) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        os_release = self._get_os_release(executor=executor)

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

    def _enable_dnf_extra_repos(self, executor: Executor) -> None:
        """Configure AlmaLinux special extra repos.

        Enable "epel-release" repo for snapd.
        """
        try:
            command = ["dnf", "install", "-y", "epel-release"]
            self._execute_run(
                command,
                executor=executor,
                verify_network=True,
                timeout=self._timeout_complex,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to enable extra repos.",
                details=details_from_called_process_error(error),
            ) from error

    def _pre_setup_packages(self, executor: Executor) -> None:
        """Configure dnf package manager."""
        self._enable_dnf_extra_repos(executor=executor)

    def _setup_packages(self, executor: Executor) -> None:
        """Install needed packages using dnf."""
        # update system
        try:
            self._execute_run(
                ["dnf", "update", "-y"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update system using dnf.",
                details=details_from_called_process_error(error),
            ) from error

        # install required packages and user-defined packages
        if not self._packages:
            return
        try:
            command = ["dnf", "install", "-y", *self._packages]
            self._execute_run(
                command,
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to install packages.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_snapd(self, executor: Executor) -> None:
        """Set up snapd using dnf."""
        try:
            self._execute_run(
                ["dnf", "install", "-y", "snapd"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_complex,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup snapd.",
                details=details_from_called_process_error(error),
            ) from error

    def _clean_up(self, executor: Executor) -> None:
        """Clean up unused packages and cached package files."""
        self._execute_run(
            ["dnf", "autoremove", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )
        self._execute_run(
            ["dnf", "clean", "packages", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )
