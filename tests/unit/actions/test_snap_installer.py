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

import pathlib
import textwrap
from unittest import mock

import pytest
import requests

from craft_providers.actions import snap_installer
from craft_providers.errors import ProviderError, details_from_called_process_error


@pytest.fixture()
def mock_requests():
    """Mock requests_unixsocket."""
    with mock.patch(
        "craft_providers.actions.snap_installer.requests_unixsocket"
    ) as mock_requests:
        yield mock_requests


@pytest.fixture(params=["1"])
def config_fixture(request, tmpdir, mocker):
    """Creates an instance config file in the pytest temp directory.

    Patches the temp_paths functions to point to the temporary directory containing the config.

    :param request: The revision of the target's snap. Default revision = 1.
    """
    temp_path = pathlib.Path(tmpdir)
    config_content = textwrap.dedent(
        f"""\
        compatibility_tag: tag-foo-v1
        snaps:
          test-name:
            revision: {request.param}
        """
    )

    def config_generator():
        """Generate a fresh config file so we do not __enter__ after __exit__."""
        config_file = temp_path / "craft-instance.conf"
        config_file.write_text(config_content)
        return config_file

    mocker.patch(
        "craft_providers.bases.instance_config.temp_paths.home_temporary_file",
        side_effect=config_generator,
    )
    mocker.patch(
        "craft_providers.bases.instance_config.temp_paths.home_temporary_directory",
        return_value=temp_path,
    )


@pytest.fixture(params=["2"])
def mock_get_host_snap_revision(request, mocker):
    """Mocks the get_host_snap_revision() function

    :param request: The revision of the host's snap. Default revision = 2.
    """
    mocker.patch(
        "craft_providers.actions.snap_installer._get_host_snap_revision",
        return_value=request.param,
    )


@pytest.fixture(params=["3"])
def mock_get_store_snap_revision(request, mocker):
    """Mocks the get_store_snap_revision() function

    :param request: The revision of the store's snap. Default revision = 3.
    """
    mocker.patch(
        "craft_providers.actions.snap_installer._get_store_snap_revision",
        return_value=request.param,
    )


def test_inject_from_host_classic(
    config_fixture,
    mock_get_host_snap_revision,
    mock_requests,
    fake_executor,
    fake_process,
):

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


def test_inject_from_host_strict(
    config_fixture,
    mock_get_host_snap_revision,
    mock_requests,
    fake_executor,
    fake_process,
):
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


@pytest.mark.parametrize("config_fixture", ["10"], indirect=True)
@pytest.mark.parametrize("mock_get_host_snap_revision", ["10"], indirect=True)
def test_inject_from_host_matching_revision_no_op(
    config_fixture,
    mock_get_host_snap_revision,
    mock_requests,
    fake_executor,
    fake_process,
):
    """Injection shouldn't occur if target revision equals the host revision"""
    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=True
    )

    assert mock_requests.mock_calls == []
    assert len(fake_process.calls) == 0


def test_inject_from_push_error(
    config_fixture, mock_requests, fake_executor, fake_process
):
    mock_executor = mock.Mock(spec=fake_executor, wraps=fake_executor)
    mock_executor.push_file.side_effect = ProviderError(brief="foo")

    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.inject_from_host(
            executor=mock_executor, snap_name="test-name", classic=False
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="Failed to inject snap 'test-name'.",
        details="Error copying snap into target environment.",
    )
    assert exc_info.value.__cause__ is not None


def test_inject_from_host_snapd_connection_error_using_pack_fallback(
    config_fixture,
    mock_get_host_snap_revision,
    mock_requests,
    fake_executor,
    fake_process,
    tmpdir,
):  # pylint: disable=too-many-arguments
    mock_requests.get.side_effect = requests.exceptions.ConnectionError()

    fake_process.register_subprocess(
        ["fake-executor", "rm", "-f", "/tmp/test-name.snap"]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "pack",
            "/snap/test-name/current/",
            f'--filename={pathlib.Path(tmpdir / "test-name.snap")}',
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
    config_fixture,
    mock_get_host_snap_revision,
    mock_requests,
    fake_executor,
    fake_process,
    tmpdir,
):  # pylint: disable=too-many-arguments
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
            f'--filename={pathlib.Path(tmpdir / "test-name.snap")}',
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


def test_inject_from_host_install_failure(
    mock_requests, config_fixture, fake_executor, fake_process
):
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


def test_install_from_store_strict(
    config_fixture, mock_get_store_snap_revision, fake_executor, fake_process
):
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


def test_install_from_store_classic(
    config_fixture, mock_get_store_snap_revision, fake_executor, fake_process
):
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


def test_install_from_store_failure(
    config_fixture, mock_get_store_snap_revision, fake_executor, fake_process
):
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


@pytest.mark.parametrize("config_fixture", ["10"], indirect=True)
@pytest.mark.parametrize("mock_get_store_snap_revision", ["10"], indirect=True)
def test_install_from_store_matching_revision_no_op(
    config_fixture, mock_get_store_snap_revision, fake_executor, fake_process
):
    """Installation from store shouldn't occur if target revision equals the host revision"""
    snap_installer.install_from_store(
        executor=fake_executor, snap_name="test-name", classic=True, channel="test-chan"
    )

    assert len(fake_process.calls) == 0
