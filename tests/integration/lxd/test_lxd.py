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


import pytest

from craft_providers.lxd import LXD


@pytest.fixture()
def lxd():
    yield LXD()


def test_init(lxd):
    lxd.init(auto=True)
    lxd.init(sudo=True, auto=True)


def test_version(lxd):
    version = lxd.version()

    assert isinstance(version, str) is True

    components = version.split(".")

    assert len(components) in [2, 3]


def test_wait_ready(lxd):
    lxd.wait_ready()
    lxd.wait_ready(sudo=True)


def test_is_supported_version(lxd):
    assert lxd.is_supported_version() is True
