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
from craft_providers.bases import ubuntu
from craft_providers.errors import BaseConfigurationError
from craft_providers.lxd import remotes


@pytest.fixture()
def mock_lxc(mocker):
    return mocker.patch("craft_providers.lxd.launcher.LXC", spec=lxd.LXC)


@pytest.fixture()
def fake_remote_image(mocker):
    return remotes.RemoteImage(
        image_name="test-image-name",
        remote_name="test-remote-name",
        remote_address="test-remote-address",
        remote_protocol=remotes.ProtocolType.LXD,
    )


@pytest.fixture()
def mock_remote_image(mocker):
    return mocker.patch(
        "craft_providers.lxd.remotes.RemoteImage", spec=remotes.RemoteImage
    )


@pytest.fixture()
def mock_get_remote_image(mocker, mock_remote_image):
    return mocker.patch(
        "craft_providers.lxd.remotes.get_remote_image", return_value=mock_remote_image
    )


@pytest.mark.parametrize(
    ("remote_name", "remote_address", "is_stable"),
    [
        (
            remotes.BUILDD_RELEASES_REMOTE_NAME,
            remotes.BUILDD_RELEASES_REMOTE_ADDRESS,
            True,
        ),
        (remotes.BUILDD_DAILY_REMOTE_NAME, remotes.BUILDD_DAILY_REMOTE_ADDRESS, False),
        (remotes.DAILY_REMOTE_NAME, remotes.DAILY_REMOTE_ADDRESS, False),
        ("other-remote-name", "other-remote-address", False),
    ],
)
def test_remote_image_is_stable_true(remote_name, remote_address, is_stable):
    """Verify `is_stable` is only true for images from the BUILDD_RELEASES remote."""
    test_remote = remotes.RemoteImage(
        image_name="test-image-name",
        remote_name=remote_name,
        remote_address=remote_address,
        remote_protocol=remotes.ProtocolType.LXD,
    )

    assert test_remote.is_stable == is_stable


def test_add_remote_new(fake_remote_image, mock_lxc, logs):
    """Verify remote is added if it does not already exist."""
    fake_remote_image.add_remote(mock_lxc)

    assert mock_lxc.mock_calls == [
        call.remote_list(),
        call.remote_list().__contains__("test-remote-name"),
        call.remote_add(
            remote="test-remote-name",
            addr="test-remote-address",
            protocol=remotes.ProtocolType.LXD.value,
        ),
    ]
    assert "Remote 'test-remote-name' was successfully added." in logs.debug


def test_add_remote_existing(fake_remote_image, mock_lxc, logs):
    """Verify existing remote is not added again."""
    mock_lxc.remote_list.return_value = {"test-remote-name": {}}

    fake_remote_image.add_remote(mock_lxc)

    assert mock_lxc.mock_calls == [call.remote_list()]
    assert "Remote 'test-remote-name' already exists." in logs.debug


def test_add_remote_race_condition(fake_remote_image, mock_lxc, logs):
    """Race condition when adding the remote, it was created by other process."""
    # the first time the list will not show the remote, then `remote_add` will fail
    # because it was just created from other process, and exactly because of that
    # it will show in the list the second time is asked
    mock_lxc.remote_list.side_effect = [{}, {"test-remote-name": {}}]
    mock_lxc.remote_add.side_effect = ValueError()

    fake_remote_image.add_remote(mock_lxc)

    assert mock_lxc.mock_calls == [
        call.remote_list(),
        call.remote_add(
            remote="test-remote-name",
            addr="test-remote-address",
            protocol=remotes.ProtocolType.LXD.value,
        ),
        call.remote_list(),
    ]
    assert (
        "Remote 'test-remote-name' is present on second check, ignoring exception "
        "ValueError()." in logs.debug
    )


def test_add_remote_race_condition_error(fake_remote_image, mock_lxc, logs):
    """Race condition code triggered but it was actually an error."""
    mock_lxc.remote_list.return_value = {}
    mock_lxc.remote_add.side_effect = ValueError()

    with pytest.raises(ValueError):
        fake_remote_image.add_remote(mock_lxc)


@pytest.mark.parametrize(
    ("provider_base_alias", "image_name"),
    [
        (ubuntu.BuilddBaseAlias.BIONIC, "core18"),
        (ubuntu.BuilddBaseAlias.FOCAL, "core20"),
        (ubuntu.BuilddBaseAlias.JAMMY, "core22"),
        (ubuntu.BuilddBaseAlias.LUNAR, "lunar"),
        (ubuntu.BuilddBaseAlias.DEVEL, "devel"),
    ],
)
def test_get_image_remote(provider_base_alias, image_name):
    """Verify `get_remote_image()` returns a RemoteImage."""
    base = ubuntu.BuilddBase(alias=provider_base_alias)
    remote_image = lxd.remotes.get_remote_image(base)

    assert remote_image.image_name == image_name


@pytest.mark.parametrize(
    ("provider_base_alias", "image_name"),
    [
        (ubuntu.BuilddBaseAlias.BIONIC, "core18"),
        (ubuntu.BuilddBaseAlias.FOCAL, "core20"),
        (ubuntu.BuilddBaseAlias.JAMMY, "core22"),
        (ubuntu.BuilddBaseAlias.LUNAR, "lunar"),
        (ubuntu.BuilddBaseAlias.DEVEL, "devel"),
    ],
)
def test_get_image_remote_deprecated(provider_base_alias, image_name):
    """Verify `get_remote_image()` returns a RemoteImage.
    temporary backward compatibility before 2.0
    """
    remote_image = lxd.remotes.get_remote_image(str(provider_base_alias.value))

    assert remote_image.image_name == image_name


def test_get_image_remote_xenial_error():
    """Raise an error when retrieving a xenial image.

    The remote image for Xenial has not been chosen for craft-providers + LXD, so an
    error is raised.
    """
    base = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.XENIAL)
    with pytest.raises(lxd.LXDError) as raised:
        lxd.remotes.get_remote_image(base)

    assert "could not find a lxd remote image for the provider base " in str(
        raised.value
    )


def test_get_image_remote_error():
    """Raise an error for an unknown provider base."""
    base = ubuntu.BuilddBase(alias=-1)  # type: ignore
    with pytest.raises(lxd.LXDError) as raised:
        lxd.remotes.get_remote_image(base)

    assert "could not find a lxd remote image for the provider base " in str(
        raised.value
    )


def test_get_image_remote_deprecated_error():
    """Raise an error for an unknown provider base."""
    with pytest.raises(BaseConfigurationError) as raised:
        lxd.remotes.get_remote_image("8.04")

    assert (
        str(raised.value)
        == "Base alias not found for BaseName(name='ubuntu', version='8.04')"
    )


def test_configure_buildd_image_remote(
    mock_lxc, logs, mock_get_remote_image, mock_remote_image
):
    """Verify deprecated `configure_buildd_image_remote()` call."""

    with pytest.warns(DeprecationWarning) as warning:
        name = lxd.remotes.configure_buildd_image_remote(lxc=mock_lxc)

    assert str(warning[0].message) == (
        "configure_buildd_image_remote() is deprecated. "
        "Use get_remote_image() and RemoteImage.add_remote()."
    )
    mock_get_remote_image.assert_called_once()
    mock_remote_image.add_remote.assert_called_once_with(mock_lxc)
    assert name == remotes.BUILDD_RELEASES_REMOTE_NAME
