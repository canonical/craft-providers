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

"""Host Executor."""
import logging
import pathlib
import shlex
import shutil
import subprocess
from typing import List, Optional

from .. import Executor

logger = logging.getLogger(__name__)


class HostExecutor(Executor):
    """Run commands directly on host.

    :param sudo_user: Optional sudo user to run commands with.  sudo will not be
        used if None.
    """

    def __init__(self, *, sudo_user: Optional[str] = "root") -> None:
        super().__init__()
        self.sudo_user = sudo_user

    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: bytes,
        file_mode: str,
        gid: int = 0,
        uid: int = 0,
    ) -> None:
        """Create file with content and file mode."""
        raise RuntimeError("unimplemented")

    def execute_run(
        self, command: List[str], check=True, **kwargs
    ) -> subprocess.CompletedProcess:
        """Execute command using subprocess.run().

        :param command: Command to execute.
        :param check: Raise exception on failure.
        :param kwargs: Keyword args to pass to subprocess.run().

        :returns: Completed process.

        :raises subprocess.CalledProcessError: if command fails and check is
            True.
        """
        command = self._prepare_execute_args(command=command)
        return subprocess.run(command, check=check, **kwargs)

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute command using Popen().

        :param command: Command to execute.
        :param kwargs: Keyword args to pass to Popen().

        :returns: Popen process.
        """
        command = self._prepare_execute_args(command=command)
        return subprocess.Popen(command, **kwargs)

    def mount(  # pylint: disable=unused-argument
        self, *, source: pathlib.Path, destination: pathlib.Path
    ) -> bool:
        """Not applicable for host provider.

        :param source: Source to mount.
        :param destination: Destination to mount to.
        """
        return False

    def _prepare_execute_args(self, command: List[str]) -> List[str]:
        """Formulate command, accounting for possible env & cwd."""
        if self.sudo_user is not None:
            final_cmd = ["sudo", "-H", "-u", self.sudo_user]
        else:
            final_cmd = []

        final_cmd.extend(command)

        quoted = " ".join([shlex.quote(c) for c in final_cmd])
        logger.info("Executing: %s", quoted)

        return final_cmd

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy source file/directory from environment to host destination.

        Standard "cp -r" rules apply:

            - if source is directory, copy happens recursively.

            - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Target directory to copy from.
        :param destination: Host destination directory to copy to.
        """
        if source.is_file():
            shutil.copy2(source, destination)
        elif source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy host source file/directory into environment at destination.

        Standard "cp -r" rules apply:
        - if source is directory, copy happens recursively.
        - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Host directory to copy.
        :param destination: Target destination directory to copy to.
        """
        if source.is_file():
            shutil.copy2(source, destination)
        elif source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"Source {source} not found.")
