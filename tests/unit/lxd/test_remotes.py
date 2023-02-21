#
# Copyright 2021-2022 Canonical Ltd.
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
from craft_providers.lxd.remotes import BUILDD_REMOTE_ADDR, BUILDD_REMOTE_NAME


@pytest.fixture
def mock_lxc():
    with mock.patch(
        "craft_providers.lxd.launcher.LXC",
        spec=lxd.LXC,
    ) as mock_lxc:
        yield mock_lxc.return_value


def test_configure_buildd_image_remote_fresh(mock_lxc, logs):
    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == BUILDD_REMOTE_NAME
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
        mock.call.remote_list().__contains__(BUILDD_REMOTE_NAME),
        mock.call.remote_add(
            remote=BUILDD_REMOTE_NAME,
            addr=BUILDD_REMOTE_ADDR,
            protocol="simplestreams",
        ),
    ]
    assert f"Remote '{BUILDD_REMOTE_NAME}' was successfully added." in logs.debug


def test_configure_buildd_image_remote_already_exists(mock_lxc, logs):
    mock_lxc.remote_list.return_value = {BUILDD_REMOTE_NAME: {}}

    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == BUILDD_REMOTE_NAME
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
    ]
    assert f"Remote '{BUILDD_REMOTE_NAME}' already exists." in logs.debug


def test_configure_buildd_image_remote_racecondition_created(mock_lxc, logs):
    """Race condition when adding the remote, it was created by other process."""
    # the first time the list will not show the remote, then `remote_add` will fail
    # because it was just created from other process, and exactly because of that
    # it will show in the list the second time is asked
    test_remote_name = BUILDD_REMOTE_NAME
    mock_lxc.remote_list.side_effect = [{}, {test_remote_name: {}}]
    mock_lxc.remote_add.side_effect = ValueError()

    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == BUILDD_REMOTE_NAME
    assert mock_lxc.mock_calls == [
        mock.call.remote_list(),
        mock.call.remote_add(
            remote=BUILDD_REMOTE_NAME,
            addr=BUILDD_REMOTE_ADDR,
            protocol="simplestreams",
        ),
        mock.call.remote_list(),
    ]
    assert (
        f"Remote '{BUILDD_REMOTE_NAME}' is present on second check, "
        "ignoring exception ValueError()." in logs.debug
    )


def test_configure_buildd_image_remote_racecondition_error(mock_lxc, logs):
    """Race condition code triggered but it was actually an error."""
    mock_lxc.remote_list.return_value = {}
    mock_lxc.remote_add.side_effect = ValueError()

    with pytest.raises(ValueError):
        lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)
