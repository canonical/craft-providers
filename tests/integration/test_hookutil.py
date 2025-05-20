#
# Copyright 2025 Canonical Ltd.
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

"""Tests for snap hook utilities."""

import pytest
from craft_providers import lxd
from craft_providers.bases import ubuntu
from craft_providers.hookutil import HookError, HookHelper, configure_hook, remove_hook

pytestmark = [pytest.mark.slow]

FAKE_PROJECT = "boopcraft"


@pytest.fixture
def spawn_lxd_instance(installed_lxd):
    base_config = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    def spawn_lxd_instance(name, *, is_base_instance):
        """Create a long-lived LXD instance under our fake project."""
        return lxd.launch(
            name=name,
            base_configuration=base_config,
            image_name="22.04",
            image_remote="ubuntu",
            project=FAKE_PROJECT,
            auto_create_project=True,
            use_base_instance=not is_base_instance,
        )

    return spawn_lxd_instance


def test_configure_hook(spawn_lxd_instance):
    # Create a current non-base instance (the base instance is also created internally)
    current_instance = spawn_lxd_instance(
        "boopcraft-myproject-on-amd64-for-amd64-59510339",
        is_base_instance=False,
    )

    # Create an outdated instance that would have been created by craft-providers>=1.7.0<1.8.0
    outdated_base_instance = spawn_lxd_instance(
        "base-instance-buildd-base-v00--be83d276b0c767e3ad60",
        is_base_instance=True,
    )

    helper = HookHelper(project_name=FAKE_PROJECT, simulate=False, debug=True)
    configure_hook(helper)

    assert current_instance.exists(), "Current non-base instance should exist"
    assert not outdated_base_instance.exists(), (
        "Outdated base instance should not exist"
    )

    current_instance.delete()
    helper._check_project_exists()  # raises exception if project doesn't exist


def test_remove_hook(spawn_lxd_instance):
    # Create a current non-base instance (the base instance is also created internally)
    current_instance = spawn_lxd_instance(
        "boopcraft-myproject-on-amd64-for-amd64-59510339",
        is_base_instance=False,
    )

    # Create an outdated instance that would have been created by craft-providers>=1.7.0<1.8.0
    outdated_base_instance = spawn_lxd_instance(
        "base-instance-buildd-base-v00--be83d276b0c767e3ad60",
        is_base_instance=True,
    )

    helper = HookHelper(project_name=FAKE_PROJECT, simulate=False, debug=True)
    remove_hook(helper)

    assert not current_instance.exists(), "Current non-base instance should not exist"
    assert not outdated_base_instance.exists(), (
        "Outdated base instance should not exist"
    )

    with pytest.raises(HookError) as e:
        helper._check_project_exists()
        assert e == HookError(f"Project {FAKE_PROJECT} does not exist in LXD.")
