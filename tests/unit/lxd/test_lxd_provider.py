# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022 Canonical Ltd.
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

from unittest import mock

import pytest

from craft_providers import bases
from craft_providers.lxd import LXDError, LXDProvider


@pytest.fixture
def mock_buildd_base_configuration(mocker):
    mock_base_config = mocker.patch("craft_providers.bases.BuilddBase", autospec=True)
    mock_base_config.compatibility_tag = "buildd-base-v0"
    yield mock_base_config


@pytest.fixture
def mock_configure_buildd_image_remote(mocker):
    yield mocker.patch(
        "craft_providers.lxd.lxd_provider.configure_buildd_image_remote",
        return_value="buildd-remote",
    )


@pytest.fixture
def mock_lxc(mocker):
    yield mocker.patch("craft_providers.lxd.LXC", autospec=True)


@pytest.fixture(autouse=True)
def mock_ensure_lxd_is_ready(mocker):
    yield mocker.patch(
        "craft_providers.lxd.lxd_provider.ensure_lxd_is_ready", return_value=None
    )


@pytest.fixture
def mock_install(mocker):
    yield mocker.patch("craft_providers.lxd.lxd_provider.install")


@pytest.fixture(autouse=True)
def mock_is_installed(mocker):
    yield mocker.patch(
        "craft_providers.lxd.lxd_provider.is_installed", return_value=True
    )


@pytest.fixture
def mock_launch(mocker):
    yield mocker.patch("craft_providers.lxd.lxd_provider.launch", autospec=True)


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
    "build_base, lxd_base",
    [
        (bases.BuilddBaseAlias.BIONIC.value, "core18"),
        (bases.BuilddBaseAlias.FOCAL.value, "core20"),
        (bases.BuilddBaseAlias.JAMMY.value, "core22"),
    ],
)
def test_launched_environment(
    build_base,
    lxd_base,
    mock_buildd_base_configuration,
    mock_configure_buildd_image_remote,
    mock_launch,
    tmp_path,
):
    provider = LXDProvider()

    with provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=mock_buildd_base_configuration,
        build_base=build_base,
        instance_name="test-instance-name",
    ) as instance:
        assert instance is not None
        assert mock_configure_buildd_image_remote.mock_calls == [mock.call()]
        assert mock_launch.mock_calls == [
            mock.call(
                name="test-instance-name",
                base_configuration=mock_buildd_base_configuration,
                image_name=lxd_base,
                image_remote="buildd-remote",
                auto_clean=True,
                auto_create_project=True,
                map_user_uid=True,
                uid=tmp_path.stat().st_uid,
                use_base_instance=True,
                project="default",
                remote="local",
            ),
        ]

        mock_launch.reset_mock()

    assert mock_launch.mock_calls == [
        mock.call().unmount_all(),
        mock.call().stop(),
    ]


def test_launched_environment_launch_base_configuration_error(
    mock_buildd_base_configuration,
    mock_configure_buildd_image_remote,
    mock_launch,
    tmp_path,
):
    error = bases.BaseConfigurationError(brief="fail")
    mock_launch.side_effect = error
    provider = LXDProvider()

    with pytest.raises(LXDError, match="fail") as raised:
        with provider.launched_environment(
            project_name="test-project",
            project_path=tmp_path,
            base_configuration=mock_buildd_base_configuration,
            build_base=bases.BuilddBaseAlias.FOCAL.value,
            instance_name="test-instance-name",
        ):
            pass

    assert raised.value.__cause__ is error
