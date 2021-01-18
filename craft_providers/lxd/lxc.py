# Copyright (C) 2020 Canonical Ltd
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

"""LXC wrapper."""
import logging
import pathlib
import shlex
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import yaml

from .yaml_loader import _load_yaml

logger = logging.getLogger(__name__)


class LXC:  # pylint: disable=too-many-public-methods
    """Wrapper for lxc."""

    def __init__(
        self,
        *,
        lxc_path: pathlib.Path = pathlib.Path("/snap/bin/lxc"),
    ):
        if lxc_path is None:
            self.lxc_path: pathlib.Path = pathlib.Path("lxc")
        else:
            self.lxc_path = lxc_path

    def _run(  # pylint: disable=redefined-builtin
        self,
        *,
        command: List[str],
        project: str = "default",
        check: bool = True,
        input=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) -> subprocess.CompletedProcess:
        """Execute command in instance, allowing output to console."""
        command = [str(self.lxc_path), "--project", project, *command]
        quoted = " ".join([shlex.quote(c) for c in command])

        logger.warning("Executing on host: %s", quoted)

        try:
            if input is not None:
                proc = subprocess.run(
                    command, check=check, input=input, stderr=stderr, stdout=stdout
                )
            else:
                proc = subprocess.run(
                    command, check=check, stderr=stderr, stdout=stdout
                )
        except subprocess.CalledProcessError as error:
            logger.warning("Failed to execute: %s", error.output)
            raise error

        return proc

    def config_device_add_disk(
        self,
        *,
        instance: str,
        source: pathlib.Path,
        destination: pathlib.Path,
        device_name: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Mount host source directory to target mount point."""
        if device_name is None:
            device_name = destination.as_posix().replace("/", "_")

        self._run(
            command=[
                "config",
                "device",
                "add",
                f"{remote}:{instance}",
                device_name,
                "disk",
                f"source={source.as_posix()}",
                f"path={destination.as_posix()}",
            ],
            project=project,
        )

    def config_device_show(
        self, *, instance: str, project: str = "default", remote: str = "local"
    ) -> Dict[str, Any]:
        """Show device config."""
        proc = self._run(
            command=["config", "device", "show", f"{remote}:{instance}"],
            project=project,
        )

        return _load_yaml(proc.stdout)

    def config_set(
        self,
        *,
        instance: str,
        key: str,
        value: str,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Set instance configuration key."""
        self._run(
            command=["config", "set", f"{remote}:{instance}", key, value],
            project=project,
        )

    def delete(
        self,
        *,
        instance: str,
        project: str = "default",
        remote: str = "local",
        force=False,
    ) -> None:
        """Delete instance."""
        command = ["delete", f"{remote}:{instance}"]

        if force:
            command.append("--force")

        self._run(command=command, project=project)

    def _formulate_command(
        self,
        *,
        command: List[str],
        instance: str,
        cwd: str = "/root",
        mode: str = "auto",
        project: str = "default",
        remote: str = "local",
    ) -> List[str]:
        """Formulate command to run."""
        final_cmd = [
            str(self.lxc_path),
            "--project",
            project,
            "exec",
            f"{remote}:{instance}",
        ]

        if cwd != "/root":
            final_cmd.extend(["--cwd", cwd])

        if mode != "auto":
            final_cmd.extend(["--mode", mode])

        final_cmd.extend(["--", *command])

        return final_cmd

    def exec(
        self,
        *,
        command: List[str],
        instance: str,
        cwd: str = "/root",
        mode: str = "auto",
        project: str = "default",
        remote: str = "local",
        runner=subprocess.run,
        **kwargs,
    ):
        """Execute command in instance with specified runner."""
        command = self._formulate_command(
            command=command,
            instance=instance,
            cwd=cwd,
            mode=mode,
            project=project,
            remote=remote,
        )

        quoted = " ".join([shlex.quote(c) for c in command])
        logger.warning("Executing in container: %s", quoted)

        return runner(command, **kwargs)  # pylint: disable=subprocess-run-check

    def file_pull(
        self,
        *,
        instance: str,
        source: pathlib.Path,
        destination: pathlib.Path,
        create_dirs: bool = True,
        recursive: bool = False,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Retrieve file from instance."""
        command = [
            "file",
            "pull",
            f"{remote}:{instance}{source.as_posix()}",
            destination.as_posix(),
        ]

        if create_dirs:
            command.append("--create-dirs")

        if recursive:
            command.append("--recursive")

        self._run(
            command=command,
            project=project,
        )

    def file_push(
        self,
        *,
        instance: str,
        source: pathlib.Path,
        destination: pathlib.Path,
        create_dirs: bool = False,
        recursive: bool = False,
        gid: str = "-1",
        uid: str = "-1",
        mode: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Create file with content and file mode."""
        command = [
            "file",
            "push",
            source.as_posix(),
            f"{remote}:{instance}{destination.as_posix()}",
        ]

        if create_dirs:
            command.append("--create-dirs")

        if recursive:
            command.append("--recursive")

        if mode:
            command.append(f"--mode={mode}")

        if gid != "-1":
            command.append(f"--gid={gid}")

        if uid != "-1":
            command.append(f"--uid={gid}")

        self._run(
            command=command,
            project=project,
        )

    def info(
        self, *, project: str = "default", remote: str = "local"
    ) -> Dict[str, Any]:
        """Get server config that instance is running on."""
        proc = self._run(
            command=["info", remote + ":"],
            project=project,
        )
        return _load_yaml(proc.stdout)

    def launch(
        self,
        *,
        config_keys: Dict[str, str],
        image: str,
        image_remote: str,
        instance: str,
        ephemeral: bool = False,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Launch instance."""
        command = [
            "launch",
            f"{image_remote}:{image}",
            f"{remote}:{instance}",
        ]

        if ephemeral:
            command.append("--ephemeral")

        for config_key in [f"{k}={v}" for k, v in config_keys.items()]:
            command.extend(["--config", config_key])

        self._run(command=command, project=project)

    def image_copy(
        self,
        *,
        image: str,
        image_remote: str,
        alias: str,
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Copy image."""
        self._run(
            command=[
                "image",
                "copy",
                f"{image_remote}:{image}",
                f"{remote}:",
                f"--alias={alias}",
            ],
            project=project,
        )

    def image_delete(
        self, *, image: str, project: str = "default", remote: str = "local"
    ) -> None:
        """Delete image."""
        self._run(
            command=[
                "image",
                "delete",
                f"{remote}:{image}",
            ],
            project=project,
        )

    def image_list(
        self, *, project: str = "default", remote: str = "local"
    ) -> List[Dict[str, Any]]:
        """List instances."""
        proc = self._run(
            command=["image", "list", f"{remote}:", "--format=yaml"],
            project=project,
        )

        return _load_yaml(proc.stdout)

    def list(
        self,
        *,
        instance: Optional[str] = None,
        project: str = "default",
        remote: str = "local",
    ) -> List[Dict[str, Any]]:
        """List instances."""
        command = ["list", "--format=yaml"]
        if instance is None:
            instance = ""

        command.append(f"{remote}:{instance}")

        proc = self._run(
            command=command,
            project=project,
        )

        return _load_yaml(proc.stdout)

    def profile_edit(
        self,
        *,
        profile: str,
        config: Dict[str, Any],
        project: str = "default",
        remote: str = "local",
    ) -> None:
        """Edit profile."""
        encoded_config = yaml.dump(config).encode()
        self._run(
            command=["profile", "edit", f"{remote}:{profile}"],
            project=project,
            input=encoded_config,
        )

    def profile_show(
        self, *, profile: str, project: str = "default", remote: str = "local"
    ) -> Dict[str, Any]:
        """Get profile."""
        proc = self._run(
            command=["profile", "show", f"{remote}:{profile}"], project=project
        )

        return _load_yaml(proc.stdout)

    def project_create(self, *, project: str, remote: str = "local") -> None:
        """Create project."""
        self._run(command=["project", "create", f"{remote}:{project}"])

    def project_list(self, remote: str = "local") -> List[str]:
        """Get list of projects.

        :returns: dictionary with remote name mapping to config.
        """
        proc = self._run(command=["project", "list", remote, "--format=yaml"])

        projects = _load_yaml(proc.stdout)
        return sorted([p["name"] for p in projects])

    def project_delete(self, *, project: str, remote: str = "local") -> None:
        """Delete project, if exists."""
        self._run(command=["project", "delete", f"{remote}:{project}"])

    def publish(
        self,
        *,
        alias: str,
        instance: str,
        project: str,
        force: bool = True,
        remote: str = "local",
    ) -> None:
        """Create project."""
        command = ["publish", "--alias", alias, f"{remote}:{instance}"]
        if force:
            command.append("--force")

        self._run(
            command=command,
            project=project,
        )

    def remote_add(self, *, remote: str, addr: str, protocol: str) -> None:
        """Add a public remote."""
        self._run(command=["remote", "add", remote, addr, f"--protocol={protocol}"])

    def remote_list(self) -> Dict[str, Any]:
        """Get list of remotes.

        :returns: dictionary with remote name mapping to config.
        """
        proc = self._run(command=["remote", "list", "--format=yaml"])

        return _load_yaml(proc.stdout)

    def setup(self) -> None:
        """(Re)Setup lxc wrapper."""
        if self.lxc_path.exists():
            return

        lxc_path = shutil.which("lxc")
        if lxc_path is None:
            lxc_path = "/snap/bin/lxc"

        self.lxc_path = pathlib.Path(lxc_path)
        if not self.lxc_path.exists():
            raise RuntimeError("lxc not found in PATH.")

    def start(
        self, *, instance: str, project: str = "default", remote: str = "local"
    ) -> None:
        """Start container."""
        self._run(command=["start", f"{remote}:{instance}"], project=project)

    def stop(
        self,
        *,
        instance: str,
        project: str = "default",
        remote: str = "local",
        force=True,
        timeout: int = -1,
    ) -> None:
        """Stop container."""
        command = ["stop", f"{remote}:{instance}"]

        if force:
            command.append("--force")

        if timeout != -1:
            command.append(f"--timeout={timeout}")

        self._run(command=command, project=project)


def purge_project(*, lxc: LXC, project: str = "default", remote: str = "local") -> None:
    """Remove project and any associated bits."""
    # with contextlib.suppress(subprocess.CalledProcessError):
    projects = lxc.project_list(remote=remote)
    if project not in projects:
        logger.warning("Attempted to purge non-existent project '%s'.", project)
        return

    # Cleanup any outstanding instances.
    for instance in lxc.list(project=project):
        logger.warning("Deleting instance '%s'.", instance)
        lxc.delete(
            instance=instance["name"], project=project, remote=remote, force=True
        )

    # Cleanup any outstanding images.
    for image in lxc.image_list(project=project):
        logger.warning("Deleting image '%s'.", image)
        lxc.image_delete(image=image["fingerprint"], project=project, remote=remote)

    # Cleanup project.
    logger.warning("Deleting project '%s'.", project)
    lxc.project_delete(project=project, remote=remote)
