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

from unittest import mock

import pytest

from craft_providers import lxd


@pytest.fixture
def mock_lxc():
    with mock.patch(
        "craft_providers.lxd.launcher.LXC",
        spec=lxd.LXC,
    ) as mock_lxc:
        yield mock_lxc.return_value


def test_configure_buildd_image_remote_fresh(mock_lxc):
    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == "craft-com.ubuntu.cloud-buildd"
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
        mock.call.remote_list().__contains__("craft-com.ubuntu.cloud-buildd"),
        mock.call.remote_add(
            remote="craft-com.ubuntu.cloud-buildd",
            addr="https://cloud-images.ubuntu.com/buildd/releases",
            protocol="simplestreams",
        ),
    ]


def test_configure_buildd_image_remote_already_exists(mock_lxc):
    mock_lxc.remote_list.return_value = {"craft-com.ubuntu.cloud-buildd": {}}

    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == "craft-com.ubuntu.cloud-buildd"
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
    ]
