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

from unittest.mock import call

import pytest
from craft_providers.bases import ubuntu
from craft_providers.errors import BaseConfigurationError
from craft_providers.multipass import MultipassError, MultipassProvider
from craft_providers.multipass.multipass_provider import (
    _BUILD_BASE_TO_MULTIPASS_REMOTE_IMAGE,
    Remote,
    RemoteImage,
)


@pytest.fixture
def mock_buildd_base_configuration(mocker):
    mock_base_config = mocker.patch(
        "craft_providers.bases.ubuntu.BuilddBase", autospec=True
    )
    mock_base_config.alias = ubuntu.BuilddBaseAlias.JAMMY
    mock_base_config.compatibility_tag = "buildd-base-v2"
    return mock_base_config


@pytest.fixture
def mock_multipass(mocker):
    return mocker.patch("craft_providers.multipass.Multipass", autospec=True)


@pytest.fixture(autouse=True)
def mock_ensure_multipass_is_ready(mocker):
    return mocker.patch(
        "craft_providers.multipass.multipass_provider.ensure_multipass_is_ready",
        return_value=None,
    )


@pytest.fixture
def mock_install(mocker):
    return mocker.patch("craft_providers.multipass.multipass_provider.install")


@pytest.fixture(autouse=True)
def mock_is_installed(mocker):
    return mocker.patch(
        "craft_providers.multipass.multipass_provider.is_installed", return_value=True
    )


@pytest.fixture
def mock_launch(mocker):
    return mocker.patch(
        "craft_providers.multipass.multipass_provider.launch", autospec=True
    )


@pytest.fixture
def mock_remote_image(mocker):
    """Returns a mock RemoteImage object."""
    _mock_remote_image = mocker.patch(
        "craft_providers.multipass.multipass_provider.RemoteImage", autospec=True
    )
    _mock_remote_image.name = "test-remote:test-image"
    _mock_remote_image.is_stable = True
    return _mock_remote_image


def test_ensure_provider_is_available_installed(
    mock_is_installed, mock_install, mock_ensure_multipass_is_ready
):
    """Verify multipass is installed if it is not already installed."""
    mock_is_installed.return_value = True
    provider = MultipassProvider()

    provider.ensure_provider_is_available()

    mock_is_installed.assert_called_once()
    mock_install.assert_not_called()
    mock_ensure_multipass_is_ready.assert_called_once()


def test_ensure_provider_is_available_not_installed(
    mock_is_installed, mock_install, mock_ensure_multipass_is_ready
):
    """Verify multipass is not re-installed if it is already installed."""
    mock_is_installed.return_value = False
    provider = MultipassProvider()

    provider.ensure_provider_is_available()

    mock_is_installed.assert_called_once()
    mock_install.assert_called_once()
    mock_ensure_multipass_is_ready.assert_called_once()


@pytest.mark.parametrize("is_installed", [True, False])
def test_is_provider_installed(is_installed, mock_is_installed):
    """Verify `is_provider_installed` checks if Multipass is actually installed."""
    mock_is_installed.return_value = is_installed
    provider = MultipassProvider()

    assert provider.is_provider_installed() == is_installed


def test_create_environment(mocker):
    mock_multipass_instance = mocker.patch(
        "craft_providers.multipass.multipass_provider.MultipassInstance"
    )

    provider = MultipassProvider()
    provider.create_environment(instance_name="test-name")

    mock_multipass_instance.assert_called_once_with(name="test-name")


@pytest.mark.parametrize(
    ("build_base", "remote_image"), _BUILD_BASE_TO_MULTIPASS_REMOTE_IMAGE.items()
)
def test_launched_environment(
    build_base,
    remote_image,
    mock_launch,
    tmp_path,
):
    """Verify `launched_environment()` function."""
    provider = MultipassProvider()
    base_configuration = ubuntu.BuilddBase(alias=build_base)
    with provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=base_configuration,
        instance_name="test-instance-name",
        allow_unstable=True,
    ) as instance:
        assert instance is not None
        assert mock_launch.mock_calls == [
            call(
                name="test-instance-name",
                base_configuration=base_configuration,
                image_name=remote_image.name,
                cpus=2,
                disk_gb=64,
                mem_gb=2,
                auto_clean=True,
            ),
        ]
        mock_launch.reset_mock()

    assert mock_launch.mock_calls == [
        call().unmount_all(),
        call().stop(),
    ]


@pytest.mark.parametrize(
    ("is_stable", "allow_unstable"),
    [
        # unstable images can only be launched when `allow_unstable=True`
        (False, True),
        # stable images can be launched regardless of `allow_unstable`
        (True, False),
        (True, True),
    ],
)
def test_launched_environment_stable(
    is_stable,
    allow_unstable,
    mock_buildd_base_configuration,
    mock_launch,
    mock_remote_image,
    mocker,
    tmp_path,
):
    """Verify allow_unstable parameter works as expected."""
    mock_remote_image.is_stable = is_stable
    mocker.patch(
        "craft_providers.multipass.multipass_provider._get_remote_image",
        return_value=mock_remote_image,
    )

    provider = MultipassProvider()
    with provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        instance_name="test-instance-name",
        allow_unstable=allow_unstable,
    ) as instance:
        assert instance is not None
        assert mock_launch.mock_calls == [
            call(
                name="test-instance-name",
                base_configuration=mock_buildd_base_configuration,
                image_name="test-remote:test-image",
                cpus=2,
                disk_gb=64,
                mem_gb=2,
                auto_clean=True,
            ),
        ]
        mock_launch.reset_mock()

    assert mock_launch.mock_calls == [
        call().unmount_all(),
        call().stop(),
    ]


def test_launched_environment_unstable_image_error(
    mock_buildd_base_configuration,
    mock_launch,
    mock_remote_image,
    mocker,
    tmp_path,
):
    """Raise an error when `allow_unstable=False` and image is unstable."""
    mock_remote_image.is_stable = False
    mocker.patch(
        "craft_providers.multipass.multipass_provider._get_remote_image",
        return_value=mock_remote_image,
    )

    provider = MultipassProvider()
    with pytest.raises(MultipassError) as raised, provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        instance_name="test-instance-name",
    ):
        pass

    assert raised.value == MultipassError(
        brief="Cannot launch unstable image 'test-remote:test-image'.",
        details=(
            "Devel or daily images are not guaranteed and are intended for "
            "experimental use only."
        ),
        resolution=(
            "Set parameter `allow_unstable` to True to launch unstable images."
        ),
    )


def test_launched_environment_launch_base_configuration_error(mock_launch, tmp_path):
    error = BaseConfigurationError(brief="fail")
    mock_launch.side_effect = error
    provider = MultipassProvider()
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    with pytest.raises(MultipassError, match="fail") as raised:
        with provider.launched_environment(
            project_name="test-project",
            project_path=tmp_path,
            base_configuration=base_configuration,
            instance_name="test-instance-name",
        ):
            pass

    assert raised.value.__cause__ is error


@pytest.mark.parametrize("remote", Remote)
def test_remote_image_name(remote):
    """Verify RemoteImage name is formulated properly."""
    remote_image = RemoteImage(remote=remote, image_name="test-name")
    assert remote_image.name == f"{remote.value}:test-name"


@pytest.mark.parametrize(
    ("remote_image", "is_stable"),
    [
        # 'release' and 'snapcraft' remotes are stable
        (RemoteImage(remote=Remote.RELEASE, image_name="test-name"), True),
        (RemoteImage(remote=Remote.SNAPCRAFT, image_name="test-name"), True),
        # 'daily' remote is not stable
        (RemoteImage(remote=Remote.DAILY, image_name="test-name"), False),
        # 'devel' images are not stable, regardless of remote
        (RemoteImage(remote=Remote.RELEASE, image_name="devel"), False),
        (RemoteImage(remote=Remote.DAILY, image_name="devel"), False),
        (RemoteImage(remote=Remote.SNAPCRAFT, image_name="devel"), False),
    ],
)
def test_remote_is_stable(remote_image, is_stable):
    """RemoteImages should be properly marked as stable or unstable."""
    assert remote_image.is_stable == is_stable


def test_multipass_name():
    """Verify MultipassProvider's name."""
    provider = MultipassProvider()

    assert provider.name == "Multipass"


def test_multipass_install_recommendation():
    """Verify MultipassProvider's install recommendation."""
    provider = MultipassProvider()

    assert (
        provider.install_recommendation
        == "Visit https://multipass.run/install for instructions to install Multipass."
    )
