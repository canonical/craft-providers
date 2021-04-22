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

import os
import shutil
import sys

import pytest

from craft_providers.lxd import LXDInstallationError, install, is_installed


@pytest.mark.parametrize("platform", ["win32", "darwin", "other"])
def test_install_unsupported_platform(mocker, platform):
    mocker.patch.object(sys, "platform", platform)

    with pytest.raises(LXDInstallationError) as exc_info:
        install()

    assert exc_info.value == LXDInstallationError(
        f"unsupported platform {sys.platform!r}"
    )


def test_install_without_sudo(fake_process, mocker):
    mocker.patch.object(sys, "platform", "linux")
    mocker.patch.object(os, "geteuid", lambda: 0, create=True)
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


def test_install_with_sudo(fake_process, mocker):
    mocker.patch.object(sys, "platform", "linux")
    mocker.patch.object(os, "geteuid", lambda: 1000, create=True)
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


def test_install_requires_sudo(mocker):
    mocker.patch.object(sys, "platform", "linux")
    mocker.patch.object(os, "geteuid", lambda: 1000, create=True)

    with pytest.raises(LXDInstallationError) as exc_info:
        install(sudo=False)

    assert exc_info.value == LXDInstallationError(
        "sudo required if not running as root"
    )


@pytest.mark.parametrize("which,installed", [("/path/to/lxd", True), (None, False)])
def test_is_installed(which, installed, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: which)

    assert is_installed() == installed
