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

import shutil
import sys
from unittest import mock

import pytest
from craft_providers import multipass

# Shortcut any calls to time.sleep with pytest-time's instant_sleep
pytestmark = pytest.mark.usefixtures("instant_sleep")


@pytest.fixture
def mock_details_from_process_error():
    details = "<details>"
    with mock.patch(
        "craft_providers.multipass.installer.details_from_called_process_error",
        return_value=details,
    ) as mock_details:
        yield mock_details


def test_install_darwin(fake_process, monkeypatch, mock_instant_sleep):
    monkeypatch.setattr(sys, "platform", "darwin")

    fake_process.register_subprocess(["brew", "install", "multipass"])
    fake_process.register_subprocess(["multipass", "set", "local.driver=qemu"])
    fake_process.register_subprocess(
        ["multipass", "version"], stdout="multipass 1.4.2\nmultipassd 1.4.2\n"
    )

    multipass.install()

    assert list(fake_process.calls) == [
        ["brew", "install", "multipass"],
        ["multipass", "set", "local.driver=qemu"],
        ["multipass", "version"],
    ]
    mock_instant_sleep.sleep.assert_called_with(20)


def test_install_darwin_error(
    fake_process, mock_details_from_process_error, monkeypatch
):
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_process.register_subprocess(
        ["brew", "install", "multipass"],
        returncode=1,
    )

    with pytest.raises(multipass.MultipassInstallationError) as exc_info:
        multipass.install()

    assert exc_info.value == multipass.MultipassInstallationError(
        reason="error during brew installation",
        details=mock_details_from_process_error.return_value,
    )


def test_install_linux(fake_process, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    fake_process.register_subprocess(["sudo", "snap", "install", "multipass"])
    fake_process.register_subprocess(
        ["multipass", "version"], stdout="multipass 1.4.2\nmultipassd 1.4.2\n"
    )

    multipass.install()

    assert list(fake_process.calls) == [
        ["sudo", "snap", "install", "multipass"],
        ["multipass", "version"],
    ]


def test_install_linux_error(
    fake_process, mock_details_from_process_error, monkeypatch
):
    monkeypatch.setattr(sys, "platform", "linux")
    fake_process.register_subprocess(
        ["sudo", "snap", "install", "multipass"],
        returncode=1,
    )

    with pytest.raises(multipass.MultipassInstallationError) as exc_info:
        multipass.install()

    assert exc_info.value == multipass.MultipassInstallationError(
        reason="error during snap installation",
        details=mock_details_from_process_error.return_value,
    )


def test_install_windows_error(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    with pytest.raises(multipass.MultipassInstallationError) as exc_info:
        multipass.install()

    assert exc_info.value == multipass.MultipassInstallationError(
        reason="automated installation not yet supported for Windows",
    )


@pytest.mark.parametrize(
    ("which", "is_installed"), [("/path/to/multipass", True), (None, False)]
)
def test_is_installed(which, is_installed, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: which)

    assert multipass.is_installed() == is_installed
