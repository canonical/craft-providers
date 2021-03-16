# Copyright 2021 Canonical Ltd
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

"""API provider for Multipass.

This implementation interfaces with multipass using the `multipass` command-line
utility.
"""

import io
import json
import logging
import pathlib
import shlex
import subprocess
from typing import Any, Dict, List, Optional

from craft_providers import errors

from .errors import MultipassError

logger = logging.getLogger(__name__)


class Multipass:
    """Wrapper for multipass command.

    :param multipass_path: Path to multipass command to use.
    """

    def __init__(
        self, *, multipass_path: pathlib.Path = pathlib.Path("multipass")
    ) -> None:
        self.multipass_path = multipass_path

    def _run(  # pylint: disable=redefined-builtin
        self,
        command: List[str],
        *,
        check=True,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute command in instance_name, allowing output to console."""
        command = [str(self.multipass_path), *command]

        logger.debug("Executing on host: %s", shlex.join(command))
        return subprocess.run(command, check=check, **kwargs)

    def delete(self, *, instance_name: str, purge=True) -> None:
        """Passthrough for running multipass delete.

        :param instance_name: The name of the instance_name to delete.
        :param purge: Flag to purge the instance_name's image after deleting.

        :raises MultipassError: on error.

        """
        command = ["delete", instance_name]
        if purge:
            command.append("--purge")

        try:
            self._run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to delete VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def exec(
        self,
        *,
        command: List[str],
        instance_name: str,
        runner=subprocess.run,
        **kwargs,
    ):
        """Execute command in instance_name with specified runner.

        :param command: Command to execute in the instance.
        :param instance_name: Name of instance to execute in.

        :returns: Runner's instance.
        """
        final_cmd = [str(self.multipass_path), "exec", instance_name, "--", *command]

        quoted_final_cmd = shlex.join(final_cmd)
        logger.debug("Executing on host: %s", quoted_final_cmd)

        return runner(final_cmd, **kwargs)  # pylint: disable=subprocess-run-check

    def info(self, *, instance_name: str) -> Optional[Dict[str, Any]]:
        """Get information/state for instance.

        :returns: Parsed json data from info command.

        :raises MultipassError: On error.
        """
        command = ["info", instance_name, "--format", "json"]

        try:
            proc = self._run(command, capture_output=True, check=True, text=True)
        except subprocess.CalledProcessError as error:
            if "does not exist" in error.stderr:
                return None

            raise MultipassError(
                brief=f"Failed to query info for VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        return json.loads(proc.stdout)

    def launch(
        self,
        *,
        instance_name: str,
        image: str,
        cpus: str = None,
        mem: str = None,
        disk: str = None,
    ) -> None:
        """Launch multipass VM.

        :param instance_name: The name the launched instance_name will have.
        :param image: Name of image to create the instance with.
        :param cpus: Amount of virtual CPUs to assign to the launched instance_name.
        :param mem: Amount of RAM to assign to the launched instance_name.
        :param disk: Amount of disk space the instance_name will see.

        :raises MultipassError: on error.
        """
        command = ["launch", image, "--name", instance_name]
        if cpus is not None:
            command.extend(["--cpus", cpus])
        if mem is not None:
            command.extend(["--mem", mem])
        if disk is not None:
            command.extend(["--disk", disk])

        try:
            self._run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to launch VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def list(self) -> List[str]:
        """List names of VMs.

        :returns: Data from stdout if instance exists, else None.

        :raises MultipassError: On error.
        """
        command = ["list", "--format", "json"]

        try:
            proc = self._run(command, capture_output=True, check=True, text=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief="Failed to query list of VMs.",
                details=errors.details_from_called_process_error(error),
            ) from error

        data_list = json.loads(proc.stdout).get("list", dict())
        return [instance["name"] for instance in data_list]

    def mount(
        self,
        *,
        source: pathlib.Path,
        target: str,
        uid_map: Dict[str, str] = None,
        gid_map: Dict[str, str] = None,
    ) -> None:
        """Mount host source path to target.

        :param source: Path of local directory to mount.
        :param target: Target mount points, in <name>[:<path>] format, where
            <name> is an instance name, and optional <path> is the mount point.
            If omitted, the mount point will be the same as the source's
            absolute path.
        :param uid_map: A mapping of user IDs for use in the mount of the form
            <host-id> -> <instance-name-id>.  File and folder ownership will be
            mapped from <host> to <instance-name> inside the instance_name.
        :param gid_map: A mapping of group IDs for use in the mount of the form
            <host-id> -> <instance-name-id>.  File and folder ownership will be
            mapped from <host> to <instance-name> inside the instance_name.
        """
        command = ["mount", str(source), target]

        if uid_map is not None:
            for host_id, instance_id in uid_map.items():
                command.extend(["--uid-map", f"{host_id}:{instance_id}"])

        if gid_map is not None:
            for host_id, instance_id in gid_map.items():
                command.extend(["--gid-map", f"{host_id}:{instance_id}"])

        try:
            self._run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to mount {str(source)!r} to {target!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def start(self, *, instance_name: str) -> None:
        """Start VM instance.

        :param instance_name: the name of the instance to start.

        :raises MultipassError: on error.
        """
        command = ["start", instance_name]

        try:
            self._run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to start VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def stop(self, *, instance_name: str, delay_mins: int = 0) -> None:
        """Stop VM instance.

        :param instance_name: the name of the instance_name to stop.
        :param delay_mins: Delay shutdown for specified number of minutes.

        :raises MultipassError: on error.
        """
        command = ["stop"]

        if delay_mins != 0:
            command.extend(["--time", str(delay_mins)])

        command.append(instance_name)

        try:
            self._run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to stop VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def transfer(self, *, source: str, destination: str) -> None:
        """Transfer to destination path with source IO.

        :param source: The source path, prefixed with <name:> for a path inside
            the instance.
        :param destination: The destination path, prefixed with <name:> for a
            path inside the instance.

        :raises MultipassError: On error.
        """
        command = ["transfer", source, destination]

        try:
            self._run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to transfer {source!r} to {destination!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def transfer_destination_io(
        self, *, source: str, destination: io.BufferedIOBase, chunk_size: int = 4096
    ) -> None:
        """Transfer from source file to destination IO.

        Note that this can't use std{in,out}=open(...) due to LP #1849753.

        :param source: The source path, prefixed with <name:> for a path inside
            the instance.
        :param destination: An IO stream to write to.

        :raises MultipassError: On error.
        """
        command = [str(self.multipass_path), "transfer", source, "-"]
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )

        # Should never happen, but pyright makes noise.
        assert proc.stdout is not None

        while True:
            data = proc.stdout.read(chunk_size)
            if not data:
                break

            destination.write(data)

        try:
            _, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()

        if proc.returncode != 0:
            raise MultipassError(
                brief=f"Failed to transfer file {source!r}.",
                details=errors.details_from_command_error(
                    cmd=command, stderr=stderr, returncode=proc.returncode
                ),
            )

    def transfer_source_io(
        self, *, source: io.BufferedIOBase, destination: str, chunk_size: int = 4096
    ) -> None:
        """Transfer to destination path with source IO.

        Note that this can't use std{in,out}=open(...) due to LP #1849753.

        :param source: An IO stream to read from.
        :param destination: The destination path, prefixed with <name:> for a
            path inside the instance.

        :raises MultipassError: On error.
        """
        command = [str(self.multipass_path), "transfer", "-", destination]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE)

        # Should never happen, but pyright makes noise.
        assert proc.stdin is not None

        while True:
            data = source.read(chunk_size)
            if not data:
                break

            proc.stdin.write(data)

        # Wait until process is complete.
        try:
            _, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()

        if proc.returncode != 0:
            raise MultipassError(
                brief=f"Failed to transfer file to destination {destination!r}.",
                details=errors.details_from_command_error(
                    cmd=command, stderr=stderr, returncode=proc.returncode
                ),
            )

    def umount(self, *, mount: str) -> None:
        """Unmount target in VM.

        :param mount: Mount point in <name>[:<path>] format, where <name> are
            instance names, and optional <path> are mount points.  If omitted,
            all mounts will be removed from the name instance.

        :raises MultipassError: On error.
        """
        command = ["umount", mount]

        try:
            self._run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to unmount {mount!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error
