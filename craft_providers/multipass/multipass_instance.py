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

"""Multipass Instance."""
import io
import logging
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional

from craft_providers.actions import linux

from .. import Executor
from .multipass import Multipass

logger = logging.getLogger(__name__)


class MultipassInstanceError(Exception):
    """Unexpected error operating on VM.

    :param msg: Error description.
    """

    def __init__(self, msg: str) -> None:
        super().__init__()

        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class MultipassInstance(Executor):
    """Multipass Instance Lifecycle."""

    def __init__(
        self,
        *,
        name: str,
        multipass: Multipass,
        host_gid: int = os.getuid(),
        host_uid: int = os.getgid(),
        platform: str = sys.platform,
    ):
        super().__init__()

        self.name = name
        self._host_gid = host_gid
        self._host_uid = host_uid
        self._multipass = multipass
        self._platform = platform

    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: bytes,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        """Create file with content and file mode.

        Multipass transfers data as "ubuntu" user, forcing us to first copy a
        file to a temporary location before moving to a (possibly) root-owned
        location and with appropriate permissions.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param group: File group owner/id.
        :param user: Filer usedr owner/id.
        """
        stream = io.BytesIO(content)

        tmp_file_path = "/".join(["/tmp", destination.as_posix().replace("/", "_")])

        self._multipass.transfer_source_io(
            source=stream,
            destination=f"{self.name}:{tmp_file_path}",
        )

        self.execute_run(
            command=["sudo", "chown", f"{user}:{group}", tmp_file_path],
        )

        self.execute_run(
            command=["sudo", "chmod", file_mode, tmp_file_path],
        )

        self.execute_run(
            command=["sudo", "mv", tmp_file_path, destination.as_posix()],
        )

    def delete(self, purge: bool = True) -> None:
        """Delete instance.

        :param purge: Purge instances immediately.
        """
        return self._multipass.delete(
            instance_name=self.name,
            purge=purge,
        )

    def _formulate_command(self, command: List[str]) -> List[str]:
        return ["sudo", "-H", "--", *command]

    def execute_popen(self, command: List[str], **kwargs) -> subprocess.Popen:
        """Execute process in instance using subprocess.Popen().

        :param command: Command to execute.
        :param kwargs: Additional keyword arguments for subprocess.Popen().

        :returns: Popen instance.
        """
        return self._multipass.exec(
            instance_name=self.name,
            command=self._formulate_command(command),
            runner=subprocess.Popen,
            **kwargs,
        )

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
        return self._multipass.exec(
            instance_name=self.name,
            command=self._formulate_command(command),
            runner=subprocess.run,
            check=check,
            **kwargs,
        )

    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.
        """
        return self.get_info() is not None

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Get configuration and state for instance.

        :returns: State information parsed from multipass if instance exists,
            else None.

        :raises MultipassInstanceError: If unable to parse VM info.
        """
        instance_config = self._multipass.info(instance_name=self.name)
        if instance_config is None:
            return None

        return instance_config.get("info", dict()).get(self.name)

    def is_mounted(self, *, host_source: pathlib.Path, target: pathlib.Path) -> bool:
        """Check if path is mounted at target.

        :param host_source: Host path to check.
        :param target: Instance path to check.

        :returns: True if host_source is mounted at target.
        """
        info = self.get_info()
        if info is None:
            raise MultipassInstanceError(f"VM no longer exists {self.name!r}.")

        mounts = info.get("mounts", dict())

        for mount_point, mount_config in mounts.items():
            if mount_point == target.as_posix() and mount_config.get(
                "source_path"
            ) == str(host_source):
                return True

        return False

    def is_running(self) -> bool:
        """Check if instance is running.

        :returns: True if instance is running.
        """
        info = self.get_info()
        if info is None:
            return False

        return info.get("state") == "Running"

    def launch(
        self,
        *,
        image: str,
        cpus: int = 2,
        disk_gb: int = 256,
        mem_gb: int = 2,
    ) -> None:
        """Launch instance.

        :param image: Name of image to create the instance with.
        :param instance_cpus: Number of CPUs.
        :param instance_disk_gb: Disk allocation in gigabytes.
        :param instance_mem_gb: Memory allocation in gigabytes.
        :param instance_name: Name of instance to use/create.
        :param instance_stop_time_mins: Stop time delay in minutes.
        """
        self._multipass.launch(
            instance_name=self.name,
            image=image,
            cpus=str(cpus),
            disk=f"{disk_gb!s}G",
            mem=f"{mem_gb!s}G",
        )

    def mount(self, *, host_source: pathlib.Path, target: pathlib.Path) -> None:
        """Mount host host_source directory to target mount point.

        Checks first to see if already mounted.

        :param host_source: Host path to mount.
        :param target: Instance path to mount to.
        """
        if self.is_mounted(host_source=host_source, target=target):
            return

        if self._platform == "win32":
            uid_map = {"0": "0"}
            gid_map = {"0": "0"}
        else:
            uid_map = {str(self._host_uid): "0"}
            gid_map = {str(self._host_gid): "0"}

        self._multipass.mount(
            source=host_source,
            target=f"{self.name}:{target.as_posix()}",
            uid_map=uid_map,
            gid_map=gid_map,
        )

    def pull(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy source file/directory from environment to host destination.

        Standard "cp -r" rules apply:

            - if source is directory, copy happens recursively.

            - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Target directory to copy from.
        :param destination: Host destination directory to copy to.

        :raises FileNotFoundError: If source does not exist.
        """
        logger.info("Syncing env:%s -> host:%s...", source, destination)

        # TODO: check if mount makes source == destination, skip if so.
        if linux.is_target_file(executor=self, target=source):
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._multipass.transfer(
                source=f"{self.name}:{source!s}", destination=str(destination)
            )
        elif linux.is_target_directory(executor=self, target=source):
            linux.directory_sync_from_remote(
                executor=self, source=source, destination=destination
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def push(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy host source file/directory into environment at destination.

        Standard "cp -r" rules apply:
        - if source is directory, copy happens recursively.
        - if destination exists, source will be copied into destination.

        Providing this as an abstract method allows the provider to implement
        the most performant option available.

        :param source: Host directory to copy.
        :param destination: Target destination directory to copy to.

        :raises FileNotFoundError: If source does not exist.
        """
        # TODO: check if mounted, skip sync if source == destination
        logger.info("Syncing host:%s -> env:%s...", source, destination)
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._multipass.transfer(
                source=str(source),
                destination=f"{self.name}:{destination!s}",
            )
        elif source.is_dir():
            # TODO: use mount() if available
            linux.directory_sync_to_remote(
                executor=self, source=source, destination=destination, delete=True
            )
        else:
            raise FileNotFoundError(f"Source {source} not found.")

    def start(self) -> None:
        """Start instance."""
        self._multipass.start(instance_name=self.name)

    def stop(self, delay_mins: int = 0) -> None:
        """Stop instance."""
        self._multipass.stop(instance_name=self.name, delay_mins=delay_mins)

    def supports_mount(self) -> bool:
        """Check if instance supports mounting from host.

        :returns: True if mount is supported.
        """
        return True
