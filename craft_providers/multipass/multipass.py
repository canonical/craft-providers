#
# Copyright 2022 Canonical Ltd.
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

"""API provider for Multipass.

This implementation interfaces with multipass using the `multipass` command-line
utility.
"""

import io
import json
import locale
import logging
import pathlib
import shlex
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import packaging.version

from craft_providers import errors
from craft_providers.const import RETRY_WAIT

from .errors import MultipassError

logger = logging.getLogger(__name__)


class Multipass:
    """Wrapper for multipass command.

    :param multipass_path: Path to multipass command to use.
    :cvar minimum_required_version: Minimum required version for compatibility.
    """

    # TODO: bump to 1.14.1 once it is released (#638)
    minimum_required_version = "1.7"

    def __init__(
        self, *, multipass_path: pathlib.Path = pathlib.Path("multipass")
    ) -> None:
        self.multipass_path = multipass_path

    def _run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Execute a multipass command.

        It always checks the result (as no errors should pass silently) and captures the
        output (so `multipass` does not pollute the terminal).
        """
        command = [str(self.multipass_path), *command]

        logger.debug("Executing on host: %s", shlex.join(command))
        return subprocess.run(command, check=True, capture_output=True, **kwargs)

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
            self._run(command)
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
        runner: Callable = subprocess.run,
        timeout: Optional[float] = None,
        check: bool = False,
        **kwargs,
    ):
        """Execute command in instance_name with specified runner.

        The working directory the command is executed from inside the instance depends
        on the host's cwd. From the Multipass documentation:
        "In case we are executing the alias on the host from a directory which is
        mounted on the instance, the command will be executed on the instance from
        there. If the working directory is not mounted on the instance, the command will
        be executed on the default directory on the instance."

        :param command: Command to execute in the instance.
        :param instance_name: Name of instance to execute in.
        :param runner: Execution function to invoke, e.g. subprocess.run or
            Popen.  First argument is finalized command with the attached
            kwargs.
        :param timeout: Timeout (in seconds) for the command.
        :param check: Raise an exception if the command fails.
        :param kwargs: Additional kwargs for runner.

        :returns: Runner's instance.
        """
        final_cmd = [str(self.multipass_path), "exec", instance_name, "--", *command]

        quoted_final_cmd = shlex.join(final_cmd)
        logger.debug("Executing on host: %s", quoted_final_cmd)

        # Only subprocess.run supports timeout
        if runner is subprocess.run:
            return runner(final_cmd, timeout=timeout, check=check, **kwargs)

        return runner(final_cmd, **kwargs)

    def info(self, *, instance_name: str) -> Dict[str, Any]:
        """Get information/state for instance.

        :returns: Parsed json data from info command.

        :raises MultipassError: On error.
        """
        command = ["info", instance_name, "--format", "json"]

        try:
            proc = self._run(command, text=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to query info for VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        return json.loads(proc.stdout)

    def is_supported_version(self) -> bool:
        """Check if Multipass version is supported.

        A helper to check if Multipass meets minimum supported version for
        craft-providers.

        :returns: True if installed version is supported.
        """
        minimum_version = packaging.version.parse(self.minimum_required_version)
        version, _ = self.version()

        parsed_version = None
        while parsed_version is None:
            try:
                parsed_version = packaging.version.parse(version)
            except packaging.version.InvalidVersion:
                # This catches versions such as: 1.15.0-dev.2929.pr661, which are
                # compliant, but not pep440 compliant. We can lob off sections until
                # we get a pep440 cempliant version.
                version = version.rpartition(".")[0]

        return parsed_version >= minimum_version

    def launch(
        self,
        *,
        instance_name: str,
        image: str,
        cpus: Optional[str] = None,
        mem: Optional[str] = None,
        disk: Optional[str] = None,
    ) -> None:
        """Launch multipass VM.

        :param instance_name: The name the launched instance will have.
        :param image: Name of image to create the instance with.
        :param cpus: Amount of virtual CPUs to assign to the launched instance.
        :param mem: Amount of RAM to assign to the launched instance.
        :param disk: Amount of disk space the launched instance will have.

        :raises MultipassError: on error.
        """
        command = ["launch", image, "--name", instance_name]
        if cpus is not None:
            command.extend(["--cpus", cpus])
        if mem is not None:
            command.extend(["--memory", mem])
        if disk is not None:
            command.extend(["--disk", disk])

        try:
            self._run(command)
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
            proc = self._run(command, text=True)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief="Failed to query list of VMs.",
                details=errors.details_from_called_process_error(error),
            ) from error

        data_list = json.loads(proc.stdout).get("list", [])
        return [instance["name"] for instance in data_list]

    def mount(
        self,
        *,
        source: pathlib.Path,
        target: str,
        uid_map: Optional[Dict[str, str]] = None,
        gid_map: Optional[Dict[str, str]] = None,
    ) -> None:
        """Mount host source path to target.

        :param source: Path of local directory to mount.
        :param target: Target mount points, in <name>[:<path>] format, where
            <name> is an instance name, and optional <path> is the mount point.
            If omitted, the mount point will be the same as the source's
            absolute path.
        :param uid_map: A mapping of user IDs for use in the mount of the form
            <host-id> -> <instance-id>.  File and folder ownership will be
            mapped from <host-id> to <instance-id> inside the instance.
        :param gid_map: A mapping of group IDs for use in the mount of the form
            <host-id> -> <instance-id>.  File and folder ownership will be
            mapped from <host-id> to <instance-id> inside the instance.
        """
        command = ["mount", str(source), target]

        if uid_map is not None:
            for host_id, instance_id in uid_map.items():
                command.extend(["--uid-map", f"{host_id}:{instance_id}"])

        if gid_map is not None:
            for host_id, instance_id in gid_map.items():
                command.extend(["--gid-map", f"{host_id}:{instance_id}"])

        try:
            self._run(command)
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
            self._run(command)
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
        command = ["stop", instance_name]

        if delay_mins != 0:
            command.extend(["--time", str(delay_mins)])

        try:
            self._run(command)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to stop VM {instance_name!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def transfer(self, *, source: str, destination: str) -> None:
        """Transfer to destination path with source IO.

        Multipass transfer uses sftp. By default, only the user `ubuntu` can transfer
        files. Therefore, the path inside the instance should be accessible by the
        `ubuntu` user.

        By default, Multipass only has access to the host's home directory. The host's
        path should be inside the home directory.

        :param source: The source path, prefixed with <name:> for a path inside
            the instance.
        :param destination: The destination path, prefixed with <name:> for a
            path inside the instance.

        :raises MultipassError: On error.
        """
        command = ["transfer", source, destination]

        try:
            self._run(command)
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
        :param chunk_size: Number of bytes to transfer at a time.  Defaults to
            4096.

        :raises MultipassError: On error.
        """
        command = [str(self.multipass_path), "transfer", source, "-"]
        with subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            # Should never happen, but mypy/pyright makes noise.
            assert proc.stdout is not None
            assert proc.stderr is not None

            while True:
                data = proc.stdout.read(chunk_size)
                if not data:
                    break

                destination.write(data)

            # Take one read of stderr in case there is anything useful
            # for debugging an error.
            stderr = proc.stderr.read()

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
        :param chunk_size: Number of bytes to transfer at a time.  Defaults to
            4096.

        :raises MultipassError: On error.
        """
        command = [str(self.multipass_path), "transfer", "-", destination]
        with subprocess.Popen(
            command, stdin=subprocess.PIPE, stderr=subprocess.PIPE
        ) as proc:
            # Should never happen, but mypy/pyright makes noise.
            assert proc.stdin is not None
            assert proc.stderr is not None

            while True:
                data = source.read(chunk_size)
                if not data:
                    break

                proc.stdin.write(data)

            # Close stdin before reading stderr, otherwise read() will hang
            # because process is waiting for more data.
            proc.stdin.close()

            # Take one read of stderr in case there is anything useful
            # for debugging an error.
            stderr = proc.stderr.read()

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
            all mounts will be removed from the named instance.

        :raises MultipassError: On error.
        """
        command = ["umount", mount]

        try:
            self._run(command)
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief=f"Failed to unmount {mount!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def wait_until_ready(
        self, *, timeout: Optional[float] = None
    ) -> Tuple[str, Optional[str]]:
        """Wait until Multipass is ready (upon install/startup).

        :param timeout: Timeout in seconds.

        :returns: Tuple of parsed versions (multipass, multipassd).  multipassd
            may be None if Multipass is not ready and the timeout limit is reached.
        """
        if timeout is not None:
            deadline: Optional[float] = time.time() + timeout
        else:
            deadline = None

        while True:
            multipass_version, multipassd_version = self.version()

            if multipassd_version is not None:
                return (multipass_version, multipassd_version)

            if deadline is not None and time.time() >= deadline:
                break

            time.sleep(RETRY_WAIT)

        raise MultipassError(
            brief="Timed out waiting for Multipass to become ready.",
        )

    def version(self) -> Tuple[str, Optional[str]]:
        """Get multipass and multipassd versions.

        :returns: Tuple of parsed versions (multipass, multipassd).  multipassd
                  may be None if Multipass is not yet ready.
        """
        try:
            proc = self._run(["version"])
        except subprocess.CalledProcessError as error:
            raise MultipassError(
                brief="Failed to check version.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            output = proc.stdout.decode(encoding=locale.getpreferredencoding())
        except UnicodeDecodeError as error:
            raise MultipassError(
                brief="Failed to check version.",
                details=f"Failed to decode output: {proc.stdout!r}",
            ) from error

        # Expected multipass version output should look like:
        # * Scenario 1: multipassd not yet ready
        #
        #   multipass: 1.5.0
        #
        # * Scenario 2: typical Linux
        #
        #   multipass: 1.5.0
        #   multipassd: 1.5.0
        #
        # * Scenario 3: typical Mac
        #
        #   multipass: 1.5.0+mac
        #   multipassd: 1.5.0+mac
        #
        # * Scenario 4: typical Windows
        #
        #   multipass: 1.5.0+win
        #   multipassd: 1.5.0+win
        #
        # * Scenario 5: outdated Windows version with notice message
        #   See: https://github.com/canonical/multipass/issues/2020
        #
        #   multipass: 1.5.0+win
        #   multipassd: 1.5.0+win
        #
        #   SOME NOTICE INFORMATION....
        #
        # After stripping and splitting:
        #    - ['multipass', '1.5.0'] # noqa: ERA001
        #    - ['multipass', '1.5.0', 'multipassd', '1.5.0'] # noqa: ERA001
        #    - ['multipass', '1.5.0+mac', 'multipassd', '1.5.0+mac'] # noqa: ERA001
        #    - ['multipass', '1.5.0+win', 'multipassd', '1.5.0+win'] # noqa: ERA001
        #    - ['multipass', '1.5.0+win', 'multipassd', '1.5.0+win', ...] # noqa: ERA001
        output_split = output.strip().split()
        if len(output_split) < 2 or output_split[0] != "multipass":
            raise MultipassError(
                brief=f"Unable to parse version output: {proc.stdout!r}",
            )

        multipass_version = output_split[1].split("+")[0]

        if len(output_split) >= 4 and output_split[2] == "multipassd":
            multipassd_version = output_split[3].split("+")[0]
        else:
            multipassd_version = None

        return (multipass_version, multipassd_version)
