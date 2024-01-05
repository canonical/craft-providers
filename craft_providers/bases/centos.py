#
# Copyright 2021-2023 Canonical Ltd.
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

"""CentOS image(s)."""
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


class CentOSBaseAlias(enum.Enum):
    """Mappings for supported CentOS images."""

    SEVEN = "7"


class CentOSBase(Base):
    """Support for CentOS images.

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
    :param cache_path: Optional path to the shared cache directory. If this is
        provided, shared cache directories will be mounted as appropriate.
    """

    compatibility_tag: str = f"centos-{Base.compatibility_tag}"

    def __init__(
        self,
        *,
        alias: CentOSBaseAlias,
        compatibility_tag: Optional[str] = None,
        environment: Optional[Dict[str, Optional[str]]] = None,
        hostname: str = "craft-centos-instance",
        snaps: Optional[List[Snap]] = None,
        packages: Optional[List[str]] = None,
        use_default_packages: bool = True,
        cache_path: Optional[pathlib.Path] = None,
    ) -> None:
        self._cache_dir = cache_path

        # ignore enum subclass (see https://github.com/microsoft/pyright/issues/6750)
        self.alias: CentOSBaseAlias = alias  # pyright: ignore

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
                    "rh-python38-python",
                    "rh-python38-python-devel",
                    "rh-python38-python-pip",
                    "rh-python38-python-pip-wheel",
                    "rh-python38-python-setuptools",
                ]
            )

        if packages:
            self._packages.extend(packages)

        self._snaps = snaps

    @staticmethod
    def default_command_environment() -> Dict[str, Optional[str]]:
        """Provide default command environment dictionary.

        The minimum environment for the CentOS image to be configured and function
        properly.  This contains the default environment found in CentOS's
        /etc/profile, plus python 3.8 from "centos-release-scl".

        :returns: Dictionary of environment key/values.
        """
        return {
            "PATH": "/usr/local/sbin:/usr/local/bin:"
            "/opt/rh/rh-python38/root/usr/bin:"
            "/sbin:/bin:/usr/sbin:/usr/bin:/snap/bin"
        }

    def _ensure_os_compatible(self, executor: Executor) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        os_release = self._get_os_release(executor=executor)

        os_id = os_release.get("ID")
        if os_id not in ("centos", "rhel"):
            raise BaseCompatibilityError(
                reason=f"Expected OS 'centos', found {os_id!r}"
            )

        compat_version_id = self.alias.value
        version_id = os_release.get("VERSION_ID")

        if version_id != compat_version_id:
            raise BaseCompatibilityError(
                reason=(
                    f"Expected OS version {compat_version_id!r},"
                    f" found {version_id!r}"
                )
            )

    def _enable_yum_extra_repos(self, executor: Executor) -> None:
        """Configure CentOS special extra repos.

        Enable "epel-release" repo for snapd.
        Enable "centos-release-scl" for python 3.8.
        """
        try:
            command = ["yum", "install", "-y", "epel-release", "centos-release-scl"]
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
        """Configure yum package manager."""
        self._enable_yum_extra_repos(executor=executor)

    def _setup_packages(self, executor: Executor) -> None:
        """Configure yum, update cache and install needed packages."""
        # update system
        try:
            self._execute_run(
                ["yum", "update", "-y"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update system using yum.",
                details=details_from_called_process_error(error),
            ) from error

        # install required packages and user-defined packages
        if not self._packages:
            return
        try:
            command = ["yum", "install", "-y", *self._packages]
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
        """Set up snapd using yum."""
        try:
            self._execute_run(
                ["yum", "install", "-y", "snapd"],
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
            ["yum", "autoremove", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )
        self._execute_run(
            ["yum", "clean", "packages", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )
