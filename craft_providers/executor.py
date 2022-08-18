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

"""Executor module."""

import contextlib
import io
import logging
import pathlib
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class Executor(ABC):
    """Interfaces to execute commands and move data in/out of an environment."""

    @abstractmethod
    def execute_popen(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.Path] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Execute a command in instance, using subprocess.Popen().

        The process' environment will inherit the execution environment's
        default environment (PATH, etc.), but can be additionally configured via
        env parameter.

        :param command: Command to execute.
        :param env: Additional environment to set for process.
        :param kwargs: Additional keyword arguments to pass.

        :returns: Popen instance.
        """

    @abstractmethod
    def execute_run(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.Path] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute a command using subprocess.run().

        The process' environment will inherit the execution environment's
        default environment (PATH, etc.), but can be additionally configured via
        env parameter.

        :param command: Command to execute.
        :param env: Additional environment to set for process.
        :param kwargs: Keyword args to pass to subprocess.run().

        :returns: Completed process.

        :raises subprocess.CalledProcessError: if command fails and check is
            True.
        """

    @abstractmethod
    def pull_file(self, *, source: pathlib.PurePath, destination: pathlib.Path) -> None:
        """Copy a file from the environment to host.

        :param source: Environment file to copy.
        :param destination: Host file path to copy to.  Parent directory
            (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises ProviderError: On error copying file.
        """

    @contextlib.contextmanager
    def temporarily_pull_file(
        self, *, source: pathlib.Path, missing_ok: bool = False
    ) -> Generator[Optional[pathlib.Path], None, None]:
        """Copy a file from the environment to a temporary file in the host.

        This is mainly a layer above `pull_file` that pulls the file into a
        temporary path which is cleaned later.

        Works as a context manager, provides the file path in the host as target.

        :param source: Environment file to copy.
        :param missing_ok: Do not raise an error if the file does not exist in the
            environment; in this case the target will be None.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist (and `missing_ok` is False).
        :raises ProviderError: On error copying file content.
        """
        # Get a temporary file path (placing it in current directory as it's the
        # most predictable place where a potential strictly-snapped app could write)
        tmp_file = tempfile.NamedTemporaryFile(
            delete=False, prefix="craft-providers-", suffix=".temp", dir="."
        )
        tmp_file.close()

        local_filepath = pathlib.Path(tmp_file.name)
        try:
            self.pull_file(source=source, destination=local_filepath)
        except FileNotFoundError:
            if missing_ok:
                yield None
            else:
                raise
        else:
            yield local_filepath
        finally:
            local_filepath.unlink()

    @abstractmethod
    def push_file(self, *, source: pathlib.Path, destination: pathlib.PurePath) -> None:
        """Copy a file from the host into the environment.

        :param source: Host file to copy.
        :param destination: Target environment file path to copy to.  Parent
            directory (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises ProviderError: On error copying file.
        """

    @abstractmethod
    def push_file_io(
        self,
        *,
        destination: pathlib.PurePath,
        content: io.BytesIO,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        """Create or replace a file with specified content and file mode.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param group: File owner group.
        :param user: File owner user.
        """

    @abstractmethod
    def delete(self) -> None:
        """Delete instance."""

    @abstractmethod
    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.
        """
