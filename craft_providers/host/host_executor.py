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

    Attributes:
        sudo_user: Optional sudo user to run commands with.
          sudo will not be used if None.
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

        Arguments:
          command: Command to execute.
        """
        command = self._prepare_execute_args(command=command)
        return subprocess.run(command, check=check, **kwargs)

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute command using Popen().

        Arguments:
          command: Command to execute.
        """
        command = self._prepare_execute_args(command=command)
        return subprocess.Popen(command, **kwargs)

    def mount(  # pylint: disable=unused-argument
        self, *, source: pathlib.Path, destination: pathlib.Path
    ) -> bool:
        """Not applicable for host provider."""
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

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        if source.is_file():
            shutil.copy2(source, destination)
        elif source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        if source.is_file():
            shutil.copy2(source, destination)
        elif source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"Source {source} not found.")
