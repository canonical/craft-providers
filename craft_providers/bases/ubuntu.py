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
from functools import total_ordering
from textwrap import dedent
from typing import Dict, List, Optional

from craft_providers.actions.snap_installer import Snap
from craft_providers.base import Base
from craft_providers.errors import (
    BaseCompatibilityError,
    BaseConfigurationError,
    ProviderError,
    details_from_called_process_error,
)
from craft_providers.executor import Executor
from craft_providers.util.os_release import parse_os_release

logger = logging.getLogger(__name__)


@total_ordering
class BuilddBaseAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = "16.04"
    BIONIC = "18.04"
    FOCAL = "20.04"
    JAMMY = "22.04"
    NOBLE = "24.04"
    ORACULAR = "24.10"
    DEVEL = "devel"

    def __lt__(self, other):
        # Devels are the greatest, luckily 'd' > [0-9]
        return self.value < other.value


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


def ensure_guest_compatible(
    base_configuration: Base,
    instance: Executor,
    lxd_version: str,
) -> None:
    """Ensure host is compatible with guest instance."""
    if not issubclass(type(base_configuration), BuilddBase):
        # Not ubuntu, not sure how to check
        return

    guest_os_release = base_configuration._get_os_release(executor=instance)
    guest_base_alias = BuilddBaseAlias(guest_os_release.get("VERSION_ID"))

    # Without loopback executor:
    host_base_alias = BuilddBaseAlias(parse_os_release().get("VERSION_ID"))

    # If the host OS is focal (20.04) or older, and the guest OS is oracular (24.10)
    # or newer, then the host lxd must be >=5.0.4 or >=5.21.2, and kernel must be
    # 5.15 or newer.  Otherwise, weird systemd failures will occur due to a mismatch
    # between cgroupv1 and v2 support.
    # https://discourse.ubuntu.com/t/lxd-5-0-4-lts-has-been-released/49681#p-123331-support-for-ubuntu-oracular-containers-on-cgroupv2-hosts
    if (host_base_alias > BuilddBaseAlias.FOCAL or
        guest_base_alias < BuilddBaseAlias.ORACULAR):
        return

    lxd_version_split = [int(vernum) for vernum in lxd_version.split(".")]
    major = lxd_version_split[0]
    minor = lxd_version_split[1]
    try:
        patch = lxd_version_split[2]
    except IndexError:
        # LXD version strings sometimes omit the patch - call it zero
        patch = 0
    lxd_exception = ProviderError(
        brief="This combination of guest and host OS versions requires a newer lxd version.",
        resolution="Ensure you have lxd >=5.0.4 or >=5.21.2 installed - try the lxd snap.",
    )
    if major == 5:
        # Major is 5, we care about patch versions given the minor
        if minor == 0 and patch < 4:
            raise lxd_exception
        if minor == 21 and patch < 2:
            raise lxd_exception
    if major < 5:
        raise lxd_exception

    kernel_version = [int(vernum) for vernum in host_instance.execute_run(
        ["uname", "-r"],
        capture_output=True,
        text=True
    ).stdout.split(".")]
    if (kernel_version[0] == 5 and kernel_version[1] < 15) or kernel_version[0] < 5:
        raise ProviderError(
            brief="This combination of guest and host OS versions requires a newer kernel version.",
            resolution="Ensure you have kernel 5.15 or newer - try the HWE kernel.",
        )
