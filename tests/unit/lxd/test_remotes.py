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

    assert name == "com.cloud-images.buildd.releases"
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
        mock.call.remote_list().__contains__("com.cloud-images.buildd.releases"),
        mock.call.remote_add(
            remote="com.cloud-images.buildd.releases",
            addr="https://cloud-images.ubuntu.com/buildd/releases",
            protocol="simplestreams",
        ),
    ]


def test_configure_buildd_image_remote_already_exists(mock_lxc):
    mock_lxc.remote_list.return_value = {"com.cloud-images.buildd.releases": {}}

    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == "com.cloud-images.buildd.releases"
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
    ]
