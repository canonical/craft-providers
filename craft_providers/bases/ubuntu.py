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

"""Ubuntu image(s)."""
import enum
import io
import logging
import pathlib
import subprocess
from textwrap import dedent
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


class BuilddBaseAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = "16.04"
    BIONIC = "18.04"
    FOCAL = "20.04"
    JAMMY = "22.04"
    NOBLE = "24.04"
    ORACULAR = "24.10"
    DEVEL = "devel"


class BuilddBase(Base):
    """Support for Ubuntu minimal buildd images.

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

    compatibility_tag: str = f"buildd-{Base.compatibility_tag}"

    def __init__(
        self,
        *,
        alias: BuilddBaseAlias,
        compatibility_tag: Optional[str] = None,
        environment: Optional[Dict[str, Optional[str]]] = None,
        hostname: str = "craft-buildd-instance",
        snaps: Optional[List[Snap]] = None,
        packages: Optional[List[str]] = None,
        use_default_packages: bool = True,
        cache_path: Optional[pathlib.Path] = None,
    ) -> None:
        # ignore enum subclass (see https://github.com/microsoft/pyright/issues/6750)
        self.alias: BuilddBaseAlias = alias  # pyright: ignore

        self._cache_path = cache_path

        if environment is None:
            self._environment = self.default_command_environment()
        else:
            self._environment = environment

        # ensure apt installs are always non-interactive
        self._environment.update(
            {
                "DEBIAN_FRONTEND": "noninteractive",
                "DEBCONF_NONINTERACTIVE_SEEN": "true",
                "DEBIAN_PRIORITY": "critical",
            }
        )

        if compatibility_tag:
            self.compatibility_tag = compatibility_tag

        self._set_hostname(hostname)

        self._packages: Optional[List[str]] = []
        if use_default_packages:
            self._packages.extend(
                [
                    "apt-utils",
                    "build-essential",
                    "curl",
                    "fuse",
                    "udev",
                    "python3",
                    "python3-dev",
                    "python3-pip",
                    "python3-wheel",
                    "python3-setuptools",
                ]
            )

        if packages:
            self._packages.extend(packages)

        self._snaps = snaps

    def _disable_automatic_apt(self, executor: Executor) -> None:
        """Disable automatic apt actions.

        This should happen as soon as possible in the instance overall setup,
        to reduce the chances of an automatic apt work being triggered during
        the setup itself (because it includes apt work which may clash
        the triggered unattended jobs).
        """
        # set the verification frequency in 10000 days and disable the upgrade
        content = dedent(
            """\
            APT::Periodic::Update-Package-Lists "10000";
            APT::Periodic::Unattended-Upgrade "0";
        """
        ).encode()
        executor.push_file_io(
            destination=pathlib.PurePosixPath("/etc/apt/apt.conf.d/20auto-upgrades"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    def _ensure_os_compatible(self, executor: Executor) -> None:
        """Ensure OS is compatible with Base."""
        os_release = self._get_os_release(executor=executor)

        os_name = os_release.get("NAME")
        if os_name != "Ubuntu":
            raise BaseCompatibilityError(
                reason=f"Expected OS 'Ubuntu', found {os_name!r}"
            )

        compat_version_id = self.alias.value
        version_id = os_release.get("VERSION_ID")

        if compat_version_id == BuilddBaseAlias.DEVEL.value:
            logger.debug(
                "Ignoring OS version mismatch for %r because base is %r.",
                version_id,
                compat_version_id,
            )
            return

        if version_id != compat_version_id:
            raise BaseCompatibilityError(
                reason=(
                    f"Expected OS version {compat_version_id!r},"
                    f" found {version_id!r}"
                )
            )

    def _post_setup_os(self, executor: Executor) -> None:
        """Ubuntu specific post-setup OS tasks."""
        self._disable_automatic_apt(executor=executor)

    def _setup_network(self, executor: Executor) -> None:
        """Set up the basic network with systemd-networkd and systemd-resolved."""
        self._setup_hostname(executor=executor)
        self._setup_resolved(executor=executor)
        self._setup_networkd(executor=executor)

    def _pre_setup_packages(self, executor: Executor) -> None:
        """Configure apt, update database."""
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00no-recommends"),
            content=io.BytesIO(b'APT::Install-Recommends "false";\n'),
            file_mode="0644",
        )

        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00update-errors"),
            content=io.BytesIO(b'APT::Update::Error-Mode "any";\n'),
            file_mode="0644",
        )

        try:
            self._execute_run(
                ["apt-get", "update"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update apt cache.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_packages(self, executor: Executor) -> None:
        """Use apt install required packages and user-defined packages."""
        if not self._packages:
            return
        try:
            command = ["apt-get", "install", "-y", *self._packages]
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
        """Install snapd and dependencies and wait until ready."""
        try:
            self._execute_run(
                ["apt-get", "install", "-y", "snapd"],
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
        self._execute_run(
            ["apt-get", "autoremove", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )
        self._execute_run(
            ["apt-get", "clean", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )


# Backward compatible, will be removed in 2.0
default_command_environment = BuilddBase.default_command_environment
