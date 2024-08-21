# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022-2023 Canonical Ltd.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import timedelta
from unittest.mock import call

import pytest
from craft_providers.bases import ubuntu
from craft_providers.errors import BaseConfigurationError
from craft_providers.lxd import LXDError, LXDProvider, LXDUnstableImageError


@pytest.fixture
def mock_remote_image(mocker):
    _mock_remote_image = mocker.patch("craft_providers.lxd.remotes.RemoteImage")
    _mock_remote_image.image_name = "test-image-name"
    _mock_remote_image.remote_name = "test-remote-name"
    return _mock_remote_image


@pytest.fixture
def mock_get_remote_image(mock_remote_image, mocker):
    _mock_get_remote_image = mocker.patch(
        "craft_providers.lxd.lxd_provider.get_remote_image",
        return_value=mock_remote_image,
    )
    return _mock_get_remote_image


@pytest.fixture
def mock_buildd_base_configuration(mocker):
    mock_base_config = mocker.patch(
        "craft_providers.bases.ubuntu.BuilddBase", autospec=True
    )
    mock_base_config.alias = ubuntu.BuilddBaseAlias.JAMMY
    mock_base_config.compatibility_tag = "buildd-base-v2"
    return mock_base_config


@pytest.fixture
def mock_lxc(mocker):
    return mocker.patch("craft_providers.lxd.LXC", autospec=True)


@pytest.fixture(autouse=True)
def mock_ensure_lxd_is_ready(mocker):
    return mocker.patch(
        "craft_providers.lxd.lxd_provider.ensure_lxd_is_ready", return_value=None
    )


@pytest.fixture
def mock_install(mocker):
    return mocker.patch("craft_providers.lxd.lxd_provider.install")


@pytest.fixture(autouse=True)
def mock_is_installed(mocker):
    return mocker.patch(
        "craft_providers.lxd.lxd_provider.is_installed", return_value=True
    )


@pytest.fixture
def mock_launch(mocker):
    return mocker.patch("craft_providers.lxd.lxd_provider.launch", autospec=True)


def test_ensure_provider_is_available_installed(
    mock_is_installed, mock_install, mock_ensure_lxd_is_ready
):
    """Verify LXD is installed if it is not already installed."""
    mock_is_installed.return_value = True
    provider = LXDProvider()

    provider.ensure_provider_is_available()

    mock_install.assert_not_called()
    mock_ensure_lxd_is_ready.assert_called_once()


def test_ensure_provider_is_available_not_installed(
    mock_is_installed, mock_install, mock_ensure_lxd_is_ready
):
    """Verify LXD is not re-installed if it is already installed."""
    mock_is_installed.return_value = False
    provider = LXDProvider()

    provider.ensure_provider_is_available()

    mock_install.assert_called_once()
    mock_ensure_lxd_is_ready.assert_called_once()


@pytest.mark.parametrize("is_installed", [True, False])
def test_is_provider_installed(is_installed, mock_is_installed):
    """Verify `is_provider_installed` checks if LXD is actually installed."""
    mock_is_installed.return_value = is_installed
    provider = LXDProvider()

    assert provider.is_provider_installed() == is_installed


def test_create_environment(mocker):
    mock_lxd_instance = mocker.patch("craft_providers.lxd.lxd_provider.LXDInstance")

    provider = LXDProvider()
    provider.create_environment(instance_name="test-name")

    mock_lxd_instance.assert_called_once_with(
        name="test-name", project="default", remote="local"
    )


@pytest.mark.parametrize(
    ("allow_unstable", "is_stable"),
    [
        # all permutations are valid except allow_unstable=False and is_stable=False
        (True, True),
        (True, False),
        (False, True),
    ],
)
def test_launched_environment(
    allow_unstable,
    is_stable,
    mock_buildd_base_configuration,
    mock_get_remote_image,
    mock_remote_image,
    mock_launch,
    mock_lxc,
    tmp_path,
):
    mock_remote_image.is_stable = is_stable
    provider = LXDProvider(lxc=mock_lxc)

    # set the expected expiration time
    expiration = timedelta(days=90) if is_stable else timedelta(days=14)

    with provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        instance_name="test-instance-name",
        allow_unstable=allow_unstable,
    ) as instance:
        assert instance is not None
        mock_get_remote_image.assert_called_once_with(mock_buildd_base_configuration)
        mock_remote_image.add_remote.assert_called_once_with(lxc=mock_lxc)
        assert mock_launch.mock_calls == [
            call(
                name="test-instance-name",
                base_configuration=mock_buildd_base_configuration,
                image_name="test-image-name",
                image_remote="test-remote-name",
                auto_clean=True,
                auto_create_project=True,
                map_user_uid=True,
                uid=tmp_path.stat().st_uid,
                use_base_instance=True,
                project="default",
                remote="local",
                expiration=expiration,
            ),
        ]

        mock_launch.reset_mock()

    assert mock_launch.mock_calls == [
        call().unmount_all(),
        call().stop(),
    ]


def test_launched_environment_launch_base_configuration_error(
    mock_buildd_base_configuration,
    mock_get_remote_image,
    mock_remote_image,
    mock_launch,
    tmp_path,
):
    error = BaseConfigurationError(brief="fail")
    mock_launch.side_effect = error
    provider = LXDProvider()

    with pytest.raises(LXDError, match="fail") as raised, provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        instance_name="test-instance-name",
    ):
        pass

    assert raised.value.__cause__ is error


def test_launched_environment_unstable_error(
    mock_buildd_base_configuration,
    mock_get_remote_image,
    mock_remote_image,
    mock_launch,
    tmp_path,
):
    """Raise an Exception when an unstable image is used with opting in."""
    mock_remote_image.is_stable = False
    provider = LXDProvider()

    with pytest.raises(LXDUnstableImageError) as raised, provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        instance_name="test-instance-name",
    ):
        pass

    assert raised.value.brief == (
        "Cannot launch an unstable image 'test-image-name' from remote "
        "'test-remote-name'"
    )


def test_lxd_name():
    """Verify LXDProvider's name."""
    provider = LXDProvider()

    assert provider.name == "LXD"


def test_lxd_install_recommendation():
    """Verify LXDProvider's install recommendation."""
    provider = LXDProvider()

    assert (
        provider.install_recommendation
        == "Visit https://ubuntu.com/lxd/install for instructions to install LXD."
    )
