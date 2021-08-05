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
import shutil
import sys
from unittest import mock

import pytest

from craft_providers.lxd import (
    LXC,
    LXDError,
    LXDInstallationError,
    install,
    installer,
    is_initialized,
    is_installed,
    is_user_permitted,
)

if sys.platform == "linux":
    import grp


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
def mock_grp():
    with mock.patch.object(
        installer,
        "grp",
        create=True,
    ) as mock_grp:
        mock_grp.getgrgid.return_value = []
        yield mock_grp


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
    mock_lxc = mock.Mock(spec=LXC)

    is_initialized(lxc=mock_lxc, remote="some-remote")

    assert mock_lxc.mock_calls == [
        mock.call.profile_show(profile="default", remote="some-remote"),
        mock.call.profile_show().get("devices"),
    ]


@pytest.mark.parametrize("which,installed", [("/path/to/lxd", True), (None, False)])
def test_is_installed(which, installed, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: which)

    assert is_installed() == installed


def test_is_user_permitted_root(mock_os_geteuid, mock_os_getgroups):
    mock_os_geteuid.return_value = 0

    assert is_user_permitted() is True


@pytest.mark.skipif(sys.platform != "linux", reason=f"unsupported on {sys.platform}")
def test_is_user_permitted_lxd_group(mock_os_geteuid, mock_os_getgroups, mock_grp):
    mock_os_getgroups.return_value = [1, 2, 3]
    mock_grp.getgrgid.side_effect = (
        lambda g: grp.struct_group(["lxd", "x", g, []])  # type: ignore
        if g == 2
        else grp.struct_group([f"group-{g}", "x", g, []])  # type: ignore
    )

    assert is_user_permitted() is True


@pytest.mark.skipif(sys.platform != "linux", reason=f"unsupported on {sys.platform}")
def test_is_user_permitted_failure(mock_os_geteuid, mock_os_getgroups, mock_grp):
    mock_os_getgroups.return_value = [1, 2, 3]
    mock_grp.getgrgid.side_effect = lambda g: grp.struct_group(
        ["not-lxd-group", "x", g, []]
    )  # type: ignore

    assert is_user_permitted() is False


def test_ensure_lxd_is_ready_not_installed(
    mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_is_installed.return_value = False

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready()

    assert exc_info.value == LXDError(
        brief="LXD is required, but not installed.",
        resolution="Visit https://snapcraft.io/lxd for instructions "
        "on how to install the LXD snap for your distribution.",
    )


def test_ensure_lxd_is_ready_not_minimum_version(
    fake_process, mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    fake_process.keep_last_process(True)
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout="3.12",
    )

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready()

    assert exc_info.value == LXDError(
        brief="LXD '3.12' does not meet the minimum required version '4.0'.",
        resolution="Visit https://snapcraft.io/lxd for instructions "
        "on how to install the LXD snap for your distribution.",
    )


def test_ensure_lxd_is_ready_not_permitted(
    mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_is_user_permitted.return_value = False

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready()

    assert exc_info.value == LXDError(
        brief="LXD requires additional permissions.",
        resolution="Ensure that the user is in the 'lxd' group.",
    )


def test_ensure_lxd_is_ready_not_initialized(
    mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    mock_is_initialized.return_value = False

    with pytest.raises(LXDError) as exc_info:
        installer.ensure_lxd_is_ready()

    assert exc_info.value == LXDError(
        brief="LXD has not been properly initialized.",
        resolution="Execute 'lxd init --auto' to initialize LXD.",
    )


def test_ensure_lxd_is_ready_ok(
    mock_is_installed, mock_is_user_permitted, mock_is_initialized
):
    installer.ensure_lxd_is_ready()
