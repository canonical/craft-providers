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

"""Helpers for snap commands."""

import contextlib
import logging
import pathlib
import shlex
import subprocess
import urllib.parse
from typing import Iterator, Optional

import requests
import requests_unixsocket  # type: ignore

from craft_providers import Executor
from craft_providers.bases.instance_config import InstanceConfiguration
from craft_providers.errors import ProviderError, details_from_called_process_error
from craft_providers.util import snap_cmd, temp_paths

logger = logging.getLogger(__name__)


class SnapInstallationError(ProviderError):
    """Unexpected error during snap installation."""


def _download_host_snap(
    *, snap_name: str, output: pathlib.Path, chunk_size: int = 64 * 1024
) -> None:
    """Download the current host snap using snapd's APIs."""
    quoted_name = urllib.parse.quote(snap_name, safe="")
    url = f"http+unix://%2Frun%2Fsnapd.socket/v2/snaps/{quoted_name}/file"
    try:
        resp = requests_unixsocket.get(url)
    except requests.exceptions.ConnectionError as error:
        raise SnapInstallationError(
            brief="Unable to connect to snapd service."
        ) from error

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as error:
        raise SnapInstallationError(
            brief=f"Unable to download snap {snap_name!r} from snapd."
        ) from error

    with output.open("wb") as stream:
        for chunk in resp.iter_content(chunk_size):
            stream.write(chunk)


def _pack_host_snap(*, snap_name: str, output: pathlib.Path) -> None:
    """Pack the current host snap."""
    cmd = [
        "snap",
        "pack",
        f"/snap/{snap_name}/current/",
        f"--filename={output}",
    ]

    logger.debug("Executing command on host: %s", shlex.join(cmd))
    subprocess.run(
        cmd,
        capture_output=True,
        check=True,
    )


def _get_host_snap_revision(snap_name: str) -> str:
    """Get the revision of the snap on the host."""
    quoted_name = urllib.parse.quote(snap_name, safe="")
    url = f"http+unix://%2Frun%2Fsnapd.socket/v2/snaps/{quoted_name}"
    try:
        snap_info = requests_unixsocket.get(url)
    except requests.exceptions.ConnectionError as error:
        raise SnapInstallationError(
            brief="Unable to connect to snapd service."
        ) from error
    snap_info.raise_for_status()
    return snap_info.json()["result"]["revision"]


def _get_target_snap_revision(snap_name: str, executor: Executor) -> Optional[str]:
    """Get the revision of the snap on the target."""
    config = InstanceConfiguration.load(executor=executor)
    if config is not None and config.snaps is not None:
        snap = config.snaps.get(snap_name)
        if snap is not None:
            return str(snap.get("revision"))
    return None


def _get_store_snap_revision(snap_name: str, channel: str) -> str:
    """Get the revision of a snap from the store."""
    quoted_name = urllib.parse.quote(snap_name, safe="")
    url = f"http+unix://%2Frun%2Fsnapd.socket/v2/find?name={quoted_name}"
    try:
        snap_info = requests_unixsocket.get(url)
    except requests.exceptions.ConnectionError as error:
        raise SnapInstallationError(
            brief="Unable to connect to snapd service."
        ) from error
    snap_info.raise_for_status()
    return snap_info.json()["result"][0]["channels"][channel]["revision"]


@contextlib.contextmanager
def _get_host_snap(snap_name: str) -> Iterator[pathlib.Path]:
    """Get snap installed on host containing the config.

    Snapd provides an API to fetch a snap. First use that to fetch a snap.
    If the snap is installed using `snap try`, it may fail to download. In
    that case, attempt to construct the snap by packing it ourselves.

    :yields: Path to snap which will be cleaned up afterwards.
    """
    with temp_paths.home_temporary_directory() as tmp_dir:
        snap_path = tmp_dir / f"{snap_name}.snap"
        try:
            _download_host_snap(snap_name=snap_name, output=snap_path)
        except SnapInstallationError:
            logger.warning(
                "Failed to fetch snap from snapd, falling back to `snap pack` to recreate"
            )
            _pack_host_snap(snap_name=snap_name, output=snap_path)

        yield snap_path


def inject_from_host(*, executor: Executor, snap_name: str, classic: bool) -> None:
    """Inject snap from host snap.

    :raises SnapInstallationError: on unexpected error.
    """
    target_snap_path = pathlib.Path(f"/tmp/{snap_name}.snap")
    host_revision = _get_host_snap_revision(snap_name=snap_name)
    target_revision = _get_target_snap_revision(snap_name=snap_name, executor=executor)
    logger.debug(
        "Revisions found for snap %r: host = %r, target = %r",
        snap_name,
        host_revision,
        target_revision,
    )

    if target_revision is not None and target_revision == host_revision:
        logger.debug(
            "Skipping snap injection for snap %r: target is already up-to-date with revision on host",
            snap_name,
        )
        return

    try:
        # Clean outdated snap, if exists.
        executor.execute_run(
            ["rm", "-f", target_snap_path.as_posix()],
            check=True,
            capture_output=True,
        )

        with _get_host_snap(snap_name) as host_snap_path:
            try:
                executor.push_file(
                    source=host_snap_path,
                    destination=target_snap_path,
                )
            except ProviderError as error:
                raise SnapInstallationError(
                    brief=f"Failed to inject snap {snap_name!r}.",
                    details="Error copying snap into target environment.",
                ) from error

        executor.execute_run(
            snap_cmd.formulate_install_command(
                classic=classic, dangerous=True, snap_path=target_snap_path
            ),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief=f"Failed to inject snap {snap_name!r}.",
            details=details_from_called_process_error(error),
        ) from error

    InstanceConfiguration.update(
        executor=executor,
        data={"snaps": {snap_name: {"revision": host_revision}}},
    )


def install_from_store(
    *,
    executor: Executor,
    snap_name: str,
    channel: str,
    classic: bool,
) -> None:
    """Install snap from store into target.

    Perform installation using method which prevents refreshing.

    :param executor: Executor for target.
    :param snap_name: Name of snap to install.
    :param channel: Channel to install from.
    :param classic: Install in classic mode.

    :raises SnapInstallationError: on unexpected error.
    """
    target_snap_path = pathlib.Path(f"/tmp/{snap_name}.snap")
    store_revision = _get_store_snap_revision(snap_name=snap_name, channel=channel)
    target_revision = _get_target_snap_revision(snap_name=snap_name, executor=executor)
    logger.debug(
        "Revisions found for snap %r: store = %r, target = %r",
        snap_name,
        store_revision,
        target_revision,
    )

    if target_revision is not None and target_revision == store_revision:
        logger.debug(
            "Skipping snap store download for snap %r: target is already up-to-date with store",
            snap_name,
        )
        return

    try:
        executor.execute_run(
            [
                "snap",
                "download",
                snap_name,
                f"--channel={channel}",
                f"--basename={snap_name}",
                "--target-directory=/tmp",
            ],
            check=True,
            capture_output=True,
        )

        executor.execute_run(
            snap_cmd.formulate_install_command(
                classic=classic,
                dangerous=True,
                snap_path=target_snap_path,
            ),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief=f"Failed to install snap {snap_name!r}.",
            details=details_from_called_process_error(error),
        ) from error

    InstanceConfiguration.update(
        executor=executor,
        data={"snaps": {snap_name: {"revision": store_revision}}},
    )
