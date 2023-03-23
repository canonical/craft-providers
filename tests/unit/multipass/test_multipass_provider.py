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

from craft_providers import bases
from craft_providers.multipass import MultipassError, MultipassProvider
from craft_providers.multipass.multipass_provider import (
    _BUILD_BASE_TO_MULTIPASS_REMOTE_IMAGE,
)


@pytest.fixture
def mock_buildd_base_configuration(mocker):
    mock_base_config = mocker.patch("craft_providers.bases.BuilddBase", autospec=True)
    mock_base_config.compatibility_tag = "buildd-base-v1"
    yield mock_base_config


@pytest.fixture
def mock_multipass(mocker):
    yield mocker.patch("craft_providers.multipass.Multipass", autospec=True)


@pytest.fixture(autouse=True)
def mock_ensure_multipass_is_ready(mocker):
    yield mocker.patch(
        "craft_providers.multipass.multipass_provider.ensure_multipass_is_ready",
        return_value=None,
    )


@pytest.fixture
def mock_install(mocker):
    yield mocker.patch("craft_providers.multipass.multipass_provider.install")


@pytest.fixture(autouse=True)
def mock_is_installed(mocker):
    yield mocker.patch(
        "craft_providers.multipass.multipass_provider.is_installed", return_value=True
    )


@pytest.fixture
def mock_launch(mocker):
    yield mocker.patch(
        "craft_providers.multipass.multipass_provider.launch", autospec=True
    )


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
    "build_base, remote_image", _BUILD_BASE_TO_MULTIPASS_REMOTE_IMAGE.items()
)
def test_launched_environment(
    build_base,
    remote_image,
    mock_buildd_base_configuration,
    mock_launch,
    tmp_path,
):
    """Verify `launched_environment()` function."""
    provider = MultipassProvider()
    with provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        build_base=build_base,
        instance_name="test-instance-name",
    ) as instance:
        assert instance is not None
        assert mock_launch.mock_calls == [
            call(
                name="test-instance-name",
                base_configuration=mock_buildd_base_configuration,
                image_name=remote_image,
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


def test_launched_environment_launch_base_configuration_error(
    mock_buildd_base_configuration, mock_launch, tmp_path
):
    error = bases.BaseConfigurationError(brief="fail")
    mock_launch.side_effect = error
    provider = MultipassProvider()

    with pytest.raises(MultipassError, match="fail") as raised:
        with provider.launched_environment(
            project_name="test-project",
            project_path=tmp_path,
            base_configuration=mock_buildd_base_configuration,
            build_base=bases.BuilddBaseAlias.FOCAL.value,
            instance_name="test-instance-name",
        ):
            pass

    assert raised.value.__cause__ is error
