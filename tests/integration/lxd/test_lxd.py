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


import pytest

from craft_providers.lxd import LXD


@pytest.fixture()
def lxd():
    yield LXD()


def test_init(lxd):
    lxd.init(auto=True)
    lxd.init(sudo=True, auto=True)


def test_version(lxd):
    components = lxd.version().split(".")

    assert len(components) in [2, 3]
    assert all(int(c) for c in components)


def test_wait_ready(lxd):
    lxd.wait_ready()
    lxd.wait_ready(sudo=True)


def test_is_supported_version(lxd):
    assert lxd.is_supported_version() is True
