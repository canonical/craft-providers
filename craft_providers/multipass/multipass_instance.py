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

"""Multipass Instance."""
import io
import logging
import pathlib
import subprocess
from typing import Any, Dict, List, Optional

from craft_providers import errors
from craft_providers.util import env_cmd

from .. import Executor
from .errors import MultipassError
from .multipass import Multipass

logger = logging.getLogger(__name__)


def _rootify_multipass_command(
    command: List[str],
    *,
    cwd: Optional[pathlib.Path] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
) -> List[str]:
    """Wrap a command to run as root with specified environment.

    - Use sudo to run as root (Multipass defaults to ubuntu user).
    - Configure sudo to set home directory.
    - Account for environment flags in env, if any.

    :param command: Command to execute.
    :param env: Additional environment flags to set.

    :returns: List of command strings for multipass exec.
    """
    sudo_cmd = ["sudo", "-H", "--"]

    if env is not None or cwd is not None:
        sudo_cmd += env_cmd.formulate_command(env, chdir=cwd)

    return sudo_cmd + command


class MultipassInstance(Executor):
    """Multipass Instance Lifecycle.

    :param name: Name of multipass instance.
    """

    def __init__(
        self,
        *,
        name: str,
        multipass: Optional[Multipass] = None,
    ):
        super().__init__()

        self.name = name

        if multipass is not None:
            self._multipass = multipass
        else:
            self._multipass = Multipass()

    def push_file_io(
        self,
        *,
        destination: pathlib.PurePath,
        content: io.BytesIO,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        """Create or replace file with content and file mode.

        Multipass transfers data as "ubuntu" user, forcing us to first copy a
        file to a temporary location before moving to a (possibly) root-owned
        location and with appropriate permissions.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param group: File group owner/id.
        :param user: File user owner/id.
        """
        try:
            tmp_file_path = self._multipass.exec(
                instance_name=self.name,
                command=["mktemp"],
                runner=subprocess.run,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()

            self._multipass.transfer_source_io(
                source=content,
                destination=f"{self.name}:{tmp_file_path}",
            )

            self.execute_run(
                ["chown", f"{user}:{group}", tmp_file_path],
                capture_output=True,
                check=True,
            )

            self.execute_run(
                ["chmod", file_mode, tmp_file_path],
                capture_output=True,
                check=True,
            )

            self.execute_run(
                ["mv", tmp_file_path, destination.as_posix()],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=(
                    f"Failed to create file {destination.as_posix()!r}"
                    f" in {self.name!r} VM."
                ),
                details=errors.details_from_called_process_error(error),
            ) from error

    def delete(self) -> None:
        """Delete instance and purge."""
        return self._multipass.delete(
            instance_name=self.name,
            purge=True,
        )

    def execute_popen(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.Path] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Execute process in instance using subprocess.Popen().

        The process' environment will inherit the execution environment's
        default environment (PATH, etc.), but can be additionally configured via
        env parameter.

        :param command: Command to execute.
        :param env: Additional environment to set for process.
        :param kwargs: Additional keyword arguments for subprocess.Popen().

        :returns: Popen instance.
        """
        return self._multipass.exec(
            instance_name=self.name,
            command=_rootify_multipass_command(command, cwd=cwd, env=env),
            runner=subprocess.Popen,
            **kwargs,
        )

    def execute_run(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.Path] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute command using subprocess.run().

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
        return self._multipass.exec(
            instance_name=self.name,
            command=_rootify_multipass_command(command, cwd=cwd, env=env),
            runner=subprocess.run,
            **kwargs,
        )

    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.

        :raises MultipassError: On unexpected failure.
        """
        vm_list = self._multipass.list()

        return self.name in vm_list

    def _get_info(self) -> Dict[str, Any]:
        """Get configuration and state for instance.

        :returns: State information parsed from multipass if instance exists,
            else None.

        :raises MultipassError: If unable to parse VM info.
        """
        info_data = self._multipass.info(instance_name=self.name).get("info")

        if info_data is None or self.name not in info_data:
            raise MultipassError(
                brief="Malformed multipass info",
                details=f"Returned data: {info_data!r}",
            )

        return info_data[self.name]

    def is_mounted(
        self, *, host_source: pathlib.Path, target: pathlib.PurePath
    ) -> bool:
        """Check if path is mounted at target.

        :param host_source: Host path to check.
        :param target: Instance path to check.

        :returns: True if host_source is mounted at target.

        :raises MultipassError: On unexpected failure.
        """
        info = self._get_info()
        mounts = info.get("mounts", {})

        for mount_point, mount_config in mounts.items():
            # Even on Windows, Multipass writes source_path as posix, e.g.:
            # 'C:/Users/chris/tmpbat91bwz.tmp-pytest'
            if (
                mount_point == target.as_posix()
                and mount_config.get("source_path") == host_source.as_posix()
            ):
                return True

        return False

    def is_running(self) -> bool:
        """Check if instance is running.

        :returns: True if instance is running.

        :raises MultipassError: On unexpected failure.
        """
        info = self._get_info()

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

        :raises MultipassError: On unexpected failure.
        """
        self._multipass.launch(
            instance_name=self.name,
            image=image,
            cpus=str(cpus),
            disk=f"{disk_gb!s}G",
            mem=f"{mem_gb!s}G",
        )

    def mount(
        self,
        *,
        host_source: pathlib.Path,
        target: pathlib.PurePath,
    ) -> None:
        """Mount host host_source directory to target mount point.

        Checks first to see if already mounted.

        :param host_source: Host path to mount.
        :param target: Instance path to mount to.

        :raises MultipassError: On unexpected failure.
        """
        if self.is_mounted(host_source=host_source, target=target):
            return

        self._multipass.mount(
            source=host_source,
            target=f"{self.name}:{target.as_posix()}",
        )

    def pull_file(self, *, source: pathlib.PurePath, destination: pathlib.Path) -> None:
        """Copy a file from the environment to host.

        :param source: Environment file to copy.
        :param destination: Host file path to copy to.  Parent directory
            (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises MultipassError: On unexpected error copying file.
        """
        proc = self.execute_run(["test", "-f", source.as_posix()], check=False)
        if proc.returncode != 0:
            raise FileNotFoundError(f"File not found: {source.as_posix()!r}")

        if not destination.parent.is_dir():
            raise FileNotFoundError(f"Directory not found: {str(destination.parent)!r}")

        self._multipass.transfer(
            source=f"{self.name}:{source.as_posix()}", destination=str(destination)
        )

    def push_file(self, *, source: pathlib.Path, destination: pathlib.PurePath) -> None:
        """Copy a file from the host into the environment.

        :param source: Host file to copy.
        :param destination: Target environment file path to copy to.  Parent
            directory (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises MultipassError: On unexpected error copying file.
        """
        if not source.is_file():
            raise FileNotFoundError(f"File not found: {str(source)!r}")

        proc = self.execute_run(
            ["test", "-d", destination.parent.as_posix()], check=False
        )
        if proc.returncode != 0:
            raise FileNotFoundError(
                f"Directory not found: {str(destination.parent.as_posix())!r}"
            )

        self._multipass.transfer(
            source=str(source),
            destination=f"{self.name}:{destination.as_posix()}",
        )

    def start(self) -> None:
        """Start instance.

        :raises MultipassError: On unexpected failure.
        """
        self._multipass.start(instance_name=self.name)

    def stop(self, *, delay_mins: int = 0) -> None:
        """Stop instance.

        :param delay_mins: Delay shutdown for specified minutes.

        :raises MultipassError: On unexpected failure.
        """
        self._multipass.stop(instance_name=self.name, delay_mins=delay_mins)

    def unmount(self, target: pathlib.Path) -> None:
        """Unmount mount target shared with host.

        :param target: Target shared with host to unmount.

        :raises MultipassError: On failure to unmount target.
        """
        mount = f"{self.name}:{target.as_posix()}"

        self._multipass.umount(mount=mount)

    def unmount_all(self) -> None:
        """Unmount all mounts shared with host.

        :raises MultipassError: On failure to unmount target.
        """
        self._multipass.umount(mount=self.name)
