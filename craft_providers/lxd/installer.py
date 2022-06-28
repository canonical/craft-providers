#
# Copyright 2021 Canonical Ltd.
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

"""LXD Provider."""

import logging
import os
import shutil
import subprocess
import sys

from craft_providers.errors import details_from_called_process_error

from . import errors
from .lxc import LXC
from .lxd import LXD

logger = logging.getLogger(__name__)


def install(sudo: bool = True) -> str:
    """Install LXD.

    Install application, using sudo if specified.

    :returns: LXD version.

    :raises LXDInstallationError: on installation error.
    :raises LXDError: on unexpected error.
    """
    if sys.platform != "linux":
        raise errors.LXDInstallationError(f"unsupported platform {sys.platform!r}")

    if not sudo and os.geteuid() != 0:
        raise errors.LXDInstallationError("sudo required if not running as root")

    if sudo:
        cmd = ["sudo"]
    else:
        cmd = []

    cmd += ["snap", "install", "lxd"]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as error:
        raise errors.LXDInstallationError(
            "Failed to init LXD.",
            details=details_from_called_process_error(error),
        ) from error

    lxd = LXD()
    lxd.wait_ready(sudo=sudo)
    lxd.init(auto=True, sudo=sudo)

    if not is_user_permitted():
        raise errors.LXDInstallationError(
            "user must be manually added to 'lxd' group before using LXD"
        )

    return lxd.version()


def is_initialized(*, remote: str, lxc: LXC) -> bool:
    """Verify that LXD has been initialized and configuration looks valid.

    If LXD has been installed but the user has not initialized it (lxd init),
    the default profile won't have devices configured.  Trying to launch an
    instance or create a project using this profile will result in failures.

    :returns: True if initialized, else False.
    """
    devices = lxc.profile_show(profile="default", remote=remote).get("devices")
    return bool(devices)


def is_installed() -> bool:
    """Check if LXD is installed (and found on PATH).

    :returns: True if lxd is installed.
    """
    return shutil.which("lxd") is not None


def is_user_permitted() -> bool:
    """Check if user has permisisons to connect to LXD.

    :returns: True if user has correct permissions.
    """
    return os.access("/var/snap/lxd/common/lxd/unix.socket", os.O_RDWR)


def ensure_lxd_is_ready(
    *, remote: str = "local", lxc: LXC = LXC(), lxd: LXD = LXD()
) -> None:
    """Ensure LXD is ready for use.

    :raises LXDError: on error.
    """
    if not is_installed():
        raise errors.LXDError(
            brief="LXD is required, but not installed.",
            resolution="Visit https://snapcraft.io/lxd for instructions "
            "on how to install the LXD snap for your distribution.",
        )

    if not lxd.is_supported_version():
        version = lxd.version()
        min_version = lxd.minimum_required_version
        raise errors.LXDError(
            brief=(
                f"LXD {version!r} does not meet the"
                f" minimum required version {min_version!r}."
            ),
            resolution="Visit https://snapcraft.io/lxd for instructions "
            "on how to install the LXD snap for your distribution.",
        )

    if not is_user_permitted():
        raise errors.LXDError(
            brief="LXD requires additional permissions.",
            resolution="Ensure that the user is in the 'lxd' group.",
        )

    if not is_initialized(lxc=lxc, remote=remote):
        raise errors.LXDError(
            brief="LXD has not been properly initialized.",
            resolution="Execute 'lxd init --auto' to initialize LXD.",
        )
