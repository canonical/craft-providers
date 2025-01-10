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

"""Executor module."""

import contextlib
import hashlib
import io
import logging
import pathlib
import re
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional

import craft_providers.util.temp_paths
from craft_providers.errors import ProviderError

logger = logging.getLogger(__name__)


class Executor(ABC):
    """Interfaces to execute commands and move data in/out of an environment."""

    @abstractmethod
    def execute_popen(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.PurePath] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Execute a command in instance, using subprocess.Popen().

        The process' environment will inherit the execution environment's
        default environment (PATH, etc.), but can be additionally configured via
        env parameter.

        :param command: Command to execute.
        :param cwd: Working directory for the process inside the instance.
        :param env: Additional environment to set for process.
        :param timeout: Timeout (in seconds) for the command.
        :param kwargs: Additional keyword arguments to pass.

        :returns: Popen instance.
        """

    @abstractmethod
    def execute_run(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.PurePath] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        timeout: Optional[float] = None,
        check: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute a command using subprocess.run().

        The process' environment will inherit the execution environment's
        default environment (PATH, etc.), but can be additionally configured via
        env parameter.

        :param command: Command to execute.
        :param cwd: Working directory for the process inside the instance.
        :param env: Additional environment to set for process.
        :param timeout: Timeout (in seconds) for the command.
        :param check: Raise an exception if the command fails.
        :param kwargs: Keyword args to pass to subprocess.run().

        :returns: Completed process.

        :raises subprocess.CalledProcessError: if command fails and check is True.
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
        self, *, source: pathlib.PurePath, missing_ok: bool = False
    ) -> Generator[Optional[pathlib.Path], None, None]:
        """Copy a file from the environment to a temporary file in the host.

        This is mainly a layer above `pull_file` that pulls the file into a
        temporary path which is cleaned later.

        Works as a context manager, provides the file path in the host as target.

        The temporary file is stored in the home directory where Multipass has access.

        :param source: Environment file to copy.
        :param missing_ok: Do not raise an error if the file does not exist in the
            environment; in this case the target will be None.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist (and `missing_ok` is False).
        :raises ProviderError: On error copying file content.
        """
        with craft_providers.util.temp_paths.home_temporary_file() as tmp_file:
            try:
                self.pull_file(source=source, destination=tmp_file)
            except FileNotFoundError:
                if missing_ok:
                    yield None
                else:
                    raise
            else:
                yield tmp_file

    @abstractmethod
    def push_file(self, *, source: pathlib.Path, destination: pathlib.PurePath) -> None:
        """Copy a file from the host into the environment.

        The destination file is overwritten if it exists.

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

    @abstractmethod
    def mount(self, *, host_source: pathlib.Path, target: pathlib.PurePath) -> None:
        """Mount host source directory to target mount point."""

    @abstractmethod
    def is_running(self) -> bool:
        """Check if instance is running.

        :returns: True if instance is running.
        """


def get_instance_name(name: str, error_class: type[ProviderError]) -> str:
    """Get an instance-friendly name from a name.

    LXD and Multipass instance names have the same naming convention
    as Linux hostnames.

    Naming convention:
    - between 1 and 63 characters long
    - made up exclusively of letters, numbers, and hyphens from the ASCII table
    - not begin with a digit or a hyphen
    - not end with a hyphen

    To create an instance name, invalid characters are removed, the name is
    truncated to 40 characters, then a hash is appended:
    <truncated-name>-<hash-of-name>
    └     1 - 40   ┘1└     20     ┘

    :param name: the name to convert
    :param error_class: the exception class to raise if name is invalid

    :raises error_class: if name contains no alphanumeric characters
    :returns: the instance name
    """
    # remove anything that is not an alphanumeric character or hyphen
    name_with_valid_chars = re.sub(r"[^\w-]", "", name, flags=re.ASCII)
    if not name_with_valid_chars:
        raise error_class(
            brief=f"failed to create an instance with name {name!r}.",
            details="name must contain at least one alphanumeric character",
        )

    # trim digits and hyphens from the beginning and hyphens from the end
    trimmed_name = re.compile(r"^[0-9-]*(?P<valid_name>.*?)[-]*$").search(
        name_with_valid_chars
    )
    if not trimmed_name or not trimmed_name.group("valid_name"):
        raise error_class(
            brief=f"failed to create an instance with name {name!r}.",
            details="name must contain at least one alphanumeric character",
        )
    valid_name = trimmed_name.group("valid_name")

    # if the original name satisfies the naming convention, then use the original name
    if name == valid_name and len(name) <= 63:
        instance_name = name

    # else, continue converting the name
    else:
        # truncate to 40 characters
        truncated_name = valid_name[:40]
        # hash the entire name, not the truncated name
        hashed_name = hashlib.sha1(name.encode()).hexdigest()[:20]
        instance_name = f"{truncated_name}-{hashed_name}"

    logger.debug("Converted name %r to instance name %r", name, instance_name)
    return instance_name
