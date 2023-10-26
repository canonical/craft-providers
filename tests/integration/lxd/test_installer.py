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

import pytest
from craft_providers import lxd


def test_is_initialized(installed_lxd):
    assert lxd.is_initialized(lxc=lxd.LXC(), remote="local") is True


def test_is_initialized_false(installed_lxd_without_init):
    assert lxd.is_initialized(lxc=lxd.LXC(), remote="local") is False


def test_is_installed():
    expected = shutil.which("lxd") is not None

    assert lxd.is_installed() is expected


def test_install(uninstalled_lxd):
    assert lxd.is_installed() is False

    lxd_version = lxd.install()

    assert lxd.is_installed() is True
    assert lxd_version is not None


def test_ensure_lxd_is_ready(installed_lxd_without_init):
    with pytest.raises(lxd.LXDError) as exc_info:
        lxd.ensure_lxd_is_ready()

    assert exc_info.value == lxd.LXDError(
        brief="LXD has not been properly initialized.",
        details=(
            "The default LXD profile is empty or does not contain a disk device with "
            "a path of '/'."
        ),
        resolution="Execute 'lxd init --auto' to initialize LXD.\n"
        "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/ for "
        "instructions on installing and configuring LXD for your operating system.",
    )
