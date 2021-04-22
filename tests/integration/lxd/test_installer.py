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

import shutil

from craft_providers import lxd


def test_is_installed():
    expected = shutil.which("lxd") is not None

    assert lxd.is_installed() is expected


def test_install(uninstalled_lxd):  # pylint: disable=unused-argument
    assert lxd.is_installed() is False

    lxd_version = lxd.install()

    assert lxd.is_installed() is True
    assert lxd_version is not None
