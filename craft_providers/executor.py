"""Executor module."""
import logging
import pathlib
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import List

from .util import path

logger = logging.getLogger(__name__)


class Executor(ABC):
    """Interfaces to execute commands and move data in/out of an environment."""

    def __init__(self, *, tar_path: pathlib.Path = None) -> None:
        if tar_path is None:
            self.tar_path = path.which_required("tar")
        else:
            self.tar_path = tar_path

    @abstractmethod
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
        ...

    @abstractmethod
    def execute_run(
        self, command: List[str], check=True, **kwargs
    ) -> subprocess.CompletedProcess:
        """Execute command in instance, using subprocess.run().

        If `env` is in kwargs, it will be applied to the target runtime
        environment, not the host's.

        :param command: Command to execute.
        :param check: Check flag to subprocess.run(), except defaults to True.
        :param kwargs: Additional keyword arguments to pass.

        :returns: Completed process.
        """
        ...

    @abstractmethod
    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute command in instance, using subprocess.Popen().

        If `env` is in kwargs, it will be applied to the target runtime
        environment, not the host's.

        :param command: Command to execute.
        :param kwargs: Additional keyword arguments to pass.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    def is_target_directory(self, target: pathlib.Path) -> bool:
        """Check if path is directory.

        :param target: Path to check.

        :returns: True if directory, False otherwise.
        """
        proc = self.execute_run(command=["test", "-d", target.as_posix()])
        return proc.returncode == 0

    def is_target_file(self, target: pathlib.Path) -> bool:
        """Check if path is file.

        :param target: Path to check.

        :returns: True if file, False otherwise.
        """
        proc = self.execute_run(command=["test", "-f", target.as_posix()])
        return proc.returncode == 0

    def naive_directory_sync_from(
        self, *, source: pathlib.Path, destination: pathlib.Path
    ) -> None:
        """Naive sync from remote using tarball.

        Relies on only the required Self.interfaces.

        :param source: Target directory to copy from.
        :param destination: Host destination directory to copy to.
        """
        destination_path = destination.as_posix()

        if destination.exists():
            shutil.rmtree(destination)

        destination.mkdir(parents=True)

        archive_proc = self.execute_popen(
            ["tar", "cpf", "-", "-C", source.as_posix(), "."],
            stdout=subprocess.PIPE,
        )

        target_proc = subprocess.Popen(
            [str(self.tar_path), "xpvf", "-", "-C", destination_path],
            stdin=archive_proc.stdout,
        )

        # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
        if archive_proc.stdout:
            archive_proc.stdout.close()

        # Waot until done.
        target_proc.communicate()

    def naive_directory_sync_to(
        self, *, source: pathlib.Path, destination: pathlib.Path, delete=True
    ) -> None:
        """Naive sync to remote using tarball.

        :param source: Host directory to copy.
        :param destination: Target destination directory to copy to.
        :param delete: Flag to delete existing destination, if exists.
        """
        destination_path = destination.as_posix()

        if delete is True:
            self.execute_run(["rm", "-rf", destination_path], check=True)

        self.execute_run(["mkdir", "-p", destination_path], check=True)

        archive_proc = subprocess.Popen(
            [self.tar_path, "cpf", "-", "-C", str(source), "."],
            stdout=subprocess.PIPE,
        )

        target_proc = self.execute_popen(
            ["tar", "xpvf", "-", "-C", destination_path],
            stdin=archive_proc.stdout,
        )

        # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
        if archive_proc.stdout:
            archive_proc.stdout.close()

        # Waot until done.
        target_proc.communicate()
