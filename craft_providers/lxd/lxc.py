#
# Copyright 2021-2022 Canonical Ltd.
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

"""LXC wrapper."""
import enum
import logging
import pathlib
import shlex
import subprocess
from typing import Any, Callable, Dict, List, Optional

import yaml

from craft_providers import errors

from .errors import LXDError

logger = logging.getLogger(__name__)


# pylint: disable=too-many-lines


class StdinType(enum.Enum):
    """Mappings for input stream to pass to stdin for lxc commands."""

    INTERACTIVE = subprocess.DEVNULL
    NULL = None


def load_yaml(data):
    """Load yaml without additional resolvers.

    LXD may return YAML that has datetimes that are not valid when parsed to
    datetime.datetime().  Instead just use the base loader and avoid resolving
    this type (and others).
    """
    return yaml.load(data, Loader=yaml.BaseLoader)


class LXC:  # pylint: disable=too-many-public-methods
    """Wrapper for lxc command-line interface."""

    def __init__(
        self,
        *,
        lxc_path: pathlib.Path = pathlib.Path("lxc"),
    ):
        self.lxc_path = lxc_path

    def _run_lxc(
        self,
        command: List[str],
        *,
        check: bool,
        project: Optional[str] = None,
        stdin: StdinType = StdinType.INTERACTIVE,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute lxc command on host, allowing output to console.

        Handles the --project=project options if project is specified.
        :param command: lxc command to execute.
        :param check: Check if the lxc command exits with a non-zero exit code.
        :param project: Name of LXD project.
        :param stdin: What input stream to pass to lxc.
        :param kwargs: Additional parameters to pass to the lxc command.

        :returns: Completed process.
        """
        lxc_cmd = [str(self.lxc_path)]

        if project is not None:
            lxc_cmd += ["--project", project]

        lxc_cmd += command

        logger.debug("Executing on host: %s", shlex.join(lxc_cmd))

        # for subprocess, input takes priority over stdin
        if "input" in kwargs:
            return subprocess.run(lxc_cmd, check=check, **kwargs)

        return subprocess.run(lxc_cmd, check=check, stdin=stdin.value, **kwargs)

    def config_device_add_disk(
        self,
        *,
        instance_name: str,
        source: pathlib.Path,
        path: pathlib.PurePath,
        device: str,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Mount host source directory to target mount point.

        :param instance_name: Name of instance.
        :param source: Host path.
        :param path: Mount target in instance.
        :param device: Name of device.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "config",
            "device",
            "add",
            f"{remote}:{instance_name}",
            device,
            "disk",
            f"source={source.as_posix()}",
            f"path={path.as_posix()}",
        ]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to add disk to instance {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def config_device_remove(
        self,
        *,
        instance_name: str,
        device: str,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Mount host source directory to target mount point.

        :param instance_name: Name of instance.
        :param device: Name of device.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "config",
            "device",
            "remove",
            f"{remote}:{instance_name}",
            device,
        ]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to remove device from instance {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def config_device_show(
        self, *, instance_name: str, project: str = "default", remote: str = "local"
    ) -> Dict[str, Any]:
        """Show full device configuration.

        :param instance_name: Name of instance.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["config", "device", "show", f"{remote}:{instance_name}"]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to show devices for instance {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        return load_yaml(proc.stdout)

    def config_set(
        self,
        *,
        instance_name: str,
        key: str,
        value: str,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Set instance_name configuration key.

        :param instance_name: Name of instance.
        :param key: Config key name.
        :param value: Config key value.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["config", "set", f"{remote}:{instance_name}", key, value]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=(
                    f"Failed to set config key {key!r} to {value!r}"
                    f" for instance {instance_name!r}."
                ),
                details=errors.details_from_called_process_error(error),
            ) from error

    def delete(
        self,
        *,
        instance_name: str,
        force: bool = False,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Delete instance.

        :param instance_name: Name of instance.
        :param force: Force deletion if running.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["delete", f"{remote}:{instance_name}"]

        if force:
            command.append("--force")

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to delete instance {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def exec(
        self,
        *,
        command: List[str],
        instance_name: str,
        cwd: Optional[str] = None,
        mode: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
        runner: Callable = subprocess.run,
        **kwargs,
    ):
        """Execute command in instance_name with specified runner.

        :param command: Command to execute in the instance.
        :param instance_name: Name of instance to execute in.
        :param cwd: Optional current working directory for command.
        :param mode: Override terminal mode Valid options include: "auto",
            "interactive", "non-interactive". lxd default is "auto".
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.
        :param runner: Execution function to invoke, e.g. subprocess.run or
            Popen.  First argument is finalized command with the attached
            kwargs.
        :param kwargs: Additional kwargs for runner.

        :returns: Runner's instance.
        """
        final_cmd = [
            str(self.lxc_path),
            "--project",
            project,
            "exec",
            f"{remote}:{instance_name}",
        ]

        if cwd is not None:
            final_cmd.extend(["--cwd", cwd])

        if mode is not None:
            final_cmd.extend(["--mode", mode])

        final_cmd += ["--", *command]

        logger.debug("Executing in container: %s", shlex.join(final_cmd))

        return runner(final_cmd, **kwargs)  # pylint: disable=subprocess-run-check

    def file_pull(
        self,
        *,
        instance_name: str,
        source: pathlib.PurePath,
        destination: pathlib.Path,
        create_dirs: bool = False,
        recursive: bool = False,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Retrieve file from instance_name.

        :param instance_name: Name of instance.
        :param source: Path in environment to pull.
        :param destination: Path in host to write to.
        :param create_dirs: Create any directories necessary.
        :param recursive: Recursively transfer files.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "file",
            "pull",
            f"{remote}:{instance_name}{source.as_posix()}",
            destination.as_posix(),
        ]

        if create_dirs:
            command.append("--create-dirs")

        if recursive:
            command.append("--recursive")

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=(
                    f"Failed to pull file {source.as_posix()!r}"
                    f" from instance {instance_name!r}."
                ),
                details=errors.details_from_called_process_error(error),
            ) from error

    def file_push(
        self,
        *,
        instance_name: str,
        source: pathlib.Path,
        destination: pathlib.PurePath,
        create_dirs: bool = False,
        recursive: bool = False,
        gid: Optional[int] = None,
        uid: Optional[int] = None,
        mode: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Create file with content and file mode.

        :param instance_name: Name of instance to push file to.
        :param source: Path in host to push.
        :param destination: Path in environment to write to.
        :param create_dirs: Create any directories necessary.
        :param recursive: Recursively transfer files.
        :param gid: Optional gid to set on push (lxd's default is -1).
        :param uid: Optional uid to set on push (lxd's default is -1).
        :param mode: Optional file mode to set on file.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "file",
            "push",
            source.as_posix(),
            f"{remote}:{instance_name}{destination.as_posix()}",
        ]

        if create_dirs:
            command.append("--create-dirs")

        if recursive:
            command.append("--recursive")

        if mode is not None:
            command.append(f"--mode={mode}")

        if gid is not None:
            command.append(f"--gid={gid}")

        if uid is not None:
            command.append(f"--uid={uid}")

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=(
                    f"Failed to push file {source.as_posix()!r}"
                    f" to instance {instance_name!r}."
                ),
                details=errors.details_from_called_process_error(error),
            ) from error

    def has_image(
        self, image_name, *, project: str = "default", remote: str = "local"
    ) -> bool:
        """Check if image with given alias name is present.

        :param image_name: Name of image alias.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.
        """
        image_list = self.image_list(project=project, remote=remote)

        for image in image_list:
            for alias in image["aliases"]:
                if image_name == alias["name"]:
                    return True

        return False

    def info(
        self,
        *,
        instance_name: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
    ) -> Dict[str, Any]:
        """Show instance or server information.

        :param instance_name: Optional instance name.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        if instance_name is None:
            instance_name = ""

        command = ["info", remote + ":" + instance_name]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to get info for remote {remote!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            return load_yaml(proc.stdout)
        except yaml.YAMLError as error:
            raise LXDError(
                brief="Failed to parse lxc info.",
                details=(
                    f"* Command that failed: {shlex.join(proc.args)!r}\n"
                    f"* Command output: {proc.stdout!r}"
                ),
            ) from error

    def launch(
        self,
        *,
        instance_name: str,
        image: str,
        image_remote: str,
        config_keys: Optional[Dict[str, str]] = None,
        ephemeral: bool = False,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Launch instance.

        :param instance_name: Name of instance to launch.
        :param image: Name of image to use.
        :param image_remote: Name of image's remote.
        :param config_keys: Configuration keys to set.
        :param ephemeral: Use ephemeral instance.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "launch",
            f"{image_remote}:{image}",
            f"{remote}:{instance_name}",
        ]

        if ephemeral:
            command.append("--ephemeral")

        if config_keys is not None:
            for config_key in [f"{k}={v}" for k, v in config_keys.items()]:
                command.extend(["--config", config_key])

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                stdin=StdinType.INTERACTIVE,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to launch instance {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def image_copy(
        self,
        *,
        image: str,
        image_remote: str,
        alias: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Copy image.

        :param instance_name: Optional instance name.
        :param alias: New alias to add to image.
        :param image: Image to copy.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "image",
            "copy",
            f"{image_remote}:{image}",
            f"{remote}:",
        ]

        if alias is not None:
            command.append(f"--alias={alias}")

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to copy image {image!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def image_delete(
        self, *, image: str, project: str = "default", remote: str = "local"
    ) -> None:
        """Delete image.

        :param image: Image to delete.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = [
            "image",
            "delete",
            f"{remote}:{image}",
        ]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to delete image {image!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def image_list(
        self, *, project: str = "default", remote: str = "local"
    ) -> List[Dict[str, Any]]:
        """List images.

        :param project: Name of LXD project.
        :param remote: Name of LXD remote.
        """
        command = ["image", "list", f"{remote}:", "--format=yaml"]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to list images for project {project!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            return load_yaml(proc.stdout)
        except yaml.YAMLError as error:
            raise LXDError(
                brief="Failed to parse lxc image list.",
                details=(
                    f"* Command that failed: {shlex.join(proc.args)!r}\n"
                    f"* Command output: {proc.stdout!r}"
                ),
            ) from error

    def list(
        self,
        *,
        project: str = "default",
        remote: str = "local",
    ) -> List[Dict[str, Any]]:
        """List instances and their status.

        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :returns: List of containers and their info.

        :raises LXDError: on unexpected error.
        """
        command = ["list", f"{remote}:", "--format=yaml"]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to list instances for project {project!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            return load_yaml(proc.stdout)
        except yaml.YAMLError as error:
            raise LXDError(
                brief="Failed to parse lxc list.",
                details=(
                    f"* Command that failed: {shlex.join(proc.args)!r}\n"
                    f"* Command output: {proc.stdout!r}"
                ),
            ) from error

    def list_names(
        self, *, project: str = "default", remote: str = "local"
    ) -> List[str]:
        """List container names.

        A helper to get a list of container names from list().

        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :returns: List of container names.

        :raises LXDError: on unexpected error.
        """
        instances = self.list(project=project, remote=remote)

        try:
            return [i["name"] for i in instances]
        except KeyError as error:
            raise LXDError(
                brief="Failed to parse lxc list.",
                details=(f"* Data received from lxc list: {instances!r}"),
            ) from error

    def profile_edit(
        self,
        *,
        profile: str,
        config: Dict[str, Any],
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Set profile configuration.

        :param profile: Name of profile.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["profile", "edit", f"{remote}:{profile}"]
        encoded_config = yaml.dump(config).encode()

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
                input=encoded_config,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to set profile {profile!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def profile_show(
        self, *, profile: str, project: str = "default", remote: str = "local"
    ) -> Dict[str, Any]:
        """Get profile configuration.

        :param profile: Name of profile.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["profile", "show", f"{remote}:{profile}"]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to show profile {profile!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        return load_yaml(proc.stdout)

    def project_create(self, *, project: str, remote: str = "local") -> None:
        """Create project.

        :param project: Name of LXD project to create.
        :param remote: Name of LXD remote to create project on.

        :raises LXDError: on unexpected error.
        """
        command = ["project", "create", f"{remote}:{project}"]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to create project {project!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def project_delete(self, *, project: str, remote: str = "local") -> None:
        """Delete project, if it exists.

        :param project: Name of LXD project to delete.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["project", "delete", f"{remote}:{project}"]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to delete project {project!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def project_list(self, remote: str = "local") -> List[str]:
        """Get list of projects.

        :param remote: Name of LXD remote to query.

        :returns: List of project names.

        :raises LXDError: on unexpected error.
        """
        command = ["project", "list", f"{remote}:", "--format=yaml"]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to list projects on remote {remote!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            projects = load_yaml(proc.stdout)
            return sorted([p["name"] for p in projects])
        except (KeyError, yaml.YAMLError) as error:
            raise LXDError(
                brief="Failed to parse lxc project list.",
                details=(
                    f"* Command that failed: {shlex.join(proc.args)!r}\n"
                    f"* Command output: {proc.stdout!r}"
                ),
            ) from error

    def publish(
        self,
        *,
        instance_name: str,
        alias: Optional[str] = None,
        force: bool = False,
        image_remote: str = "local",
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Publish image from instance.

        :param instance_name: Name of instance to publish image from.
        :param alias: New alias to define at target.
        :param force: Force publishing of image, even if container is running.
        :param image_remote: Name of remote to publish image to.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote instance is found on.

        :raises LXDError: on unexpected error.
        """
        command = [
            "publish",
            f"{remote}:{instance_name}",
            f"{image_remote}:",
        ]

        if alias is not None:
            command.append(f"--alias={alias}")

        if force:
            command.append("--force")

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to publish image from {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def remote_add(
        self, *, remote: str, addr: str, protocol: str = "simplestreams"
    ) -> None:
        """Add a public remote.

        :param remote: Name of remote to add.
        :param addr: Address of remote.
        :param protocol: Name of protocol ("simplestreams" or "lxd").

        :raises LXDError: on unexpected error.
        """
        command = ["remote", "add", remote, addr, f"--protocol={protocol}"]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to add remote {remote!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def remote_list(self) -> Dict[str, Any]:
        """Get list of remotes.

        :returns: dictionary with remote name mapping to config.
        """
        command = ["remote", "list", "--format=yaml"]

        try:
            proc = self._run_lxc(
                command,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief="Failed to list remotes.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            return load_yaml(proc.stdout)
        except yaml.YAMLError as error:
            raise LXDError(
                brief="Failed to parse lxc remote list.",
                details=(
                    f"* Command that failed: {shlex.join(proc.args)!r}\n"
                    f"* Command output: {proc.stdout!r}"
                ),
            ) from error

    def start(
        self, *, instance_name: str, project: str = "default", remote: str = "local"
    ) -> None:
        """Start container.

        :param instance_name: Name of instance to start.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["start", f"{remote}:{instance_name}"]

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to start {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def stop(
        self,
        *,
        instance_name: str,
        force: bool = False,
        timeout: int = -1,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Stop container.

        :param instance_name: Name of instance to stop.
        :param force: Force instance to stop.
        :param timeout: Timeout in seconds. -1 is no timeout.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote.

        :raises LXDError: on unexpected error.
        """
        command = ["stop", f"{remote}:{instance_name}"]

        if force:
            command.append("--force")

        if timeout != -1:
            command.append(f"--timeout={timeout}")

        try:
            self._run_lxc(
                command,
                capture_output=True,
                check=True,
                project=project,
            )
        except subprocess.CalledProcessError as error:
            raise LXDError(
                brief=f"Failed to stop {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error
