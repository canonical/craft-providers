"""LXD Instance."""
import logging
import os
import pathlib
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from .. import Executor
from .lxc import LXC

logger = logging.getLogger(__name__)


class LXDInstance(Executor):
    """LXD Instance Lifecycle."""

    def __init__(
        self,
        *,
        name: str,
        project: str = "default",
        remote: str = "local",
        lxc: Optional[LXC] = None,
    ):
        super().__init__()

        self.name = name
        self.project = project
        self.remote = remote
        if lxc is None:
            self.lxc = LXC()
        else:
            self.lxc = lxc

    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: bytes,
        file_mode: str,
        gid: int = 0,
        uid: int = 0,
    ) -> None:
        """Create file with content and file mode.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param gid: File owner group ID.
        :param uid: Filer owner user ID.
        """
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(content)
            temp_file.flush()

        self.lxc.file_push(
            instance=self.name,
            source=pathlib.Path(temp_file.name),
            destination=destination,
            mode=file_mode,
            gid=str(gid),
            uid=str(uid),
            project=self.project,
            remote=self.remote,
        )

        os.unlink(temp_file.name)

    def delete(self, force: bool = True) -> None:
        """Delete instance.

        :param force: Delete even if running.
        """
        return self.lxc.delete(
            instance=self.name,
            project=self.project,
            remote=self.remote,
            force=force,
        )

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute process in instance using subprocess.Popen().

        :param command: Command to execute.
        :param kwargs: Additional keyword arguments for subprocess.Popen().

        :returns: Popen instance.
        """
        return self.lxc.exec(
            instance=self.name,
            command=command,
            project=self.project,
            remote=self.remote,
            runner=subprocess.Popen,
            **kwargs,
        )

    def execute_run(
        self, command: List[str], check=True, **kwargs
    ) -> subprocess.CompletedProcess:
        """Execute process in instance using subprocess.run().

        :param command: Command to execute.
        :param kwargs: Additional keyword arguments for subprocess.run().

        :returns: CompletedProcess instance returned from subprocess.run().
        """
        return self.lxc.exec(
            instance=self.name,
            command=command,
            project=self.project,
            remote=self.remote,
            runner=subprocess.run,
            check=check,
            **kwargs,
        )

    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.
        """
        return self.get_state() is not None

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get state configuration for instance.

        :returns: State information parsed from lxc if instance exists, else
                  None.
        """
        instances = self.lxc.list(
            instance=self.name, project=self.project, remote=self.remote
        )

        # lxc returns a filter instances starting with instance name rather
        # than the exact instance.  Find the exact match...
        for instance in instances:
            if instance["name"] == self.name:
                return instance

        return None

    def is_mounted(self, *, source: pathlib.Path, destination: pathlib.Path) -> bool:
        """Check if path is mounted at target.

        :param source: Host path to check.
        :param destination: Instance path to check.

        :returns: True if source is mounted at destination.
        """

        devices = self.lxc.config_device_show(
            instance=self.name, project=self.project, remote=self.remote
        )
        disks = [d for d in devices.values() if d.get("type") == "disk"]

        return any(
            disk.get("path") == destination.as_posix()
            and disk.get("source") == source.as_posix()
            for disk in disks
        )

    def is_running(self) -> bool:
        """Check if instance is running.

        :returns: True if instance is running.
        """
        state = self.get_state()
        if state is None:
            return False

        return state.get("status") == "Running"

    def launch(
        self,
        *,
        image: str,
        image_remote: str,
        uid: str = str(os.getuid()),
        ephemeral: bool = True,
    ) -> None:
        """Launch instance.

        :param image: Image name to launch.
        :param image_remote: Image remote name.
        :param uid: Host user ID to map to instance root.
        :param ephemeral: Flag to enable ephemeral instance.
        """
        config_keys = dict()
        config_keys["raw.idmap"] = f"both {uid!s} 0"

        if self._host_supports_mknod():
            config_keys["security.syscalls.intercept.mknod"] = "true"

        self.lxc.launch(
            config_keys=config_keys,
            ephemeral=ephemeral,
            instance=self.name,
            image=image,
            image_remote=image_remote,
            project=self.project,
            remote=self.remote,
        )

    def mount(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Mount host source directory to target mount point.

        Checks first to see if already mounted.

        :param source: Host path to mount.
        :param destination: Instance path to mount to.
        """
        if self.is_mounted(source=source, destination=destination):
            return

        self.lxc.config_device_add_disk(
            instance=self.name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
        )

    def _host_supports_mknod(self) -> bool:
        """Check if host supports mknod in container.

        See: https://linuxcontainers.org/lxd/docs/master/syscall-interception

        :returns: True if mknod is supported.
        """
        cfg = self.lxc.info(project=self.project, remote=self.remote)
        env = cfg.get("environment", dict())
        kernel_features = env.get("kernel_features", dict())
        seccomp_listener = kernel_features.get("seccomp_listener", "false")

        return seccomp_listener == "true"

    def start(self) -> None:
        """Start instance."""
        self.lxc.start(instance=self.name, project=self.project, remote=self.remote)

    def stop(self) -> None:
        """Stop instance."""
        self.lxc.stop(instance=self.name, project=self.project, remote=self.remote)

    def supports_mount(self) -> bool:
        """Check if instance supports mounting from host.

        :returns: True if mount is supported.
        """
        return self.remote == "local"

    def sync_from(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Sync contents from instance to host.

        :param source: Path to copy from instance.
        :param destination: Path on host to copy to.
        """
        logger.info("Syncing env:%s -> host:%s...", source, destination)
        # TODO: check if mount makes source == destination, skip if so.
        if self.is_target_file(source):
            self.lxc.file_pull(
                instance=self.name,
                source=source,
                destination=destination,
                project=self.project,
                remote=self.remote,
                create_dirs=True,
            )
        elif self.is_target_directory(target=source):
            self.lxc.file_pull(
                instance=self.name,
                source=source,
                destination=destination,
                project=self.project,
                remote=self.remote,
                create_dirs=True,
                recursive=True,
            )
            # TODO: use mount() if available
            self.naive_directory_sync_from(source=source, destination=destination)
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def sync_to(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Sync contents from host to instance.

        :param source: Path on host to copy from.
        :param destination: Path in instance to copy to.
        """
        # TODO: check if mounted, skip sync if source == destination
        logger.info("Syncing host:%s -> env:%s...", source, destination)
        if source.is_file():
            self.lxc.file_push(
                instance=self.name,
                source=source,
                destination=destination,
                project=self.project,
                remote=self.remote,
            )
        elif source.is_dir():
            # TODO: use mount() if available
            self.naive_directory_sync_to(
                source=source, destination=destination, delete=True
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")
