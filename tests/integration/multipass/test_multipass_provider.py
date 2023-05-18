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
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
import sys

import pytest

from craft_providers.bases import ubuntu
from craft_providers.multipass import MultipassProvider, is_installed


def test_ensure_provider_is_available_not_installed(uninstalled_multipass):
    """Verify multipass is installed and configured."""
    assert is_installed() is False
    provider = MultipassProvider()
    provider.ensure_provider_is_available()


def test_ensure_provider_is_available_installed(installed_multipass):
    """Verify multipass is installed and configured."""
    assert is_installed() is True
    provider = MultipassProvider()
    provider.ensure_provider_is_available()


def test_create_environment(installed_multipass, instance_name):
    """Verify create environment does not produce an error."""
    provider = MultipassProvider()
    test_instance = provider.create_environment(instance_name=instance_name)
    assert test_instance.exists() is False


LINUX_ONLY_ALIASES = [
    ubuntu.BuilddBaseAlias.XENIAL,
    ubuntu.BuilddBaseAlias.LUNAR,
    ubuntu.BuilddBaseAlias.DEVEL,
]

@pytest.mark.parametrize(
    "alias",
    [
        *(alias for alias in ubuntu.BuilddBaseAlias if alias not in LINUX_ONLY_ALIASES),
        *(pytest.param(alias, marks=pytest.mark.skipif(sys.platform != "Linux"))
          for alias in LINUX_ONLY_ALIASES),
    ]
)
def test_launched_environment(alias, installed_multipass, instance_name, tmp_path):
    """Verify `launched_environment()` creates and starts an instance then stops
    the instance when the method loses context."""
    provider = MultipassProvider()

    base_configuration = ubuntu.BuilddBase(alias=alias)

    with provider.launched_environment(
        project_name="test-multipass-project",
        project_path=tmp_path,
        base_configuration=base_configuration,
        instance_name=instance_name,
        allow_unstable=True,
    ) as test_instance:
        assert test_instance.exists() is True
        assert test_instance.is_running() is True

    assert test_instance.exists() is True
    assert test_instance.is_running() is False
