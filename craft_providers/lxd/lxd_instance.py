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

"""LXD Instance Executor."""

import io
import logging
import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from craft_providers import errors
from craft_providers.util import env_cmd

from .. import Executor
from .errors import LXDError
from .lxc import LXC

logger = logging.getLogger(__name__)


class LXDInstance(Executor):
    """LXD Instance Lifecycle."""

    def __init__(
        self,
        *,
        name: str,
        default_command_environment: Optional[Dict[str, Optional[str]]] = None,
        project: str = "default",
        remote: str = "local",
        lxc: Optional[LXC] = None,
    ):
        super().__init__()

        if default_command_environment is not None:
            self.default_command_environment = default_command_environment
        else:
            self.default_command_environment = {}

        self.name = name
        self.project = project
        self.remote = remote

        if lxc is None:
            self.lxc = LXC()
        else:
            self.lxc = lxc

    def _finalize_lxc_command(
        self,
        command: List[str],
        *,
        env: Optional[Dict[str, Optional[str]]] = None,
    ) -> List[str]:
        """Wrap a command to run as root with specified environment.

        LXD will run commands as root.

        Account for the command environment by using the default command
        environment as the baseline, updating it to reflect the command's env
        parameter, if any.

        :param command: Command to execute.
        :param env: Additional environment flags to set/unset.

        :returns: List of command strings for multipass exec.
        """
        command_env = self.default_command_environment.copy()

        if env:
            command_env.update(env)

        if command_env:
            return env_cmd.formulate_command(command_env) + command

        return command

    def push_file_io(
        self,
        *,
        destination: pathlib.Path,
        content: io.BytesIO,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        """Create file with content and file mode.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param group: File group owner/id.
        :param user: File user owner/id.

        :raises LXDError: On unexpected error.
        """
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            shutil.copyfileobj(content, temp_file)

        temp_path = pathlib.Path(temp_file.name)
        self.lxc.file_push(
            instance_name=self.name,
            source=temp_path,
            destination=destination,
            mode=file_mode,
            project=self.project,
            remote=self.remote,
        )

        # We don't use gid/uid for file_push() in case we don't know the
        # user/group IDs in advance.  Just chown it.
        try:
            self.execute_run(
                ["chown", f"{user}:{group}", destination.as_posix()],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to create file {destination.as_posix()!r} in instance {self.name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        os.unlink(temp_file.name)

    def delete(self, force: bool = True) -> None:
        """Delete instance.

        :param force: Delete even if running.

        :raises LXDError: On unexpected error.
        """
        return self.lxc.delete(
            instance_name=self.name,
            project=self.project,
            remote=self.remote,
            force=force,
        )

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
        if cwd is None:
            cwd_path = None
        else:
            cwd_path = cwd.as_posix()

        return self.lxc.exec(
            instance_name=self.name,
            command=self._finalize_lxc_command(command=command, env=env),
            project=self.project,
            remote=self.remote,
            runner=subprocess.Popen,
            cwd=cwd_path,
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
        if cwd is None:
            cwd_path = None
        else:
            cwd_path = cwd.as_posix()

        return self.lxc.exec(
            instance_name=self.name,
            command=self._finalize_lxc_command(command=command, env=env),
            project=self.project,
            remote=self.remote,
            runner=subprocess.run,
            cwd=cwd_path,
            **kwargs,
        )

    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.

        :raises LXDError: On unexpected error.
        """
        return self._get_state() is not None

    def _get_disk_devices(self) -> Dict[str, Any]:
        """Query instance and return dictionary of disk devices."""
        devices = self.lxc.config_device_show(
            instance_name=self.name, project=self.project, remote=self.remote
        )

        disks = {}
        for name, config in devices.items():
            if config.get("type") == "disk":
                disks[name] = config

                # Ensure the expected keys are in config.
                if "path" not in config or "source" not in config:
                    raise LXDError(
                        brief=f"Failed to parse lxc device {name!r}.",
                        details=f"* Device configuration: {devices!r}",
                    )

        return disks

    def _get_state(self) -> Optional[Dict[str, Any]]:
        """Get state configuration for instance.

        :returns: State information parsed from lxc if instance exists, else
                  None.

        :raises LXDError: On unexpected error.
        """
        instances = self.lxc.list(project=self.project, remote=self.remote)

        for instance in instances:
            if instance["name"] == self.name:
                return instance

        return None

    def is_mounted(self, *, host_source: pathlib.Path, target: pathlib.Path) -> bool:
        """Check if path is mounted at target.

        :param host_source: Host path to check.
        :param target: Instance path to check.

        :returns: True if host_source is mounted at target.

        :raises LXDError: On unexpected error.
        """
        disks = self._get_disk_devices()

        return any(
            disk["path"] == target.as_posix()
            and disk["source"] == host_source.as_posix()
            for _, disk in disks.items()
        )

    def is_running(self) -> bool:
        """Check if instance is running.

        :returns: True if instance is running.

        :raises LXDError: On unexpected error.
        """
        state = self._get_state()
        if state is None:
            raise LXDError(brief=f"Instance {self.name!r} does not exist.")

        return state.get("status") == "Running"

    def launch(
        self,
        *,
        image: str,
        image_remote: str,
        map_user_uid: bool = False,
        ephemeral: bool = False,
    ) -> None:
        """Launch instance.

        :param image: Image name to launch.
        :param image_remote: Image remote name.
        :param uid: Host user ID to map to instance root.
        :param ephemeral: Flag to enable ephemeral instance.

        :raises LXDError: On unexpected error.
        """
        config_keys = dict()

        if map_user_uid:
            uid = os.getuid()
            config_keys["raw.idmap"] = f"both {uid!s} 0"

        if self._host_supports_mknod():
            config_keys["security.syscalls.intercept.mknod"] = "true"

        self.lxc.launch(
            config_keys=config_keys,
            ephemeral=ephemeral,
            instance_name=self.name,
            image=image,
            image_remote=image_remote,
            project=self.project,
            remote=self.remote,
        )

    def mount(
        self,
        *,
        host_source: pathlib.Path,
        target: pathlib.Path,
        device_name: Optional[str] = None,
    ) -> None:
        """Mount host source directory to target mount point.

        Checks first to see if already mounted.  If no device name is given, it
        will be generated with the format "disk-{target.as_posix()}".

        :param host_source: Host path to mount.
        :param target: Instance path to mount to.
        :param device_name: Name for disk device.

        :raises LXDError: On unexpected error.
        """
        if self.is_mounted(host_source=host_source, target=target):
            return

        if device_name is None:
            device_name = "disk-" + target.as_posix()

        self.lxc.config_device_add_disk(
            instance_name=self.name,
            source=host_source,
            path=target,
            device=device_name,
            project=self.project,
            remote=self.remote,
        )

    def _host_supports_mknod(self) -> bool:
        """Check if host supports mknod in container.

        See: https://linuxcontainers.org/lxd/docs/master/syscall-interception

        :returns: True if mknod is supported.

        :raises LXDError: On unexpected error.
        """
        cfg = self.lxc.info(project=self.project, remote=self.remote)
        env = cfg.get("environment", dict())
        kernel_features = env.get("kernel_features", dict())
        seccomp_listener = kernel_features.get("seccomp_listener", "false")

        return seccomp_listener == "true"

    def pull_file(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy a file from the environment to host.

        :param source: Environment file to copy.
        :param destination: Host file path to copy to.  Parent directory
            (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises LXDError: On unexpected error copying file.
        """
        proc = self.execute_run(["test", "-f", source.as_posix()], check=False)
        if proc.returncode != 0:
            raise FileNotFoundError(f"File not found: {source.as_posix()!r}")

        if not destination.parent.is_dir():
            raise FileNotFoundError(f"Directory not found: {str(destination.parent)!r}")

        self.lxc.file_pull(
            instance_name=self.name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
        )

    def push_file(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        """Copy a file from the host into the environment.

        :param source: Host file to copy.
        :param destination: Target environment file path to copy to.  Parent
            directory (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises LXDError: On unexpected error copying file.
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

        # Copy into target with uid/gid 0, rather than copying the IDs from the
        # host file.
        self.lxc.file_push(
            instance_name=self.name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
            gid=0,
            uid=0,
        )

    def start(self) -> None:
        """Start instance.

        :raises LXDError: on unexpected error.
        """
        self.lxc.start(
            instance_name=self.name, project=self.project, remote=self.remote
        )

    def stop(self) -> None:
        """Stop instance.

        :raises LXDError: on unexpected error.
        """
        self.lxc.stop(instance_name=self.name, project=self.project, remote=self.remote)

    def supports_mount(self) -> bool:
        """Check if instance supports mounting from host.

        :returns: True if mount is supported.
        """
        return self.remote == "local"

    def unmount(self, target: pathlib.Path) -> None:
        """Unmount mount target shared with host.

        :param target: Target shared with host to unmount.

        :raises LXDError: On failure to unmount target.
        """
        disks = self._get_disk_devices()

        unmounted = False
        for name, config in disks.items():
            if config["path"] == target.as_posix():
                self.lxc.config_device_remove(
                    instance_name=self.name,
                    device=name,
                    project=self.project,
                    remote=self.remote,
                )
                unmounted = True

        if not unmounted:
            raise LXDError(
                brief=f"Failed to unmount {target.as_posix()!r} in instance {self.name!r} - no such disk.",
                details=f"* Disk device configuration: {disks!r}",
            )

    def unmount_all(self) -> None:
        """Unmount all mounts shared with host.

        :raises LXDError: On failure to unmount target.
        """
        disks = self._get_disk_devices()

        for name, _ in disks.items():
            self.lxc.config_device_remove(
                instance_name=self.name,
                device=name,
                project=self.project,
                remote=self.remote,
            )
