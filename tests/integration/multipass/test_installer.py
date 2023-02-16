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

from craft_providers import multipass


def test_is_installed():
    expected = shutil.which("multipass") is not None

    assert multipass.is_installed() is expected


def test_install(uninstalled_multipass):
    assert multipass.is_installed() is False

    multipass_version = multipass.install()

    assert multipass.is_installed() is True
    assert multipass_version is not None
