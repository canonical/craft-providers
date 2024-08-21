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


import pytest
from craft_providers.lxd import LXD


@pytest.fixture
def lxd():
    return LXD()


@pytest.mark.parametrize(
    "sudo",
    [
        pytest.param(False, id="no-sudo"),
        pytest.param(True, marks=pytest.mark.with_sudo, id="with-sudo"),
    ],
)
def test_init(lxd, sudo):
    lxd.init(auto=True, sudo=sudo)


def test_version(lxd):
    version = lxd.version()

    assert isinstance(version, str) is True

    components = version.split(".")

    assert len(components) in [2, 3]


@pytest.mark.parametrize(
    "sudo",
    [
        pytest.param(False, id="no-sudo"),
        pytest.param(True, marks=pytest.mark.with_sudo, id="with-sudo"),
    ],
)
def test_wait_ready(lxd, sudo):
    lxd.wait_ready(sudo=sudo)


def test_is_supported_version(lxd):
    assert lxd.is_supported_version() is True
