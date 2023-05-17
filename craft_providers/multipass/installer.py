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

"""Multipass Provider."""

import logging
import shutil
import subprocess
import sys
import time

from craft_providers.errors import details_from_called_process_error

from . import errors
from .multipass import Multipass

logger = logging.getLogger(__name__)


def install() -> str:
    """Install Multipass.

    :returns: Multipass version.

    :raises MultipassInstallationError: on error.
    """
    if sys.platform == "darwin":
        _install_darwin()
    elif sys.platform == "linux":
        _install_linux()
    elif sys.platform == "win32":
        raise errors.MultipassInstallationError(
            "automated installation not yet supported for Windows"
        )
    else:
        raise errors.MultipassInstallationError(
            f"unsupported platform {sys.platform!r}"
        )

    # TODO: Multipass needs time after being installed for `multipassd` to start.
    # Without a delay, errors could happen on launch, i.e.: "Remote "" is unknown or
    # unreachable." Current guidance is to sleep 20 seconds after install, but we
    # should have a more reliable and timely approach.
    # See: https://github.com/canonical/multipass/issues/1995
    time.sleep(20)

    multipass_version, _ = Multipass().wait_until_ready()
    return multipass_version


def _install_darwin() -> None:
    try:
        subprocess.run(["brew", "install", "multipass"], check=True)
        # wait for multipassd to start before changing the driver
        time.sleep(20)
        # this can be removed when multipass 1.12 is available on brew, because
        # qemu will be the new default
        subprocess.run(["multipass", "set", "local.driver=qemu"], check=True)
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


def is_installed() -> bool:
    """Check if Multipass is installed (and found on PATH).

    :returns: True if multipass is installed.
    """
    return shutil.which("multipass") is not None
