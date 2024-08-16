#
# Copyright 2021 Canonical Ltd.
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

import os
import sys
from typing import Any, Dict
from unittest import mock
from unittest.mock import call

import pytest
from craft_providers.errors import ProviderError
from craft_providers.lxd import (
    LXC,
    LXD,
    LXDError,
    LXDInstallationError,
    install,
    installer,
    is_initialized,
    is_installed,
    is_user_permitted,
)


@pytest.fixture
def mock_is_installed():
    with mock.patch(
        "craft_providers.lxd.installer.is_installed", return_value=True
    ) as mock_is_installed:
        yield mock_is_installed


@pytest.fixture
def mock_is_user_permitted():
    with mock.patch(
        "craft_providers.lxd.installer.is_user_permitted", return_value=True
    ) as mock_is_user_permitted:
        yield mock_is_user_permitted


@pytest.fixture
def mock_is_initialized():
    with mock.patch(
        "craft_providers.lxd.installer.is_initialized", return_value=True
    ) as mock_is_initialized:
        yield mock_is_initialized


@pytest.fixture
def mock_lxd():
    mock_lxd = mock.Mock(spec=LXD)
    mock_lxd.is_supported_version.return_value = True
    mock_lxd.version.return_value = "4.4"
    mock_lxd.minimum_required_version = LXD.minimum_required_version

    return mock_lxd


@pytest.fixture
def mock_os_geteuid():
    with mock.patch.object(
        os, "geteuid", return_value=500, create=True
    ) as mock_os_geteuid:
        yield mock_os_geteuid


@pytest.fixture
def mock_os_getgroups():
    with mock.patch.object(
        os, "getgroups", return_value=[], create=True
    ) as mock_os_getgroups:
        yield mock_os_getgroups


@pytest.fixture
def mock_os_access():
    with mock.patch.object(
        os, "access", return_value=True, create=True
    ) as mock_os_access:
        yield mock_os_access


@pytest.mark.parametrize("platform", ["win32", "darwin", "other"])
def test_install_unsupported_platform(mocker, platform):
    mocker.patch.object(sys, "platform", platform)

    with pytest.raises(LXDInstallationError) as exc_info:
        install()

    assert exc_info.value == LXDInstallationError(
        f"unsupported platform {sys.platform!r}"
    )


def test_install_without_sudo(
    fake_process, mocker, mock_is_user_permitted, mock_os_geteuid
):
    mocker.patch.object(sys, "platform", "linux")
    mock_os_geteuid.return_value = 0
    fake_process.register_subprocess(
        [
            "snap",
            "install",
            "lxd",
        ]
    )
    fake_process.register_subprocess(
        [
            "lxd",
            "waitready",
        ]
    )
    fake_process.register_subprocess(
        [
            "lxd",
            "init",
            "--auto",
        ]
    )
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout="4.0",
    )

    version = install(sudo=False)

    assert version == "4.0"
    mock_is_user_permitted.assert_called_once()


def test_install_with_sudo(
    fake_process, mocker, mock_is_user_permitted, mock_os_geteuid
):
    mocker.patch.object(sys, "platform", "linux")
    fake_process.register_subprocess(
        [
            "sudo",
            "snap",
            "install",
            "lxd",
        ]
    )
    fake_process.register_subprocess(
        [
            "sudo",
            "lxd",
            "waitready",
        ]
    )
    fake_process.register_subprocess(
        [
            "sudo",
            "lxd",
            "init",
            "--auto",
        ]
    )
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout="4.0",
    )

    version = install(sudo=True)

    assert version == "4.0"
    mock_is_user_permitted.assert_called_once()


def test_install_requires_sudo(mocker, mock_is_user_permitted, mock_os_geteuid):
    mocker.patch.object(sys, "platform", "linux")

    with pytest.raises(LXDInstallationError) as exc_info:
        install(sudo=False)

    assert exc_info.value == LXDInstallationError(
        "sudo required if not running as root"
    )


@pytest.mark.skipif(sys.platform != "linux", reason=f"unsupported on {sys.platform}")
def test_install_requires_user_to_be_added_to_lxd_group(
    fake_process, mock_is_user_permitted
):
    mock_is_user_permitted.return_value = False
    fake_process.register_subprocess(
        [
            "sudo",
            "snap",
            "install",
            "lxd",
        ]
    )
    fake_process.register_subprocess(
        [
            "sudo",
            "lxd",
            "waitready",
        ]
    )
    fake_process.register_subprocess(
        [
            "sudo",
            "lxd",
            "init",
            "--auto",
        ]
    )
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout="4.0",
    )

    with pytest.raises(LXDInstallationError) as exc_info:
        install(sudo=True)

    assert exc_info.value == LXDInstallationError(
        "user must be manually added to 'lxd' group before using LXD"
    )


def test_is_initialized():
    """Return true if there is a valid disk device in the default profile."""
    mock_lxc = mock.Mock(spec=LXC)
    mock_lxc.profile_show.return_value = {
        "config": {},
        "description": "Default LXD profile",
        "devices": {
            "eth0": {
                "name": "eth0",
                "network": "lxdbr0",
                "type": "nic",
            },
            "root": {
                "path": "/",
                "pool": "default",
                "type": "disk",
            },
        },
        "name": "default",
    }

    initialized = is_initialized(lxc=mock_lxc, remote="test")

    assert initialized


def test_is_initialized_empty_profile():
    """Return false if the default profile is empty."""
    mock_lxc = mock.Mock(spec=LXC)
    mock_lxc.profile_show.return_value = {}

    initialized = is_initialized(lxc=mock_lxc, remote="test")

    assert not initialized


@pytest.mark.parametrize(
    "devices",
    [
        # no devices
        {},
        # path is not `/`
        {"root": {"path": "/foo", "pool": "default", "type": "disk"}},
        # type is not `disk`
        {"root": {"path": "/", "pool": "default", "type": "other"}},
    ],
)
def test_is_initialized_no_disk_device(devices):
    """Return false is there is not a valid disk device."""
    mock_lxc = mock.Mock(spec=LXC)
    mock_lxc.profile_show.return_value = {
        "config": {},
        "description": "Default LXD profile",
        "devices": devices,
        "name": "default",
    }

    initialized = is_initialized(lxc=mock_lxc, remote="test")

    assert not initialized


@pytest.mark.parametrize(("has_lxd_executable"), [(True), (False)])
@pytest.mark.parametrize(("has_nonsnap_socket"), [(True), (False)])
@pytest.mark.parametrize(
    ("status", "exception", "installed"),
    [
        ({"result": {"status": "active"}}, None, True),
        ({"result": {"status": "foo"}}, None, False),
        ({}, ProviderError, False),
        (None, ProviderError, False),
    ],
)
def test_is_installed(
    mocker, has_nonsnap_socket, has_lxd_executable, status, exception, installed
):
    class FakeSnapInfo:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> Dict[str, Any]:
            return status

    mock_get = mocker.patch("requests_unixsocket.get", return_value=FakeSnapInfo())
    mocker.patch("pathlib.Path.is_socket", return_value=has_nonsnap_socket)
    mocker.patch("shutil.which", return_value="lxd" if has_lxd_executable else None)

    if has_nonsnap_socket and has_lxd_executable:
        assert is_installed()
        return

    if exception:
        with pytest.raises(exception):
            is_installed()
    else:
        assert is_installed() == (installed and has_lxd_executable)

    assert mock_get.mock_calls[0] == call(
        url="http+unix://%2Frun%2Fsnapd.socket/v2/snaps/lxd",
        params={"select": "enabled"},
    )


@pytest.mark.skipif(sys.platform != "linux", reason=f"unsupported on {sys.platform}")
def test_is_user_permitted(mock_os_access):
    mock_os_access.return_value = True

    assert is_user_permitted() is True


@pytest.mark.skipif(sys.platform != "linux", reason=f"unsupported on {sys.platform}")
def test_is_user_permitted_failure(mock_os_access):
    mock_os_access.return_value = False

    assert is_user_permitted() is False


def test_ensure_lxd_is_ready_not_installed(
    mock_lxd, mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_is_installed.return_value = False

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready(lxd=mock_lxd)

    assert exc_info.value == LXDError(
        brief="LXD is required, but not installed.",
        resolution=(
            "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/ for "
            "instructions on installing and configuring LXD for your operating system."
        ),
    )


def test_ensure_lxd_is_ready_not_minimum_version(
    mock_lxd, mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_lxd.is_supported_version.return_value = False
    mock_lxd.version.return_value = "3.12"

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready(lxd=mock_lxd)

    assert exc_info.value == LXDError(
        brief="LXD '3.12' does not meet the minimum required version '4.0'.",
        resolution=(
            "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/ for "
            "instructions on installing and configuring LXD for your operating system."
        ),
    )


def test_ensure_lxd_is_ready_not_permitted(
    mock_lxd, mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_is_user_permitted.return_value = False

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready(lxd=mock_lxd)

    assert exc_info.value == LXDError(
        brief="LXD requires additional permissions.",
        resolution="Ensure that the user is in the 'lxd' group.\n"
        "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/ for "
        "instructions on installing and configuring LXD for your operating system.",
    )


def test_ensure_lxd_is_ready_not_initialized(
    mock_lxd, mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_is_initialized.return_value = False

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready(lxd=mock_lxd)

    assert exc_info.value == LXDError(
        brief="LXD has not been properly initialized.",
        details=(
            "The default LXD profile is empty or does not contain a disk device "
            "with a path of '/'."
        ),
        resolution="Execute 'lxd init --auto' to initialize LXD.\n"
        "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/ for "
        "instructions on installing and configuring LXD for your operating system.",
    )


def test_ensure_lxd_is_ready_ok(
    mock_lxd, mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    installer.ensure_lxd_is_ready(lxd=mock_lxd)
