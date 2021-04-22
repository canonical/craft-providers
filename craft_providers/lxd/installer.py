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

"""LXD Provider."""

import logging
import os
import shutil
import subprocess
import sys

from craft_providers.errors import details_from_called_process_error

from . import errors
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

    return lxd.version()


def is_installed() -> bool:
    """Check if LXD is installed (and found on PATH).

    :returns: True if lxd is installed.
    """
    return shutil.which("lxd") is not None
