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

import pytest
from craft_providers import ProviderError
from craft_providers.lxd import LXDError, LXDProvider
from craft_providers.multipass import MultipassError, MultipassProvider

known_provider_classes = [LXDProvider, MultipassProvider]


@pytest.fixture(params=known_provider_classes)
def provider_class(request):
    return request.param


@pytest.fixture(autouse=True)
def mock_lxd_delete(mocker):
    return mocker.patch("craft_providers.lxd.LXDInstance.delete")


@pytest.fixture(autouse=True)
def mock_lxd_exists(mocker):
    return mocker.patch("craft_providers.lxd.LXDInstance.exists", return_value=True)


@pytest.fixture(autouse=True)
def mock_lxd_is_installed(mocker):
    return mocker.patch(
        "craft_providers.lxd.lxd_provider.is_installed", return_value=True
    )


@pytest.fixture(autouse=True)
def mock_multipass_delete(mocker):
    return mocker.patch("craft_providers.multipass.MultipassInstance.delete")


@pytest.fixture(autouse=True)
def mock_multipass_exists(mocker):
    return mocker.patch(
        "craft_providers.multipass.MultipassInstance.exists", return_value=True
    )


@pytest.fixture(autouse=True)
def mock_multipass_is_installed(mocker):
    return mocker.patch(
        "craft_providers.multipass.multipass_provider.is_installed", return_value=True
    )


def test_clean_project_environment_exists(
    mock_lxd_delete, mock_multipass_delete, provider_class
):
    """Assert instance is deleted if it exists."""
    provider = provider_class()
    provider.clean_project_environments(instance_name="test-name")

    if isinstance(provider, LXDProvider):
        mock_lxd_delete.assert_called_once()
    else:
        mock_multipass_delete.assert_called_once()


def test_clean_project_environment_does_not_exist(
    mock_lxd_exists,
    mock_lxd_delete,
    mock_multipass_exists,
    mock_multipass_delete,
    provider_class,
):
    """Assert instance is not deleted if it does not exist."""
    mock_lxd_exists.return_value = False
    mock_multipass_exists.return_value = False

    provider = provider_class()
    provider.clean_project_environments(instance_name="test-name")

    mock_lxd_delete.assert_not_called()
    mock_multipass_delete.assert_not_called()


def test_clean_project_environment_not_installed(
    mock_lxd_delete,
    mock_lxd_is_installed,
    mock_multipass_delete,
    mock_multipass_is_installed,
    provider_class,
):
    """Assert instance is not deleted if the provider is not installed."""
    mock_lxd_is_installed.return_value = False
    mock_multipass_is_installed.return_value = False

    provider = provider_class()
    provider.clean_project_environments(instance_name="test-name")

    mock_lxd_delete.assert_not_called()
    mock_multipass_delete.assert_not_called()


def test_clean_project_environment_exists_error(
    mock_lxd_exists, mock_multipass_exists, provider_class
):
    """Assert error on `exists` call is caught."""
    mock_lxd_exists.side_effect = LXDError("fail")
    mock_multipass_exists.side_effect = MultipassError("fail")
    provider = provider_class()

    with pytest.raises(ProviderError) as raised:
        provider.clean_project_environments(instance_name="test-name")

    assert str(raised.value) == "fail"


def test_clean_project_environment_delete_error(
    mock_lxd_delete, mock_multipass_delete, provider_class
):
    """Assert error on `delete` call is caught."""
    mock_lxd_delete.side_effect = LXDError("fail")
    mock_multipass_delete.side_effect = MultipassError("fail")
    provider = provider_class()

    with pytest.raises(ProviderError) as raised:
        provider.clean_project_environments(instance_name="test-name")

    assert str(raised.value) == "fail"
