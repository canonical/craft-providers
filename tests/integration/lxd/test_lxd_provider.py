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
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import pytest
from craft_providers.bases import get_base_from_alias, ubuntu
from craft_providers.lxd import LXDProvider, is_installed


def test_ensure_provider_is_available_not_installed(uninstalled_lxd):
    """Verify lxd is installed and configured."""
    assert is_installed() is False
    provider = LXDProvider()
    provider.ensure_provider_is_available()


def test_ensure_provider_is_available_installed(installed_lxd):
    """Verify lxd is installed and configured."""
    assert is_installed() is True
    provider = LXDProvider()
    provider.ensure_provider_is_available()


def test_create_environment(installed_lxd, instance_name):
    provider = LXDProvider()
    test_instance = provider.create_environment(instance_name=instance_name)
    assert test_instance.exists() is False


@pytest.mark.parametrize(
    "alias",
    set(ubuntu.BuilddBaseAlias) - {ubuntu.BuilddBaseAlias.XENIAL},
)
def test_launched_environment(alias, installed_lxd, instance_name, tmp_path):
    provider = LXDProvider()

    base_configuration = get_base_from_alias(alias)(alias=alias)
    with provider.launched_environment(
        project_name="test-project",
        project_path=tmp_path,
        base_configuration=base_configuration,
        instance_name=instance_name,
        allow_unstable=True,
    ) as test_instance:
        assert test_instance.exists() is True
        assert test_instance.is_running() is True

    assert test_instance.exists() is True
    assert test_instance.is_running() is False
