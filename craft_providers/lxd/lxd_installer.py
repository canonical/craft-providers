# Copyright (C) 2021 Canonical Ltd
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

"""LXD manager."""

import logging
import pathlib
import subprocess
import sys
from typing import Optional

from craft_providers.util import path

logger = logging.getLogger(__name__)


class LXDInstallerError(Exception):
    """LXD Installation Error.

    :param reason: Reason for install failure.
    """

    def __init__(self, reason: str) -> None:
        super().__init__()

        self.reason = reason

    def __str__(self) -> str:
        return f"Failed to install LXD: {self.reason}"


def _get_version(*, lxd_path: pathlib.Path) -> str:
    """Get LXD version."""
    _wait_until_ready(lxd_path=lxd_path, use_sudo=False)

    proc = subprocess.run(
        [str(lxd_path), "version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return proc.stdout.decode().strip()


def ensure_supported_version(*, lxd_path: pathlib.Path) -> None:
    """Ensure LXD meets minimum requirements.

    :raises LXDInstallerError: if unsupported.
    """
    version = _get_version(lxd_path=lxd_path)
    if version is None or not _is_supported_version(version=version):
        raise LXDInstallerError(f"version {version!r} unsupported (must be >= 4.0)")


def find_lxc() -> Optional[pathlib.Path]:
    """Find lxc executable.

    Check PATH for executable, falling back to platform-specific path if not
    found.

    :returns: Path to lxd executable.  If executable not found, path
                is /snap/bin/lxc.
    """
    bin_name = "lxc"

    # TODO: platform-specific sane options
    fallback = pathlib.Path("/snap/bin/lxc")

    bin_path = path.which(bin_name)
    if bin_path is None and fallback.exists():
        return fallback

    if bin_path is not None and bin_path.exists():
        return bin_path

    return None


def find_lxd() -> Optional[pathlib.Path]:
    """Find lxd executable.

    Check PATH for executable, falling back to platform-specific path if not
    found.

    :returns: Path to lxd executable.  If executable not found, path
                is /snap/bin/lxd.
    """
    bin_name = "lxd"

    # TODO: platform-specific sane options
    fallback = pathlib.Path("/snap/bin/lxd")

    bin_path = path.which(bin_name)
    if bin_path is None and fallback.exists():
        return fallback

    if bin_path is not None and bin_path.exists():
        return bin_path

    return None


def _initialize_server(lxd_path: pathlib.Path, use_sudo: bool) -> None:
    if use_sudo:
        cmd = ["sudo"]
    else:
        cmd = []

    cmd += [str(lxd_path), "init", "--auto"]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as error:
        raise LXDInstallerError("encountered error initializing lxd") from error


def _install_linux(*, use_sudo: bool) -> None:
    if use_sudo:
        cmd = ["sudo"]
    else:
        cmd = []

    cmd += ["snap", "install", "lxd"]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as error:
        raise LXDInstallerError("encountered error installing 'lxd' snap") from error


def install(*, platform: str = sys.platform) -> pathlib.Path:
    """Install LXD client & server.

    :param platform: Host platform.

    :raises LXDInstallerError: On installation failure.
    """
    lxd_path = find_lxd()
    if lxd_path is None:
        if platform == "linux":
            _install_linux(use_sudo=True)
        else:
            raise LXDInstallerError(f"platform {platform} not supported")

        lxd_path = find_lxd()
        if lxd_path is None:
            raise LXDInstallerError("cannot find 'lxd' on PATH")

        _wait_until_ready(lxd_path=lxd_path, use_sudo=True)
        _initialize_server(lxd_path=lxd_path, use_sudo=True)

    ensure_supported_version(lxd_path=lxd_path)
    return lxd_path


def is_installed() -> bool:
    """Check if LXD is installed (found valid lxd executable)."""
    return find_lxd() is not None


def _is_supported_version(*, version: str) -> bool:
    """Check if Lxd minimum supported version."""
    version_components = version.split(".")
    major_minor = ".".join([version_components[0], version_components[1]])

    return float(major_minor) >= 4.0


def _wait_until_ready(
    *,
    lxd_path: pathlib.Path,
    use_sudo: bool,
    timeout_secs: int = 30,
) -> None:
    """Wait until LXD is ready."""
    if use_sudo:
        cmd = ["sudo"]
    else:
        cmd = []

    cmd += [str(lxd_path), "waitready", f"--timeout={timeout_secs}"]

    subprocess.run(cmd, check=True)
