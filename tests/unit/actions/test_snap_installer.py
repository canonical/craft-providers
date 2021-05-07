# Copyright 2021 Canonical Ltd.
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

from unittest import mock

import pytest
import requests

from craft_providers.actions import snap_installer
from craft_providers.errors import details_from_called_process_error


@pytest.fixture()
def mock_requests():
    """Mock requests_unixsocket."""
    with mock.patch(
        "craft_providers.actions.snap_installer.requests_unixsocket"
    ) as mock_requests:
        yield mock_requests


@pytest.fixture()
def mock_temp_dir():
    """Mock tempfile.TemporaryDirectory, setting default value to '/fake-tmp'."""
    with mock.patch("tempfile.TemporaryDirectory") as mock_temp_dir:
        mock_temp_dir.return_value.__enter__.return_value = "/fake-tmp"
        yield mock_temp_dir


def test_inject_from_host_classic(mock_requests, fake_executor, fake_process):
    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--classic",
            "--dangerous",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=True
    )

    assert mock_requests.mock_calls == [
        mock.call.get("http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"),
        mock.call.get().raise_for_status(),
        mock.call.get().iter_content(65536),
        mock.call.get().iter_content().__iter__(),
    ]

    assert len(fake_process.calls) == 2


def test_inject_from_host_strict(mock_requests, fake_executor, fake_process):
    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--dangerous",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=False
    )

    assert mock_requests.mock_calls == [
        mock.call.get("http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"),
        mock.call.get().raise_for_status(),
        mock.call.get().iter_content(65536),
        mock.call.get().iter_content().__iter__(),
    ]

    assert len(fake_process.calls) == 2


def test_inject_from_host_snapd_connection_error_using_pack_fallback(
    mock_requests, mock_temp_dir, fake_executor, fake_process
):
    mock_requests.get.side_effect = requests.exceptions.ConnectionError()

    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "pack",
            "/snap/test-name/current/",
            "--filename=/fake-tmp/test-name.snap",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--dangerous",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=False
    )

    assert mock_requests.mock_calls == [
        mock.call.get("http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"),
    ]
    assert len(fake_process.calls) == 3


def test_inject_from_host_snapd_http_error_using_pack_fallback(
    mock_requests, mock_temp_dir, fake_executor, fake_process
):
    mock_requests.get.return_value.raise_for_status.side_effect = (
        requests.exceptions.HTTPError()
    )
    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "pack",
            "/snap/test-name/current/",
            "--filename=/fake-tmp/test-name.snap",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--dangerous",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=False
    )

    assert mock_requests.mock_calls == [
        mock.call.get("http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"),
        mock.call.get().raise_for_status(),
    ]

    assert len(fake_process.calls) == 3


def test_inject_from_host_install_failure(mock_requests, fake_executor, fake_process):
    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--dangerous",
        ],
        returncode=1,
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.inject_from_host(
            executor=fake_executor, snap_name="test-name", classic=False
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="Failed to inject snap 'test-name'.",
        details=details_from_called_process_error(exc_info.value.__cause__),  # type: ignore
    )

    assert len(fake_process.calls) == 2


def test_install_from_store_strict(fake_executor, fake_process):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "download",
            "test-name",
            "--channel=test-chan",
            "--basename=test-name",
            "--target-directory=/tmp",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--dangerous",
        ],
    )

    snap_installer.install_from_store(
        executor=fake_executor,
        snap_name="test-name",
        classic=False,
        channel="test-chan",
    )

    assert len(fake_process.calls) == 2


def test_install_from_store_classic(fake_executor, fake_process):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "download",
            "test-name",
            "--channel=test-chan",
            "--basename=test-name",
            "--target-directory=/tmp",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--classic",
            "--dangerous",
        ],
    )

    snap_installer.install_from_store(
        executor=fake_executor, snap_name="test-name", classic=True, channel="test-chan"
    )

    assert len(fake_process.calls) == 2


def test_install_from_store_failure(fake_executor, fake_process):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "download",
            "test-name",
            "--channel=test-chan",
            "--basename=test-name",
            "--target-directory=/tmp",
        ],
        returncode=1,
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.install_from_store(
            executor=fake_executor,
            snap_name="test-name",
            classic=True,
            channel="test-chan",
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="Failed to install snap 'test-name'.",
        details=details_from_called_process_error(exc_info.value.__cause__),  # type: ignore
    )
