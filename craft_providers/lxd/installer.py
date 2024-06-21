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
import pathlib
import shutil
import subprocess
import sys

import requests
import requests_unixsocket  # type: ignore

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

    cmd = ["sudo"] if sudo else []

    cmd += ["snap", "install", "lxd"]

    logger.debug("installing LXD")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as error:
        raise errors.LXDInstallationError(
            reason="failed to init LXD",
            details=details_from_called_process_error(error),
        ) from error

    lxd = LXD()
    lxd.wait_ready(sudo=sudo)

    logger.debug("initialising LXD")
    lxd.init(auto=True, sudo=sudo)

    if not is_user_permitted():
        raise errors.LXDInstallationError(
            "user must be manually added to 'lxd' group before using LXD"
        )

    return lxd.version()


def is_initialized(*, remote: str, lxc: LXC) -> bool:
    """Verify that LXD has been initialized and configuration looks valid.

    If LXD has been installed but the user has not initialized it (lxd init),
    the default profile will be empty.  Trying to launch an instance or create
    a project using this profile will result in failures.

    LXD may be improperly initialized. To verify LXD was properly initialized, the
    default profile must contain a disk device with the path `/`.

    :returns: True if initialized, else False.
    """
    devices = lxc.profile_show(profile="default", remote=remote).get("devices")

    if not devices:
        return False

    return any(
        device.get("type") == "disk" and device.get("path") == "/"
        for device in devices.values()
    )


def is_installed() -> bool:
    """Check if LXD is installed.

    :returns: True if lxd is installed.
    """
    logger.debug("Checking if LXD is installed.")

    # check if non-snap lxd socket exists (for Arch or NixOS)
    if (
        pathlib.Path("/var/lib/lxd/unix.socket").is_socket()
        and shutil.which("lxd") is not None
    ):
        return True

    # query snapd API
    url = "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/lxd"
    try:
        snap_info = requests_unixsocket.get(url=url, params={"select": "enabled"})
    except requests.exceptions.ConnectionError as error:
        raise errors.ProviderError(
            brief="Unable to connect to snapd service."
        ) from error

    try:
        snap_info.raise_for_status()
    except requests.exceptions.HTTPError as error:
        logger.debug(f"Could not get snap info for LXD: {error}")
        return False

    # the LXD snap should be installed and active but check the status
    # for completeness
    try:
        status = snap_info.json()["result"]["status"]
    except (TypeError, KeyError):
        raise errors.ProviderError(brief="Unexpected response from snapd service.")

    logger.debug(f"LXD snap status: {status}")
    # snap status can be "installed" or "active" - "installed" revisions
    # are filtered from this API call with `select: enabled`
    return bool(status == "active") and shutil.which("lxd") is not None


def is_user_permitted() -> bool:
    """Check if user has permissions to connect to LXD.

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
            resolution=errors.LXD_INSTALL_HELP,
        )

    if not lxd.is_supported_version():
        version = lxd.version()
        min_version = lxd.minimum_required_version
        raise errors.LXDError(
            brief=(
                f"LXD {version!r} does not meet the"
                f" minimum required version {min_version!r}."
            ),
            resolution=errors.LXD_INSTALL_HELP,
        )

    if not is_user_permitted():
        raise errors.LXDError(
            brief="LXD requires additional permissions.",
            resolution=(
                "Ensure that the user is in the 'lxd' group.\n"
                + errors.LXD_INSTALL_HELP
            ),
        )

    if not is_initialized(lxc=lxc, remote=remote):
        raise errors.LXDError(
            brief="LXD has not been properly initialized.",
            details=(
                "The default LXD profile is empty or does not contain a disk device "
                "with a path of '/'."
            ),
            resolution=(
                "Execute 'lxd init --auto' to initialize LXD.\n"
                + errors.LXD_INSTALL_HELP
            ),
        )
