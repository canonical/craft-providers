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

"""LXD command-line interface helpers."""
import logging
import pathlib
import subprocess
from typing import Optional

import packaging.version

from craft_providers.errors import details_from_called_process_error

from .errors import LXDError

logger = logging.getLogger(__name__)


class LXD:
    """Interface to `lxd` command-line.

    :param lxd_path: Path to lxd.
    :cvar minimum_required_version: Minimum lxd version required for compatibility.
    """

    minimum_required_version = "4.0"

    def __init__(self, *, lxd_path: pathlib.Path = pathlib.Path("lxd")) -> None:
        self.lxd_path = lxd_path

    def init(self, *, auto: bool = False, sudo: bool = False) -> None:
        """Initialize LXD.

        Sudo is required if user is not in lxd group.

        :param auto: Use default settings.
        :param sudo: Use sudo to invoke init.
        """
        cmd = ["sudo"] if sudo else []

        cmd += [str(self.lxd_path), "init"]

        if auto:
            cmd.append("--auto")

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as error:
            raise LXDError(
                "Failed to init LXD.",
                details=details_from_called_process_error(error),
            ) from error

    def is_supported_version(self) -> bool:
        """Check if LXD version is supported.

        A helper to check if LXD meets minimum supported version for
        craft-providers (currently >= 4.0).

        :returns: True if installed version is supported.
        """
        minimum_version = packaging.version.parse(self.minimum_required_version)
        version = self.version()

        if "." not in version:
            raise LXDError(
                "Failed to parse LXD version.",
                details=f"Version data returned: {version!r}",
            )

        return packaging.version.parse(version) >= minimum_version

    def version(self) -> str:
        """Query LXD version.

        The version is of the format:
        <major>.<minor>[.<micro>] [LTS]

        Version examples:
        - 5.21.0 LTS
        - 4.13
        - 4.0.5
        - 2.0.12

        :returns: Version string.
        """
        cmd = [str(self.lxd_path), "version"]

        try:
            proc = subprocess.run(cmd, capture_output=True, check=True, text=True)
        except subprocess.CalledProcessError as error:
            raise LXDError(
                "Failed to query LXD version.",
                details=details_from_called_process_error(error),
            ) from error

        version_string = proc.stdout.strip()
        if version_string:
            return version_string.split()[0]

        raise LXDError(
            "Failed to parse LXD version.",
            details=f"Version data returned: {version_string!r}",
        )

    def wait_ready(
        self,
        *,
        sudo: bool = False,
        timeout: Optional[int] = None,
    ) -> None:
        """Wait until LXD is ready.

        Sudo is required if user is not in lxd group.

        :param sudo: Use sudo to invoke waitready.
        :param timeout: Timeout in seconds.
        """
        cmd = ["sudo"] if sudo else []

        cmd += [str(self.lxd_path), "waitready"]

        if timeout is not None:
            cmd.append(f"--timeout={timeout}")

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as error:
            raise LXDError(
                "Failed to wait for LXD to get ready.",
                details=details_from_called_process_error(error),
            ) from error
