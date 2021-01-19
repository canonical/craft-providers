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

"""Linux executor actions."""
import logging
import pathlib
import shutil
import subprocess
from time import sleep

from craft_providers import Executor

logger = logging.getLogger(__name__)


def directory_sync_from_remote(
    *,
    executor: Executor,
    source: pathlib.Path,
    destination: pathlib.Path,
    delete: bool = False,
    host_tar_cmd: str = "tar",
    target_tar_cmd: str = "tar"
) -> None:
    """Naive sync from remote using tarball.

    Relies on only the required Executor.interfaces.

    :param source: Target directory to copy from.
    :param destination: Host destination directory to copy to.
    """
    destination_path = destination.as_posix()

    if delete and destination.exists():
        shutil.rmtree(destination)

    destination.mkdir(parents=True)

    archive_proc = executor.execute_popen(
        [host_tar_cmd, "cpf", "-", "-C", source.as_posix(), "."],
        stdout=subprocess.PIPE,
    )

    target_proc = subprocess.Popen(
        [target_tar_cmd, "xpvf", "-,", "-C", destination_path],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()


def directory_sync_to_remote(
    *,
    executor: Executor,
    source: pathlib.Path,
    destination: pathlib.Path,
    delete=True,
    host_tar_cmd: str = "tar",
    target_tar_cmd: str = "tar"
) -> None:
    """Naive sync to remote using tarball.

    :param source: Host directory to copy.
    :param destination: Target destination directory to copy to.
    :param delete: Flag to delete existing destination, if exists.
    """
    destination_path = destination.as_posix()

    if delete is True:
        executor.execute_run(["rm", "-rf", destination_path], check=True)

    executor.execute_run(["mkdir", "-p", destination_path], check=True)

    archive_proc = subprocess.Popen(
        [host_tar_cmd, "cpf", "-", "-C", str(source), "."],
        stdout=subprocess.PIPE,
    )

    target_proc = executor.execute_popen(
        [target_tar_cmd, "xpvf", "-", "-C", destination_path],
        stdin=archive_proc.stdout,
    )

    # Allow archive_proc to receive a SIGPIPE if destination_proc exits.
    if archive_proc.stdout:
        archive_proc.stdout.close()

    # Waot until done.
    target_proc.communicate()


def is_target_directory(*, executor: Executor, target: pathlib.Path) -> bool:
    """Check if path is directory in executed environment.

    :param target: Path to check.

    :returns: True if directory, False otherwise.
    """
    proc = executor.execute_run(command=["test", "-d", target.as_posix()])
    return proc.returncode == 0


def is_target_file(*, executor: Executor, target: pathlib.Path) -> bool:
    """Check if path is file in executed environment.

    :param target: Path to check.

    :returns: True if file, False otherwise.
    """
    proc = executor.execute_run(command=["test", "-f", target.as_posix()])
    return proc.returncode == 0


def wait_for_system_ready(
    *, executor: Executor, retry_count=120, retry_interval: float = 0.5
) -> None:
    """Wait until system is ready as defined by sysemctl is-system-running.

    :param executor: Executor for target container.
    :param retry_count: Number of times to check systemctl.
    :param retry_interval: Time between checks to systemctl.
    """
    logger.info("Waiting for container to be ready...")
    for _ in range(retry_count):
        proc = executor.execute_run(
            command=["systemctl", "is-system-running"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        running_state = proc.stdout.decode().strip()
        if proc.returncode == 0:
            if running_state in ["running", "degraded"]:
                break

            logger.warning(
                "Unexpected state for systemctl is-system-running: %s",
                running_state,
            )

        sleep(retry_interval)
    else:
        logger.warning("System exceeded timeout to get ready.")
