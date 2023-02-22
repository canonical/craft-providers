# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
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

from unittest.mock import call

import pytest

from craft_providers import lxd
from craft_providers.bases import BuilddBaseAlias
from craft_providers.lxd.remotes import (
    BUILDD_RELEASES_REMOTE_ADDRESS,
    BUILDD_RELEASES_REMOTE_NAME,
)


@pytest.fixture
def mock_lxc(mocker):
    yield mocker.patch("craft_providers.lxd.launcher.LXC", spec=lxd.LXC)


def test_configure_buildd_image_remote_fresh(mock_lxc, logs):
    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == BUILDD_RELEASES_REMOTE_NAME
    assert mock_lxc.mock_calls == [
        call.remote_list(),
        call.remote_list().__contains__(BUILDD_RELEASES_REMOTE_NAME),
        call.remote_add(
            remote=BUILDD_RELEASES_REMOTE_NAME,
            addr=BUILDD_RELEASES_REMOTE_ADDRESS,
            protocol="simplestreams",
        ),
    ]
    assert f"Remote '{BUILDD_RELEASES_REMOTE_NAME}' was successfully added." in logs.debug


def test_configure_buildd_image_remote_already_exists(mock_lxc, logs):
    mock_lxc.remote_list.return_value = {BUILDD_RELEASES_REMOTE_NAME: {}}

    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == BUILDD_RELEASES_REMOTE_NAME
    assert mock_lxc.mock_calls == [
        call.remote_list(),
    ]
    assert f"Remote '{BUILDD_RELEASES_REMOTE_NAME}' already exists." in logs.debug


def test_configure_buildd_image_remote_racecondition_created(mock_lxc, logs):
    """Race condition when adding the remote, it was created by other process."""
    # the first time the list will not show the remote, then `remote_add` will fail
    # because it was just created from other process, and exactly because of that
    # it will show in the list the second time is asked
    test_remote_name = BUILDD_RELEASES_REMOTE_NAME
    mock_lxc.remote_list.side_effect = [{}, {test_remote_name: {}}]
    mock_lxc.remote_add.side_effect = ValueError()

    name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert name == BUILDD_RELEASES_REMOTE_NAME
    assert mock_lxc.mock_calls == [
        call.remote_list(),
        call.remote_add(
            remote=BUILDD_RELEASES_REMOTE_NAME,
            addr=BUILDD_RELEASES_REMOTE_ADDRESS,
            protocol="simplestreams",
        ),
        call.remote_list(),
    ]
    assert (
        f"Remote '{BUILDD_RELEASES_REMOTE_NAME}' is present on second check, "
        "ignoring exception ValueError()." in logs.debug
    )


def test_configure_buildd_image_remote_racecondition_error(mock_lxc, logs):
    """Race condition code triggered but it was actually an error."""
    mock_lxc.remote_list.return_value = {}
    mock_lxc.remote_add.side_effect = ValueError()

    with pytest.raises(ValueError):
        lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)


@pytest.mark.parametrize(
    "provider_base, image_name",
    [
        (BuilddBaseAlias.BIONIC.value, "core18"),
        (BuilddBaseAlias.FOCAL.value, "core20"),
        (BuilddBaseAlias.JAMMY.value, "core22"),
    ],
)
def test_get_image_remote(provider_base, image_name):
    """Verify `get_remote_image()` returns a RemoteImage."""
    remote_image = lxd.remotes.get_remote_image(provider_base)

    assert remote_image.image_name == image_name


def test_get_image_remote_xenial_error():
    """Raise an error when retrieving a xenial image.

    The remote image for Xenial has not been chosen for craft-providers + LXD, so an
    error is raised.
    """
    with pytest.raises(lxd.LXDError) as raised:
        lxd.remotes.get_remote_image(BuilddBaseAlias.XENIAL.value)

    assert str(raised.value) == (
        "could not find a lxd remote image for the provider base '16.04'"
    )


def test_get_image_remote_error():
    """Raise an error for an unknown provider base."""
    with pytest.raises(lxd.LXDError) as raised:
        lxd.remotes.get_remote_image("unknown-base")

    assert str(raised.value) == (
        "could not find a lxd remote image for the provider base 'unknown-base'"
    )
