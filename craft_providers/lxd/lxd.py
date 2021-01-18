# Copyright (C) 2020 Canonical Ltd
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
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class LXD:
    """LXD Interface."""

    def __init__(
        self,
        *,
        lxd_path: Optional[pathlib.Path] = None,
    ):
        if lxd_path is None:
            self.lxd_path = self._find_lxd()
        else:
            self.lxd_path = lxd_path

    def ensure_supported_version(self) -> None:
        """Ensure LXD meets minimum requirements.

        :raises RuntimeError: if unsupported.
        """
        proc = subprocess.run(
            [self.lxd_path, "version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        version = proc.stdout.decode().strip()
        version_components = version.split(".")
        major_minor = ".".join([version_components[0], version_components[1]])
        if float(major_minor) < 4.0:
            raise RuntimeError(
                "LXD version {version!r} is unsupported. Must be >= 4.0."
            )

    def _find_lxd(self) -> pathlib.Path:
        """Find lxd executable.

        Check PATH for executable, falling back to /snap/bin/lxd if not found.

        :returns: Path to lxd executable.  If executable not found, path is
                  /snap/bin/lxd.
        """
        which_lxd = shutil.which("lxd")

        # Default to standard snap location if not found in PATH.
        if which_lxd is None:
            lxd_path = pathlib.Path("/snap/bin/lxd")
        else:
            lxd_path = pathlib.Path(which_lxd)

        return lxd_path

    def setup(self) -> None:
        """Ensure LXD is installed with required version.

        :raises RuntimeError: if unsupported.
        """
        if not self.lxd_path.exists():
            subprocess.run(["sudo", "snap", "install", "lxd"], check=True)

            self.lxd_path = self._find_lxd()
            if not self.lxd_path.exists():
                raise RuntimeError("Failed to install LXD, or lxd not found in PATH.")

            subprocess.run(
                ["sudo", str(self.lxd_path), "waitready", "--timeout=30"], check=True
            )
            subprocess.run(["sudo", str(self.lxd_path), "init", "--auto"], check=True)

        self.ensure_supported_version()
