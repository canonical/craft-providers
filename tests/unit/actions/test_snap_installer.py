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

import json
import pathlib
import subprocess
import textwrap
from unittest import mock

import pytest
import requests
import yaml
from craft_providers.actions import snap_installer
from craft_providers.actions.snap_installer import Snap
from craft_providers.errors import (
    BaseConfigurationError,
    ProviderError,
    details_from_called_process_error,
)
from craft_providers.instance_config import InstanceConfiguration
from logassert import Exact  # type: ignore


@pytest.fixture
def mock_requests():
    """Mock requests_unixsocket."""
    with mock.patch(
        "craft_providers.actions.snap_installer.requests_unixsocket"
    ) as mock_requests:
        yield mock_requests


@pytest.fixture(params=["1"])
def config_fixture(fake_home_temporary_file, request):
    """Creates an instance config file in the pytest temp directory.

    Patches the temp_paths functions to point to the
    temporary directory containing the config.

    :param request: The revision of the target's snap. Default revision = 1.
    """
    config_content = textwrap.dedent(
        f"""\
        compatibility_tag: tag-foo-v2
        snaps:
          test-name:
            revision: '{request.param}'
            source: {snap_installer.SNAP_SRC_HOST}
        """
    )

    fake_home_temporary_file.write_text(config_content)


@pytest.fixture(params=[{"revision": "2", "id": "3", "publisher": {"id": "4"}}])
def mock_get_host_snap_info(request, mocker):
    """Mocks the get_host_snap_revision() function

    :param request: The revision of the host's snap. Default revision = 2.
    """
    mockee = "craft_providers.actions.snap_installer.get_host_snap_info"
    if isinstance(request.param, Exception):
        mocker.patch(mockee, side_effect=request.param)
    else:
        mocker.patch(mockee, return_value=request.param)


@pytest.fixture(params=["3"])
def mock_get_snap_revision_ensuring_source(request, mocker):
    """Mocks the _get_snap_revision_ensuring_source() function

    :param request: The revision of the snap. Default revision = 3.
    """
    mocker.patch(
        "craft_providers.actions.snap_installer._get_snap_revision_ensuring_source",
        return_value=request.param,
    )


@pytest.fixture(params=["4"])
def mock_get_target_snap_revision_from_snapd(request, mocker):
    """Mocks the _get_target_snap_revision_from_snapd() function

    :param request: The revision of the snap. Default revision = 4.
    """
    mocker.patch(
        "craft_providers.actions.snap_installer._get_target_snap_revision_from_snapd",
        return_value=request.param,
    )


def test_inject_from_host_classic(
    config_fixture,
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
    tmp_path,
):
    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "ack",
            "/tmp/test-name.assert",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--classic",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=True
    )

    mock_requests.get.assert_called_with(
        "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"
    )

    assert len(fake_process.calls) == 6
    assert Exact("Installing snap 'test-name' from host (classic=True)") in logs.debug
    assert "Revisions found: host='2', target='1'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "2",
        "source": snap_installer.SNAP_SRC_HOST,
    }


def test_inject_from_host_strict(
    config_fixture,
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
    tmp_path,
):
    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "ack",
            "/tmp/test-name.assert",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=False
    )

    mock_requests.get.assert_called_with(
        "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"
    )

    assert len(fake_process.calls) == 6
    assert Exact("Installing snap 'test-name' from host (classic=False)") in logs.debug
    assert "Revisions found: host='2', target='1'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "2",
        "source": snap_installer.SNAP_SRC_HOST,
    }


def test_inject_from_host_snap_name(
    config_fixture,
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
    tmp_path,
):
    """Inject a snap installed locally with the `--name` parameter."""
    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])
    fake_process.register_subprocess(
        ["fake-executor", "snap", "ack", "/tmp/test-name.assert"]
    )
    fake_process.register_subprocess(
        ["fake-executor", "snap", "install", "/tmp/test-name.snap"]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name_suffix", classic=False
    )

    mock_requests.get.assert_called_with(
        "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name_suffix/file"
    )
    assert len(fake_process.calls) == 6
    assert (
        Exact(
            "Installing snap 'test-name_suffix' from host as 'test-name' in instance "
            "(classic=False)."
        )
        in logs.debug
    )
    assert "Revisions found: host='2', target='1'" in logs.debug
    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "2",
        "source": snap_installer.SNAP_SRC_HOST,
    }


def test_inject_from_host_snap_name_with_base(
    config_fixture,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
    tmp_path,
    mocker,
):
    """Inject a snap and its base installed locally with the `--name` parameter."""
    # register 'snap known' calls
    fake_process.register_subprocess(
        ["snap", "known", fake_process.any()], occurrences=8
    )
    fake_process.register_subprocess(
        ["fake-executor", "snap", "ack", "/tmp/coreXX.assert"]
    )
    fake_process.register_subprocess(
        ["fake-executor", "snap", "ack", "/tmp/test-name.assert"]
    )
    fake_process.register_subprocess(
        ["fake-executor", "snap", "install", "/tmp/coreXX.snap"]
    )
    fake_process.register_subprocess(
        ["fake-executor", "snap", "install", "/tmp/test-name.snap"]
    )

    mocker.patch(
        "craft_providers.actions.snap_installer.get_host_snap_info",
        side_effect=[
            {
                "id": "",
                "name": "test-name",
                "type": "app",
                "base": "coreXX",
                "version": "0.1",
                "channel": "",
                "revision": "2",
                "publisher": {"id": ""},
                "confinement": "classic",
            },
            {
                "id": "",
                "name": "coreXX",
                "type": "base",
                "version": "0.1",
                "channel": "latest/stable",
                "revision": "1",
                "publisher": {"id": ""},
                "confinement": "strict",
            },
            {
                "id": "",
                "name": "coreXX",
                "type": "base",
                "version": "0.1",
                "channel": "latest/stable",
                "revision": "1",
                "publisher": {"id": ""},
                "confinement": "strict",
            },
            {
                "id": "",
                "name": "test-name",
                "type": "app",
                "base": "coreXX",
                "version": "0.1",
                "channel": "",
                "revision": "2",
                "publisher": {"id": ""},
                "confinement": "classic",
            },
        ],
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name_suffix", classic=False
    )

    mock_requests.get.assert_called_with(
        "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name_suffix/file"
    )
    assert len(fake_process.calls) == 12
    assert (
        "Installing base snap 'coreXX' for 'test-name_suffix' from host" in logs.debug
    )
    assert (
        Exact(
            "Installing snap 'test-name_suffix' from host as 'test-name' in instance (classic=False)."
        )
        in logs.debug
    )


@pytest.mark.parametrize("mock_get_host_snap_info", [{"revision": "x3"}], indirect=True)
def test_inject_from_host_dangerous(
    config_fixture,
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
    tmp_path,
):
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

    mock_requests.get.assert_called_with(
        "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"
    )

    assert len(fake_process.calls) == 1
    assert Exact("Installing snap 'test-name' from host (classic=False)") in logs.debug
    assert "Revisions found: host='x3', target='1'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "x3",
        "source": snap_installer.SNAP_SRC_HOST,
    }


@pytest.mark.parametrize(
    ("snap_name", "snap_instance_name"),
    [
        pytest.param("test-name", "test-name", id="non-aliased"),
        pytest.param("test-name", "test-name_suffix", id="aliased"),
    ],
)
def test_inject_from_host_not_dangerous(
    snap_instance_name,
    snap_name,
    config_fixture,
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
    tmp_path,
):
    fake_process.register_subprocess(
        [
            "snap",
            "known",
            "account-key",
            "public-key-sha3-384=BWDEoaqyr25nF5SNCvEv2v"
            "7QnM9QsfCc0PBMYD_i2NGSQ32EF2d4D0hqUel3m8ul",
        ]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "known",
            "snap-declaration",
            f"snap-name={snap_name}",
        ]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "known",
            "snap-revision",
            "snap-revision=2",
            "snap-id=3",
        ]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "known",
            "account",
            "account-id=4",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "ack",
            f"/tmp/{snap_name}.assert",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            f"/tmp/{snap_name}.snap",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name=snap_instance_name, classic=False
    )

    mock_requests.get.assert_called_with(
        f"http+unix://%2Frun%2Fsnapd.socket/v2/snaps/{snap_instance_name}/file"
    )

    assert len(fake_process.calls) == 6
    if snap_instance_name == snap_name:
        assert (
            rf"Installing snap {snap_instance_name!r} from host \(classic=False\)"
            in logs.debug
        )
    else:
        assert (
            rf"Installing snap {snap_instance_name!r} from host as {snap_name!r} in instance \(classic=False\)\."
            in logs.debug
        )
    assert "Revisions found: host='2', target='1'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps[snap_name] == {
        "revision": "2",
        "source": snap_installer.SNAP_SRC_HOST,
    }


@pytest.mark.parametrize("config_fixture", ["10"], indirect=True)
@pytest.mark.parametrize("mock_get_host_snap_info", [{"revision": "10"}], indirect=True)
def test_inject_from_host_matching_revision_no_op(
    config_fixture,
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    logs,
):
    """Injection shouldn't occur if target revision equals the host revision"""
    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=True
    )

    assert mock_requests.mock_calls == []
    assert len(fake_process.calls) == 0
    assert "Revisions found: host='10', target='10'" in logs.debug
    assert (
        "Skipping snap injection: target is already up-to-date with revision on host"
    ) in logs.debug


@pytest.mark.parametrize(
    "mock_get_host_snap_info",
    [snap_installer.SnapInstallationError("msg")],
    indirect=True,
)
def test_inject_from_host_no_snapd(mock_get_host_snap_info, fake_executor):
    """The host does not have snapd at all."""
    with pytest.raises(snap_installer.SnapInstallationError):
        snap_installer.inject_from_host(
            executor=fake_executor, snap_name="test-name", classic=False
        )


def test_inject_from_host_push_error(mock_requests, fake_executor, mocker):
    mock_executor = mock.Mock(spec=fake_executor, wraps=fake_executor)
    mock_executor.push_file.side_effect = ProviderError(brief="foo")

    mocker.patch(
        "craft_providers.actions.snap_installer.get_host_snap_info",
        side_effect=[
            {
                "id": "",
                "name": "test-name",
                "type": "app",
                "version": "0.1",
                "channel": "",
                "revision": "x1",
                "confinement": "classic",
            },
        ],
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.inject_from_host(
            executor=mock_executor, snap_name="test-name", classic=False
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="failed to copy snap file for snap 'test-name'",
        details="error copying snap file into target environment",
    )
    assert exc_info.value.__cause__ is not None


def test_inject_from_host_with_base_push_error(mock_requests, fake_executor, mocker):
    mock_executor = mock.Mock(spec=fake_executor, wraps=fake_executor)
    mock_executor.push_file.side_effect = ProviderError(brief="foo")

    mocker.patch(
        "craft_providers.actions.snap_installer.get_host_snap_info",
        side_effect=[
            {
                "id": "",
                "name": "test-name",
                "type": "app",
                "base": "coreXX",
                "version": "0.1",
                "channel": "",
                "revision": "x1",
                "confinement": "classic",
            },
            {
                "id": "",
                "name": "coreXX",
                "type": "base",
                "version": "0.1",
                "channel": "",
                "revision": "x1",
                "confinement": "strict",
            },
        ],
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.inject_from_host(
            executor=mock_executor, snap_name="test-name", classic=False
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="failed to copy snap file for snap 'coreXX'",
        details="error copying snap file into target environment",
    )
    assert exc_info.value.__cause__ is not None


def test_inject_from_host_snapd_connection_error_using_pack_fallback(
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    tmpdir,
):
    mock_requests.get.side_effect = requests.exceptions.ConnectionError()

    fake_process.register_subprocess(
        [
            "snap",
            "pack",
            "/snap/test-name/current/",
            f'--filename={pathlib.PurePosixPath(tmpdir / "test-name.snap")}',
        ]
    )
    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "ack",
            "/tmp/test-name.assert",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=False
    )

    assert mock_requests.mock_calls == [
        mock.call.get("http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"),
    ]
    assert len(fake_process.calls) == 7


def test_inject_from_host_snapd_http_error_using_pack_fallback(
    mock_get_host_snap_info,
    mock_requests,
    fake_executor,
    fake_process,
    tmpdir,
):
    mock_requests.get.return_value.raise_for_status.side_effect = (
        requests.exceptions.HTTPError()  # type: ignore [reportGeneralTypeIssues]
    )
    fake_process.register_subprocess(
        [
            "snap",
            "pack",
            "/snap/test-name/current/",
            f'--filename={pathlib.PurePosixPath(tmpdir / "test-name.snap")}',
        ]
    )
    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "ack",
            "/tmp/test-name.assert",
        ]
    )
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
        ]
    )

    snap_installer.inject_from_host(
        executor=fake_executor, snap_name="test-name", classic=False
    )

    assert mock_requests.mock_calls == [
        mock.call.get("http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-name/file"),
        mock.call.get().raise_for_status(),
    ]

    assert len(fake_process.calls) == 7


def test_inject_from_host_install_failure(
    mock_requests, fake_executor, fake_process, mocker
):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "/tmp/test-name.snap",
            "--dangerous",
        ],
        stdout="snap error",
        stderr="snap error details",
        returncode=1,
    )

    mocker.patch(
        "craft_providers.actions.snap_installer.get_host_snap_info",
        side_effect=[
            {
                "id": "",
                "name": "test-name",
                "type": "app",
                "version": "0.1",
                "channel": "",
                "revision": "x1",
                "confinement": "classic",
            },
        ],
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.inject_from_host(
            executor=fake_executor, snap_name="test-name", classic=False
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="failed to install snap 'test-name'",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )

    assert len(fake_process.calls) == 1


@pytest.mark.parametrize(
    "mock_get_snap_revision_ensuring_source", [None], indirect=True
)
def test_install_from_store_strict(
    config_fixture,
    mock_get_snap_revision_ensuring_source,
    fake_executor,
    fake_process,
    logs,
    mock_get_target_snap_revision_from_snapd,
):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "test-name",
            "--channel",
            "test-chan",
        ],
    )

    snap_installer.install_from_store(
        executor=fake_executor,
        snap_name="test-name_suffix",
        classic=False,
        channel="test-chan",
    )

    assert len(fake_process.calls) == 1
    assert (
        Exact(
            "Installing snap 'test-name_suffix' as 'test-name' from store "
            "(channel='test-chan', classic=False).",
        )
        in logs.debug
    )
    assert "Revision found in target: None" in logs.debug
    assert "Revision after install/refresh: '4'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "4",
        "source": snap_installer.SNAP_SRC_STORE,
    }


@pytest.mark.parametrize(
    "mock_get_snap_revision_ensuring_source", [None], indirect=True
)
def test_install_from_store_classic(
    config_fixture,
    mock_get_snap_revision_ensuring_source,
    fake_executor,
    fake_process,
    logs,
    mock_get_target_snap_revision_from_snapd,
):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "test-name",
            "--channel",
            "test-chan",
            "--classic",
        ],
    )

    snap_installer.install_from_store(
        executor=fake_executor, snap_name="test-name", classic=True, channel="test-chan"
    )

    assert len(fake_process.calls) == 1
    assert (
        Exact(
            "Installing snap 'test-name' from store "
            "(channel='test-chan', classic=True)."
        )
        in logs.debug
    )
    assert "Revision found in target: None" in logs.debug
    assert "Revision after install/refresh: '4'" in logs.debug


def test_refresh_from_store(
    config_fixture,
    mock_get_snap_revision_ensuring_source,
    fake_executor,
    fake_process,
    logs,
    mock_get_target_snap_revision_from_snapd,
):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "refresh",
            "test-name",
            "--channel",
            "test-chan",
        ],
    )

    snap_installer.install_from_store(
        executor=fake_executor,
        snap_name="test-name",
        classic=False,
        channel="test-chan",
    )

    assert len(fake_process.calls) == 1
    assert (
        Exact(
            "Installing snap 'test-name' from store"
            " (channel='test-chan', classic=False)."
        )
        in logs.debug
    )
    assert "Revision found in target: '3'" in logs.debug
    assert "Revision after install/refresh: '4'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "4",
        "source": snap_installer.SNAP_SRC_STORE,
    }


def test_install_from_store_failure(
    config_fixture, mock_get_snap_revision_ensuring_source, fake_executor, fake_process
):
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "refresh",
            "test-name",
            "--channel",
            "test-chan",
        ],
        stdout="snap error",
        stderr="snap error details",
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
        brief="Failed to install/refresh snap 'test-name'.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.parametrize(
    "mock_get_snap_revision_ensuring_source", [None], indirect=True
)
def test_install_from_store_trim_suffix(
    config_fixture,
    mock_get_snap_revision_ensuring_source,
    fake_executor,
    fake_process,
    logs,
    mock_get_target_snap_revision_from_snapd,
):
    """Trim the `_name` suffix from the snap name, if present."""
    fake_process.register_subprocess(
        [
            "fake-executor",
            "snap",
            "install",
            "test-name",
            "--channel",
            "test-chan",
        ],
    )

    snap_installer.install_from_store(
        executor=fake_executor,
        snap_name="test-name",
        classic=False,
        channel="test-chan",
    )

    assert len(fake_process.calls) == 1
    assert (
        Exact(
            "Installing snap 'test-name' from store"
            " (channel='test-chan', classic=False)."
        )
        in logs.debug
    )
    assert "Revision found in target: None" in logs.debug
    assert "Revision after install/refresh: '4'" in logs.debug

    # check saved config
    (saved_config_record,) = (
        x
        for x in fake_executor.records_of_push_file_io
        if "craft-instance.conf" in x["destination"]
    )
    config = InstanceConfiguration(**yaml.safe_load(saved_config_record["content"]))
    assert config.snaps is not None
    assert config.snaps["test-name"] == {
        "revision": "4",
        "source": snap_installer.SNAP_SRC_STORE,
    }


# -- tests for the helping functions


def test_get_host_snap_info_ok(responses):
    """Revision retrieved ok."""
    snap_info = {"result": {"revision": "15"}}
    responses.add(
        responses.GET,
        "http+unix://%2Frun%2Fsnapd.socket/v2/snaps/test-snap",
        json=snap_info,
    )
    result = snap_installer.get_host_snap_info("test-snap")["revision"]
    assert result == "15"


def test_get_host_snap_info_connection_error(responses):
    """Error when connecting to snapd.

    Note that nothing is added to responses, so ConnectionError will be raised when
    trying to connect, which is the effect we want.
    """
    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer.get_host_snap_info("test-snap")
    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="Unable to connect to snapd service."
    )
    assert exc_info.value.__cause__ is not None


def test_get_assertion_connection_error(mocker):
    """Raise SnapInstallation when 'snap known' call fails."""
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            100, ["error"], output="snap error", stderr="snap error details"
        ),
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer._get_assertion(["test1", "test2"])
    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="failed to get assertions for snap",
        details="* Command that failed: 'error'\n* Command exit code: 100\n* Command output: 'snap error'\n* Command standard error output: 'snap error details'",
    )
    assert exc_info.value.__cause__ is not None


def test_add_assertions_from_host_error_on_push(
    fake_executor, fake_process, mock_requests, mocker, tmpdir
):
    """Raise SnapInstallationError when assert file cannot be pushed."""
    mock_executor = mock.Mock(spec=fake_executor, wraps=fake_executor)
    mock_executor.push_file.side_effect = ProviderError(brief="foo")

    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer._add_assertions_from_host(
            executor=mock_executor,
            snap_name="test-name",
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="failed to copy assert file for snap 'test-name'",
        details="error copying snap assert file into target environment",
    )
    assert exc_info.value.__cause__ is not None
    assert len(fake_process.calls) == 4


def test_add_assertions_from_host_error_on_ack(
    fake_executor, fake_process, mock_requests
):
    """Raise SnapInstallationError when 'snap ack' fails."""
    fake_process.register_subprocess(
        ["fake-executor", "snap", "ack", "/tmp/test-name.assert"],
        stdout="snap error",
        stderr="snap error details",
        returncode=1,
    )

    # register 'snap known' calls
    for _ in range(4):
        fake_process.register_subprocess(["snap", "known", fake_process.any()])

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer._add_assertions_from_host(
            executor=fake_executor, snap_name="test-name"
        )

    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="failed to add assertions for snap 'test-name'",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )

    assert len(fake_process.calls) == 5


def test_get_target_snap_revision_from_snapd_process_error(fake_process, fake_executor):
    """Error when running curl to get info from snapd in target environment."""
    expected_cmd = [
        "fake-executor",
        "curl",
        "--silent",
        "--unix-socket",
        "/run/snapd.socket",
        "http://localhost/v2/snaps/test-snap",
    ]
    fake_process.register_subprocess(
        expected_cmd, stdout="snap error", stderr="snap error details", returncode=1
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer._get_target_snap_revision_from_snapd("test-snap", fake_executor)
    assert exc_info.value == snap_installer.SnapInstallationError(
        "Unable to get target snap revision.",
        details="* Command that failed: 'fake-executor curl --silent --unix-socket /run/snapd.socket http://localhost/v2/snaps/test-snap'\n* Command exit code: 1\n* Command output: b'snap error'\n* Command standard error output: b'snap error details'",
    )
    assert exc_info.value.__cause__ is not None


def test_get_target_snap_revision_from_snapd_ok(fake_process, fake_executor):
    """Proper info retrieved ok."""
    expected_cmd = [
        "fake-executor",
        "curl",
        "--silent",
        "--unix-socket",
        "/run/snapd.socket",
        "http://localhost/v2/snaps/test-snap",
    ]
    fake_snapd_response = json.dumps({"status-code": 200, "result": {"revision": "17"}})
    fake_process.register_subprocess(expected_cmd, stdout=fake_snapd_response)

    result = snap_installer._get_target_snap_revision_from_snapd(
        "test-snap", fake_executor
    )
    assert result == "17"


def test_get_target_snap_revision_from_snapd_not_found(fake_process, fake_executor):
    """The requested snap is not found in target's snapd."""
    expected_cmd = [
        "fake-executor",
        "curl",
        "--silent",
        "--unix-socket",
        "/run/snapd.socket",
        "http://localhost/v2/snaps/test-snap",
    ]
    fake_snapd_response = {"status-code": 404}
    fake_process.register_subprocess(
        expected_cmd, stdout=json.dumps(fake_snapd_response)
    )

    result = snap_installer._get_target_snap_revision_from_snapd(
        "test-snap", fake_executor
    )
    assert result is None


def test_get_target_snap_revision_from_snapd_unknown(fake_process, fake_executor):
    """The target's snapd returns an unknown response."""
    expected_cmd = [
        "fake-executor",
        "curl",
        "--silent",
        "--unix-socket",
        "/run/snapd.socket",
        "http://localhost/v2/snaps/test-snap",
    ]
    fake_snapd_response = {"status-code": 666}
    fake_process.register_subprocess(
        expected_cmd, stdout=json.dumps(fake_snapd_response)
    )

    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer._get_target_snap_revision_from_snapd("test-snap", fake_executor)
    assert exc_info.value == snap_installer.SnapInstallationError(
        f"Unknown response from snapd: {fake_snapd_response!r}"
    )


def test_get_snap_revision_ensuring_source_ok(config_fixture, fake_executor):
    """Snap is available being installed by specified source."""
    result = snap_installer._get_snap_revision_ensuring_source(
        "test-name", snap_installer.SNAP_SRC_HOST, fake_executor
    )
    assert result == "1"


@pytest.mark.parametrize(
    "fake_config",
    [
        None,
        InstanceConfiguration(snaps=None),
        InstanceConfiguration(snaps={"othersnap": {"revision": "1000"}}),
    ],
)
def test_get_snap_revision_ensuring_source_no_config(fake_config, fake_executor):
    """No config available for the indicated snap."""
    with mock.patch.object(InstanceConfiguration, "load", return_value=fake_config):
        result = snap_installer._get_snap_revision_ensuring_source(
            "test-name", snap_installer.SNAP_SRC_HOST, fake_executor
        )
    assert result is None


def test_get_snap_revision_ensuring_source_missing_source(
    fake_process, fake_executor, config_fixture
):
    """Support for instances that have old configuration and then the lib is updated."""
    fake_config = InstanceConfiguration(snaps={"test-name": {"revision": "1000"}})
    fake_process.register_subprocess(["fake-executor", "snap", "remove", "test-name"])
    with mock.patch.object(InstanceConfiguration, "load", return_value=fake_config):
        result = snap_installer._get_snap_revision_ensuring_source(
            "test-name", snap_installer.SNAP_SRC_STORE, fake_executor
        )
    assert result is None
    assert len(fake_process.calls) == 1


def test_get_snap_revision_ensuring_source_different_source_ok(
    fake_process, fake_executor, config_fixture
):
    """Snap is available but from other source; snap removal ended ok."""
    fake_process.register_subprocess(["fake-executor", "snap", "remove", "test-name"])
    result = snap_installer._get_snap_revision_ensuring_source(
        "test-name", snap_installer.SNAP_SRC_STORE, fake_executor
    )
    assert result is None
    assert len(fake_process.calls) == 1


def test_get_snap_revision_ensuring_source_different_source_error(
    fake_process, fake_executor, config_fixture
):
    """Snap is available but from other source; snap removal failed."""
    fake_process.register_subprocess(
        ["fake-executor", "snap", "remove", "test-name"],
        stdout="snap error",
        stderr="snap error details",
        returncode=1,
    )
    with pytest.raises(snap_installer.SnapInstallationError) as exc_info:
        snap_installer._get_snap_revision_ensuring_source(
            "test-name", snap_installer.SNAP_SRC_STORE, fake_executor
        )
    assert exc_info.value == snap_installer.SnapInstallationError(
        brief="Failed to remove snap 'test-name'.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )
    assert exc_info.value.__cause__ is not None


# -- tests for the Snap pydantic model


def test_snaps_no_channel_raises_errors(fake_executor):
    """Verify the Snap model raises an error when the channel is an empty string."""
    with pytest.raises(BaseConfigurationError) as exc_info:
        Snap(name="snap1", channel="")

    assert exc_info.value == BaseConfigurationError(
        brief="channel cannot be empty",
        resolution="set channel to a non-empty string or `None`",
    )
