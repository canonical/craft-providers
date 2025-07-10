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

"""LXD Instance Executor."""

import io
import logging
import os
import pathlib
import shutil
import subprocess
import tempfile
import warnings
from typing import Any

from craft_providers.const import RETRY_WAIT, TIMEOUT_SIMPLE
from craft_providers.errors import details_from_called_process_error
from craft_providers.executor import Executor, get_instance_name
from craft_providers.lxd.errors import LXDError
from craft_providers.lxd.lxc import LXC
from craft_providers.lxd.lxd_instance_status import (
    LXDInstanceState,
    ProviderInstanceStatus,
)
from craft_providers.util import env_cmd, retry

logger = logging.getLogger(__name__)


class LXDInstance(Executor):
    """Wrapper for a LXD Instance.

    :ivar name: The provided name for the instance.
    :ivar instance_name: The normalized name actually used for the instance.
    :ivar project: The name of the LXD project.
    :ivar remote: The name of the LXD remote.
    :ivar lxc: The LXC wrapper to use.
    """

    def __init__(
        self,
        *,
        name: str,
        default_command_environment: dict[str, str | None] | None = None,
        project: str = "default",
        remote: str = "local",
        lxc: LXC | None = None,
        intercept_mknod: bool = True,
    ) -> None:
        """Create an LXD executor.

        To comply with LXD naming conventions, the supplied name is converted to a
        LXD-compatible name before creating the instance.

        :param name: The name of the LXDInstance.
        :param default_command_environment: The command environment.
        :param project: The name of the LXD project.
        :param remote: The name of the LXD remote.
        :param lxc: The LXC wrapper to use.
        :param intercept_mknod: If the host can, tell LXD instance to intercept mknod

        :raises LXDError: If the name is invalid.
        """
        super().__init__()

        if default_command_environment is not None:
            self.default_command_environment = default_command_environment
        else:
            self.default_command_environment = {}

        self.name = name
        self.instance_name = get_instance_name(name, LXDError)
        self.project = project
        self.remote = remote
        self._intercept_mknod = intercept_mknod

        if lxc is None:
            self.lxc = LXC()
        else:
            self.lxc = lxc

    def _finalize_lxc_command(
        self,
        command: list[str],
        *,
        env: dict[str, str | None] | None = None,
    ) -> list[str]:
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
        destination: pathlib.PurePath,
        content: io.BytesIO,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        """Create or replace file with content and file mode.

        :param destination: Path to file.
        :param content: Contents of file.
        :param file_mode: File mode string (e.g. '0644').
        :param group: File group owner/id.
        :param user: File user owner/id.

        :raises LXDError: On unexpected error.
        """
        with tempfile.NamedTemporaryFile() as temp_file:
            shutil.copyfileobj(content, temp_file)  # type: ignore # mypy #15031
            # Ensure the file is written to disk.
            temp_file.flush()

            temp_path = pathlib.Path(temp_file.name)
            self.lxc.file_push(
                instance_name=self.instance_name,
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
                    timeout=TIMEOUT_SIMPLE,
                )
            except subprocess.CalledProcessError as error:
                raise LXDError(
                    brief=(
                        f"Failed to create file {destination.as_posix()!r}"
                        f" in instance {self.instance_name!r}."
                    ),
                    details=details_from_called_process_error(error),
                ) from error

    def delete(self, force: bool = True) -> None:
        """Delete instance.

        :param force: Delete even if running.

        :raises LXDError: On unexpected error.
        """
        return self.lxc.delete(
            instance_name=self.instance_name,
            project=self.project,
            remote=self.remote,
            force=force,
        )

    def execute_popen(
        self,
        command: list[str],
        *,
        cwd: pathlib.PurePath | None = None,
        env: dict[str, str | None] | None = None,
        timeout: float | None = None,
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
        cwd_path = None if cwd is None else cwd.as_posix()

        return self.lxc.exec(
            instance_name=self.instance_name,
            command=self._finalize_lxc_command(command=command, env=env),
            project=self.project,
            remote=self.remote,
            runner=subprocess.Popen,
            timeout=timeout,
            cwd=cwd_path,
            **kwargs,
        )

    def execute_run(
        self,
        command: list[str],
        *,
        cwd: pathlib.PurePath | None = None,
        env: dict[str, str | None] | None = None,
        timeout: float | None = None,
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

        :raises subprocess.CalledProcessError: if command fails and check is
            True.
        """
        cwd_path = None if cwd is None else cwd.as_posix()

        return self.lxc.exec(
            instance_name=self.instance_name,
            command=self._finalize_lxc_command(command=command, env=env),
            project=self.project,
            remote=self.remote,
            runner=subprocess.run,
            timeout=timeout,
            cwd=cwd_path,
            check=check,
            **kwargs,
        )

    def exists(self) -> bool:
        """Check if instance exists.

        :returns: True if instance exists.

        :raises LXDError: On unexpected error.
        """
        return self._get_instance_information() is not None

    def _get_disk_devices(self) -> dict[str, Any]:
        """Query instance and return dictionary of disk devices."""
        devices = self.lxc.config_device_show(
            instance_name=self.instance_name, project=self.project, remote=self.remote
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

    def _get_instance_information(self) -> dict[str, Any] | None:
        """Get information for a LXD instance.

        :returns: A dictionary of all information for an instance, including the
            instance's profile, devices, configuration, and status.

        :raises LXDError: On unexpected error.
        """
        instances = self.lxc.list(project=self.project, remote=self.remote)

        for instance in instances:
            if instance["name"] == self.instance_name:
                return instance

        return None

    def _get_state(self) -> LXDInstanceState:
        """Get the state of an instance.

        :raises LXDError: If the instance does not exist or has no state.
        """
        info = self._get_instance_information()
        if info is None:
            raise LXDError(brief=f"Instance {self.instance_name!r} does not exist.")

        if state := info.get("status"):
            return LXDInstanceState(state.upper())

        raise LXDError(
            brief=f"Instance {self.instance_name!r} has no state.",
            details=f"Instance information: {info!r}",
        )

    def is_mounted(
        self, *, host_source: pathlib.Path, target: pathlib.PurePath
    ) -> bool:
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

        :raises LXDError: If the instance doesn't exist or has no state.
        """
        return self._get_state() == LXDInstanceState.RUNNING

    def launch(
        self,
        *,
        image: str,
        image_remote: str,
        map_user_uid: bool = False,
        ephemeral: bool = False,
        uid: int | None = None,
    ) -> None:
        """Launch instance.

        :param image: Image name to launch.
        :param image_remote: Image remote name.
        :param map_user_uid: Whether id mapping should be used.
        :param uid: If ``map_user_uid`` is True,
                    the host user ID to map to instance root.
        :param ephemeral: Flag to enable ephemeral instance.

        :raises LXDError: On unexpected error.
        """
        config_keys = {}

        if map_user_uid:
            if not uid:
                uid = os.getuid()
            config_keys["raw.idmap"] = f"both {uid!s} 0"

        if self._intercept_mknod:
            if not self._host_supports_mknod():
                warnings.warn(
                    "Application configured to intercept guest mknod calls, "
                    "but the host OS does not support intercepting mknod."
                )
            else:
                config_keys["security.syscalls.intercept.mknod"] = "true"

        self.lxc.launch(
            config_keys=config_keys,
            ephemeral=ephemeral,
            instance_name=self.instance_name,
            image=image,
            image_remote=image_remote,
            project=self.project,
            remote=self.remote,
        )

    def mount(self, *, host_source: pathlib.Path, target: pathlib.PurePath) -> None:
        """Mount host source directory to target mount point.

        Checks first to see if already mounted.
        The source will be mounted as a disk named "disk-{target.as_posix()}".

        :param host_source: Host path to mount.
        :param target: Instance path to mount to.

        :raises LXDError: On unexpected error.
        """
        if self.is_mounted(host_source=host_source, target=target):
            return

        self.lxc.config_device_add_disk(
            instance_name=self.instance_name,
            source=host_source,
            path=target,
            device=f"disk-{target.as_posix()}",
            project=self.project,
            remote=self.remote,
        )

    def _host_supports_mknod(self) -> bool:
        """Check if host supports mknod in container.

        See: https://documentation.ubuntu.com/lxd/en/latest/syscall-interception/

        :returns: True if mknod is supported.

        :raises LXDError: On unexpected error.
        """
        cfg = self.lxc.info(project=self.project, remote=self.remote)
        env = cfg.get("environment", {})
        kernel_features = env.get("kernel_features", {})
        seccomp_listener = kernel_features.get("seccomp_listener", "false")

        return seccomp_listener == "true"

    def pull_file(self, *, source: pathlib.PurePath, destination: pathlib.Path) -> None:
        """Copy a file from the environment to host.

        :param source: Environment file to copy.
        :param destination: Host file path to copy to.  Parent directory
            (destination.parent) must exist.

        :raises FileNotFoundError: If source file or destination's parent
            directory does not exist.
        :raises LXDError: On unexpected error copying file.
        """
        proc = self.execute_run(
            ["test", "-f", source.as_posix()],
            check=False,
            timeout=TIMEOUT_SIMPLE,
        )
        if proc.returncode != 0:
            raise FileNotFoundError(f"File not found: {source.as_posix()!r}")

        if not destination.parent.is_dir():
            raise FileNotFoundError(f"Directory not found: {str(destination.parent)!r}")

        self.lxc.file_pull(
            instance_name=self.instance_name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
        )

    def push_file(self, *, source: pathlib.Path, destination: pathlib.PurePath) -> None:
        """Copy a file from the host into the environment.

        The destination file is overwritten if it exists.

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
            ["test", "-d", destination.parent.as_posix()],
            check=False,
            timeout=TIMEOUT_SIMPLE,
        )
        if proc.returncode != 0:
            raise FileNotFoundError(
                f"Directory not found: {str(destination.parent.as_posix())!r}"
            )

        # Copy into target with uid/gid 0, rather than copying the IDs from the
        # host file.
        self.lxc.file_push(
            instance_name=self.instance_name,
            source=source,
            destination=destination,
            project=self.project,
            remote=self.remote,
            gid=0,
            uid=0,
        )

    def _shutdown(self, delay_mins: int) -> None:
        """Shutdown instance from inside the instance with a given delay.

        :param delay_mins: How long to delay the shutdown.
        """
        if delay_mins < 0:
            raise ValueError("Cannot delay for a negative amount of time.")
        self.execute_run(
            [
                "shutdown",
                f"+{delay_mins}",
                "Shutdown triggered by craft-providers.",
            ],
            capture_output=True,
            check=True,
        )

    def _cancel_shutdown(self) -> None:
        """Cancel any scheduled shutdown on the instance."""
        self.execute_run(["shutdown", "-c"])

    def start(self) -> None:
        """Start the instance.

        :raises LXDError: If the instance fails to start.
        """
        logger.info("Starting instance")
        if self.info().get("Status") == LXDInstanceState.RUNNING.value:
            if (
                state := self.config_get("user.craft_providers.status")
            ) == ProviderInstanceStatus.FINISHED.value:
                logger.debug("Instance already running but available.")
                self.config_set(
                    "user.craft_providers.status", ProviderInstanceStatus.IN_USE.value
                )
                self._cancel_shutdown()
                return
            raise LXDError(
                "Instance is already running but not available.",
                details=f"Instance state is {state}",
                resolution="The same instance cannot be used by multiple processes.",
            )

        self.lxc.start(
            instance_name=self.instance_name, project=self.project, remote=self.remote
        )

        def _is_running(timeout: float) -> None:
            """Raise an error if the instance isn't running."""
            if self.is_running():
                return
            raise LXDError("Instance isn't running")

        # `lxc start` is an asynchronous operation, so wait until the instance
        # starts before returning.
        retry.retry_until_timeout(
            timeout=TIMEOUT_SIMPLE,
            retry_wait=RETRY_WAIT,
            func=_is_running,
            error=LXDError(brief="Instance failed to start."),
        )
        self.config_set(
            "user.craft_providers.status", ProviderInstanceStatus.IN_USE.value
        )

    def restart(self) -> None:
        """Restart the instance.

        :raises LXDError: If the instance fails to restart.
        """
        self.lxc.restart(
            instance_name=self.instance_name, project=self.project, remote=self.remote
        )

        def _is_running(timeout: float) -> None:
            """Raise an error if the instance isn't running."""
            if self.is_running():
                return
            raise LXDError(brief="Instance isn't running.")

        # `lxc restart` is an asynchronous operation, so wait until the instance
        # restarts before returning.
        retry.retry_until_timeout(
            timeout=TIMEOUT_SIMPLE,
            retry_wait=RETRY_WAIT,
            func=_is_running,
            error=LXDError(brief="Instance failed to restart."),
        )

    def stop(self, delay_mins: int | None = None) -> None:
        """Stop the instance.

        :param delay_mins: minutes to delay the instance shutdown.
        :raises LXDError: If the instance fails to stop.

        If delay_mins is 0 (the default), this method waits for the shutdown to finish.
        If it's nonzero, the method returns after preparing the shutdown.
        """
        if delay_mins is not None:
            logger.debug(f"Shutting down after {delay_mins} minutes")
            self.config_set(
                "user.craft_providers.status", ProviderInstanceStatus.FINISHED.value
            )
            self._shutdown(delay_mins)
            return

        self.lxc.stop(
            instance_name=self.instance_name, project=self.project, remote=self.remote
        )

        def _is_stopped(timeout: float) -> None:
            """Raise an error if the instance exists or isn't stopped."""
            # ephemeral instances are deleted when 'stop' completes
            if not self.exists() or self._get_state() == LXDInstanceState.STOPPED:
                return
            raise LXDError(brief="Instance hasn't stopped.")

        # `lxc stop` is an asynchronous operation, so wait until the instance
        # stops before returning.
        retry.retry_until_timeout(
            timeout=TIMEOUT_SIMPLE,
            retry_wait=5,
            func=_is_stopped,
            error=LXDError(brief="Instance failed to stop."),
        )
        if self.exists():
            self.config_set(
                "user.craft_providers.status", ProviderInstanceStatus.FINISHED.value
            )

    def supports_mount(self) -> bool:
        """Check if instance supports mounting from host.

        :returns: True if mount is supported.
        """
        return self.remote == "local"

    def unmount(self, target: pathlib.PurePath) -> None:
        """Unmount mount target shared with host.

        :param target: Target shared with host to unmount.

        :raises LXDError: On failure to unmount target.
        """
        disks = self._get_disk_devices()

        unmounted = False
        for name, config in disks.items():
            if config["path"] == target.as_posix():
                self.lxc.config_device_remove(
                    instance_name=self.instance_name,
                    device=name,
                    project=self.project,
                    remote=self.remote,
                )
                unmounted = True

        if not unmounted:
            raise LXDError(
                brief=(
                    f"Failed to unmount {target.as_posix()!r}"
                    f" in instance {self.instance_name!r} - no such disk."
                ),
                details=f"* Disk device configuration: {disks!r}",
            )

    def unmount_all(self) -> None:
        """Unmount all mounts shared with host.

        :raises LXDError: On failure to unmount target.
        """
        disks = self._get_disk_devices()

        for name, _ in disks.items():
            self.lxc.config_device_remove(
                instance_name=self.instance_name,
                device=name,
                project=self.project,
                remote=self.remote,
            )

    def config_get(self, key: str) -> str:
        """Get instance configuration value.

        :param key: Configuration key to get.

        :returns: Configuration value.

        :raises LXDError: On unexpected error.
        """
        return self.lxc.config_get(
            instance_name=self.instance_name,
            key=key,
            project=self.project,
            remote=self.remote,
        )

    def config_set(self, key: str, value: str) -> None:
        """Set instance configuration value.

        :param key: Configuration key to set.
        :param value: Configuration key to the value.

        :returns: None.

        :raises LXDError: On unexpected error.
        """
        self.lxc.config_set(
            instance_name=self.instance_name,
            key=key,
            value=value,
            project=self.project,
            remote=self.remote,
        )

    def info(self) -> dict[str, Any]:
        """Get info for an instance."""
        return self.lxc.info(
            instance_name=self.instance_name,
            project=self.project,
            remote=self.remote,
        )
