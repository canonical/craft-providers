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

"""Helpers for snap commands."""

import contextlib
import json
import logging
import pathlib
import shlex
import subprocess
import urllib.parse
from typing import Any, Dict, Iterator, List, Optional

import pydantic
import requests
import requests_unixsocket  # type: ignore

from craft_providers.const import TIMEOUT_COMPLEX, TIMEOUT_SIMPLE
from craft_providers.errors import (
    BaseConfigurationError,
    ProviderError,
    details_from_called_process_error,
)
from craft_providers.executor import Executor
from craft_providers.instance_config import InstanceConfiguration
from craft_providers.util import snap_cmd, temp_paths

logger = logging.getLogger(__name__)


# possible sources for the snap (using these two constants instead
# of an enum because the values are persisted with JSON)
SNAP_SRC_HOST = "host"
SNAP_SRC_STORE = "store"


class SnapInstallationError(ProviderError):
    """Unexpected error during snap installation."""


class Snap(pydantic.BaseModel, extra="forbid"):
    """Details of snap to install in the base.

    :param name: name of snap
    :param channel: snap store channel to install from (default is stable)
      If channel is `None`, then the snap is injected from the host instead
      of being installed from the store.
    :param classic: true if snap is a classic snap (default is false)
    """

    name: str
    channel: Optional[str] = "stable"
    classic: bool = False

    @pydantic.field_validator("channel")
    def validate_channel(cls, channel):
        """Validate that channel is not an empty string.

        :raises BaseConfigurationError: if channel is empty
        """
        if channel is not None and not channel:
            raise BaseConfigurationError(
                brief="channel cannot be empty",
                resolution="set channel to a non-empty string or `None`",
            )
        return channel


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
    command = snap_cmd.formulate_pack_command(snap_name, output)

    logger.debug("Executing command on host: %s", shlex.join(command))
    subprocess.run(
        command,
        capture_output=True,
        check=True,
    )


def get_host_snap_info(snap_name: str) -> Dict[str, Any]:
    """Get info about a snap installed on the host."""
    quoted_name = urllib.parse.quote(snap_name, safe="")
    url = f"http+unix://%2Frun%2Fsnapd.socket/v2/snaps/{quoted_name}"
    try:
        snap_info = requests_unixsocket.get(url)
    except requests.exceptions.ConnectionError as error:
        raise SnapInstallationError(
            brief="Unable to connect to snapd service."
        ) from error
    snap_info.raise_for_status()
    # TODO: represent snap info in a dataclass
    return snap_info.json()["result"]


def _get_target_snap_revision_from_snapd(
    snap_name: str, executor: Executor
) -> Optional[str]:
    """Get the revision of the snap on the target."""
    quoted_name = urllib.parse.quote(snap_name, safe="")
    url = f"http://localhost/v2/snaps/{quoted_name}"
    cmd = ["curl", "--silent", "--unix-socket", "/run/snapd.socket", url]
    try:
        proc = executor.execute_run(
            cmd, check=True, capture_output=True, timeout=TIMEOUT_SIMPLE
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief="Unable to get target snap revision.",
            details=details_from_called_process_error(error),
        ) from error

    result = json.loads(proc.stdout)
    if result["status-code"] == 404:
        # snap not found
        return None
    if result["status-code"] == 200:
        return result["result"]["revision"]
    raise SnapInstallationError(f"Unknown response from snapd: {result!r}")


def _get_snap_revision_ensuring_source(
    snap_name: str, source: str, executor: Executor
) -> Optional[str]:
    """Get revision of snap on target and ensure the installation source."""
    instance_config = InstanceConfiguration.load(executor=executor)
    if instance_config is None or instance_config.snaps is None:
        return None

    config = instance_config.snaps.get(snap_name)
    if config is None:
        # not installed before
        return None

    # use 'get' to retrieve the source to support configs
    # saved by previous versions of the lib
    if config.get("source") == source:
        # previously installed from specified source: ok
        return config["revision"]

    # installed from other source: remove it
    logger.debug(
        "Snap %r installed from other source (%s), removing", snap_name, config
    )
    cmd = snap_cmd.formulate_remove_command(snap_name)
    try:
        executor.execute_run(
            cmd, check=True, capture_output=True, timeout=TIMEOUT_SIMPLE
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief=f"Failed to remove snap {snap_name!r}.",
            details=details_from_called_process_error(error),
        ) from error
    return None


@contextlib.contextmanager
def _get_host_snap(snap_name: str) -> Iterator[pathlib.Path]:
    """Get snap installed on host containing the config.

    Snapd provides an API to fetch a snap. First use that to fetch a snap.
    If the snap is installed using `snap try`, it may fail to download. In
    that case, attempt to construct the snap by packing it ourselves.

    :yields: context manager that sets the temporary snap installation file
      as the target
    """
    with temp_paths.home_temporary_directory() as tmp_dir:
        snap_path = tmp_dir / f"{snap_name}.snap"
        try:
            _download_host_snap(snap_name=snap_name, output=snap_path)
        except SnapInstallationError:
            logger.debug(
                "Failed to fetch snap from snapd,"
                " falling back to `snap pack` to recreate"
            )
            _pack_host_snap(snap_name=snap_name, output=snap_path)

        yield snap_path


def _get_assertion(query: List[str]) -> bytes:
    """Get an assertion from snapd.

    :param query: assertion query to pass to `snap known`
    :returns: assertion data
    :raises SnapInstallationError: if 'snap known' call fails
    """
    command = snap_cmd.formulate_known_command(query=query)
    logger.debug("Executing command on host: %s", command)
    try:
        return subprocess.run(command, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief="failed to get assertions for snap",
            details=details_from_called_process_error(error),
        ) from error


@contextlib.contextmanager
def _get_assertions_file(
    snap_name: str, snap_id: str, snap_revision: str, snap_publisher_id: str
) -> Iterator[pathlib.Path]:
    """Get an assertion file for a snap.

    :param snap_name: Name of snap to inject
    :param snap_id: ID of the snap
    :param snap_revision: Revision of the snap
    :param snap_publisher_id: The ID of the snap's publisher's account

    :yields: context manager that will set the temporary snap assertion file
      as the target
    """
    logger.debug("Creating an assert file for snap %r", snap_name)
    assertion_queries = [
        [
            "account-key",
            "public-key-sha3-384=BWDEoaqyr25nF5SNCvEv2v"
            "7QnM9QsfCc0PBMYD_i2NGSQ32EF2d4D0hqUel3m8ul",
        ],
        ["snap-declaration", f"snap-name={snap_name.partition('_')[0]}"],
        ["snap-revision", f"snap-revision={snap_revision}", f"snap-id={snap_id}"],
        ["account", f"account-id={snap_publisher_id}"],
    ]

    with temp_paths.home_temporary_file() as assert_file_path:
        with open(assert_file_path, "wb") as assert_file:
            for query in assertion_queries:
                assert_file.write(_get_assertion(query))
                assert_file.write(b"\n")
            assert_file.flush()
            yield assert_file_path


def _add_assertions_from_host(executor: Executor, snap_name: str) -> None:
    """Add assertions from the host into the target for a snap.

    :param executor: Executor for target
    :param snap_name: Name of snap to inject
    """
    # trim the `_name` suffix, if present
    target_assert_path = pathlib.PurePosixPath(f"/tmp/{snap_name.split('_')[0]}.assert")
    snap_info = get_host_snap_info(snap_name)

    try:
        with _get_assertions_file(
            snap_name=snap_name,
            snap_id=snap_info["id"],
            snap_revision=snap_info["revision"],
            snap_publisher_id=snap_info["publisher"]["id"],
        ) as host_assert_path:
            executor.push_file(
                source=host_assert_path,
                destination=target_assert_path,
            )
    except ProviderError as error:
        raise SnapInstallationError(
            brief=f"failed to copy assert file for snap {snap_name!r}",
            details="error copying snap assert file into target environment",
        ) from error

    try:
        executor.execute_run(
            snap_cmd.formulate_ack_command(snap_assert_path=target_assert_path),
            check=True,
            capture_output=True,
            timeout=TIMEOUT_COMPLEX,
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief=f"failed to add assertions for snap {snap_name!r}",
            details=details_from_called_process_error(error),
        ) from error


def inject_from_host(*, executor: Executor, snap_name: str, classic: bool) -> None:
    """Inject snap from host snap.

    If the snap on the host was installed with the `--name` parameter, the host snap's
    name will be formatted as `<snap_name>_<name>`. The `--name` parameter is not
    used when the snap is installed inside the instance, so the instance's snap
    name will just be `<snap_name>` (no suffix).

    :param executor: Executor for target
    :param snap_name: Name of snap to inject
    :param classic: Install in classic mode

    :raises SnapInstallationError: on failure to inject snap
    """
    # the local snap name may have a suffix if it was installed with `--name`
    snap_store_name = snap_name.split("_")[0]
    if snap_name == snap_store_name:
        logger.debug("Installing snap %r from host (classic=%s)", snap_name, classic)
    else:
        logger.debug(
            "Installing snap %r from host as %r in instance (classic=%s).",
            snap_name,
            snap_store_name,
            classic,
        )

    host_snap_info = get_host_snap_info(snap_name)
    host_snap_base = host_snap_info.get("base", None)
    if host_snap_base:
        logger.debug(
            "Installing base snap %r for %r from host", host_snap_base, snap_name
        )
        inject_from_host(executor=executor, snap_name=host_snap_base, classic=False)

    host_revision = host_snap_info["revision"]
    target_revision = _get_snap_revision_ensuring_source(
        snap_name=snap_store_name,
        source=SNAP_SRC_HOST,
        executor=executor,
    )
    logger.debug("Revisions found: host=%r, target=%r", host_revision, target_revision)

    if target_revision is not None and target_revision == host_revision:
        logger.debug(
            "Skipping snap injection:"
            " target is already up-to-date with revision on host"
        )
        return

    target_snap_path = pathlib.PurePosixPath(f"/tmp/{snap_store_name}.snap")
    is_dangerous = host_revision.startswith("x")

    if not is_dangerous:
        _add_assertions_from_host(executor=executor, snap_name=snap_name)

    with _get_host_snap(snap_name) as host_snap_path:
        try:
            executor.push_file(
                source=host_snap_path,
                destination=target_snap_path,
            )
        except ProviderError as error:
            raise SnapInstallationError(
                brief=f"failed to copy snap file for snap {snap_name!r}",
                details="error copying snap file into target environment",
            ) from error

    try:
        executor.execute_run(
            snap_cmd.formulate_local_install_command(
                classic=classic, dangerous=is_dangerous, snap_path=target_snap_path
            ),
            check=True,
            capture_output=True,
            timeout=TIMEOUT_COMPLEX,
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief=f"failed to install snap {snap_store_name!r}",
            details=details_from_called_process_error(error),
        ) from error

    InstanceConfiguration.update(
        executor=executor,
        data={
            "snaps": {
                snap_store_name: {"revision": host_revision, "source": SNAP_SRC_HOST}
            }
        },
    )


def install_from_store(
    *, executor: Executor, snap_name: str, channel: str, classic: bool
) -> None:
    """Install snap from store into target.

    Perform installation using method which prevents refreshing.

    :param executor: Executor for target.
    :param snap_name: Name of snap to install.
    :param channel: Channel to install from.
    :param classic: Install in classic mode.

    :raises SnapInstallationError: on unexpected error.
    """
    # trim the `_name` suffix, if present
    snap_store_name = snap_name.split("_")[0]
    if snap_name == snap_store_name:
        logger.debug(
            "Installing snap %r from store (channel=%r, classic=%s).",
            snap_name,
            channel,
            classic,
        )
    else:
        logger.debug(
            "Installing snap %r as %r from store (channel=%r, classic=%s).",
            snap_name,
            snap_store_name,
            channel,
            classic,
        )

    target_revision = _get_snap_revision_ensuring_source(
        snap_name=snap_store_name,
        source=SNAP_SRC_STORE,
        executor=executor,
    )
    logger.debug("Revision found in target: %r", target_revision)

    if target_revision is None:
        # no snap present in the target environment, just install it
        cmd = snap_cmd.formulate_remote_install_command(
            snap_name=snap_store_name,
            channel=channel,
            classic=classic,
        )
    else:
        # refresh the already installed snap
        cmd = snap_cmd.formulate_refresh_command(
            snap_name=snap_store_name,
            channel=channel,
        )

    try:
        executor.execute_run(
            cmd,
            check=True,
            capture_output=True,
            timeout=TIMEOUT_COMPLEX,
        )
    except subprocess.CalledProcessError as error:
        raise SnapInstallationError(
            brief=f"Failed to install/refresh snap {snap_store_name!r}.",
            details=details_from_called_process_error(error),
        ) from error

    new_target_revision = _get_target_snap_revision_from_snapd(
        snap_name=snap_store_name,
        executor=executor,
    )
    logger.debug("Revision after install/refresh: %r", new_target_revision)

    InstanceConfiguration.update(
        executor=executor,
        data={
            "snaps": {
                snap_store_name: {
                    "revision": new_target_revision,
                    "source": SNAP_SRC_STORE,
                }
            }
        },
    )
