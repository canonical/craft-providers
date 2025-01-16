# Copyright 2024 Canonical Ltd.
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

from unittest.mock import MagicMock, call

import pytest
from craft_providers.hookutil import (
    HookError,
    HookHelper,
    LXDInstance,
    configure_hook,
    remove_hook,
)

PROJECT_NAME = "fakeproj"


def test_no_projects():
    """Make sure HookError is raised if there is no corresponding lxc project."""
    # Use our own mock HookHelper rather than the fixture, we need to do things a little
    # differently here
    HookHelper._check_has_lxd = MagicMock()
    original_lxc_func = HookHelper.lxc

    def fake_lxc(self, *args, **kwargs):
        if len(args) == 2 and args[0:2] == ("project", "list"):
            return []
        return original_lxc_func(*args, **kwargs)

    HookHelper.lxc = fake_lxc

    with pytest.raises(HookError) as e:
        HookHelper(project_name=PROJECT_NAME, simulate=False, debug=True)
    assert f"Project {PROJECT_NAME} does not exist in LXD" in str(e)


@pytest.fixture
def fake_hookhelper():
    def fake_hookhelper(instance_list):
        HookHelper._check_project_exists = MagicMock()  # raise nothing
        HookHelper._check_has_lxd = MagicMock()
        helper = HookHelper(project_name=PROJECT_NAME, simulate=False, debug=True)

        original_lxc_func = helper.lxc

        def fake_lxc(*args, **kwargs):
            if len(args) == 1 and args[0] == "list":
                return instance_list
            return original_lxc_func(*args, **kwargs)

        helper.lxc = fake_lxc

        helper.delete_instance = MagicMock()
        helper.delete_project = MagicMock()
        helper.delete_all_images = MagicMock()
        return helper

    return fake_hookhelper


def assert_instances_deleted(helper, instances):
    """Transform json list to instance calls for passing to assert_has_calls."""
    helper.delete_instance.assert_has_calls(
        [call(LXDInstance.unmarshal(instance)) for instance in instances],
        any_order=True,
    )


def test_configure_nothing_to_delete(fake_hookhelper):
    """Test the configure hook logic with mocked lxc calls."""
    instances = [
        {
            "name": f"base-instance-{PROJECT_NAME}-buildd-base-v7-c-a839ea97c42df2065713",
            "created_at": "2024-11-15T03:14:36.041502388Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24",
                "image.version": "24.04",
            },
        },
        {
            "name": f"{PROJECT_NAME}-busybox-gadget-on-amd64-for-amd64-13389833",
            "created_at": "2024-11-15T03:15:33.48330342Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24",
                "image.version": "24.04",
            },
        },
    ]
    helper = fake_hookhelper(instances)

    configure_hook(helper)

    helper.delete_instance.assert_not_called()
    helper.delete_project.assert_not_called()


def test_configure_simple_delete_superseded(fake_hookhelper):
    """Test a simple case where some images with out-of-date compat tags are deleted."""
    instances = [
        {
            "name": f"base-instance-{PROJECT_NAME}-buildd-base-v7-c-a839ea97c42df2065713",
            "created_at": "2024-11-15T03:14:36.041502388Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24",
                "image.version": "24.04",
            },
        },
        {
            "name": f"{PROJECT_NAME}-busybox-gadget-on-amd64-for-amd64-13389833",
            "created_at": "2024-11-15T03:15:33.48330342Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24",
                "image.version": "24.04",
            },
        },
        {
            "name": f"base-instance-{PROJECT_NAME}-buildd-base-v6-c-a839ea97c42df2065712",
            "created_at": "2024-11-15T02:14:36.041502388Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v6-craft-com.ubuntu.cloud-buildd-daily-core22",
                "image.version": "22.04",
            },
        },
        {
            "name": f"{PROJECT_NAME}-busybox-gadget-on-amd64-for-amd64-13389832",
            "created_at": "2024-11-15T02:15:33.48330342Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v6-craft-com.ubuntu.cloud-buildd-daily-core22",
                "image.version": "22.04",
            },
        },
    ]
    helper = fake_hookhelper(instances)
    configure_hook(helper)
    assert_instances_deleted(helper, instances[2:2])


def test_remove_simple_delete(fake_hookhelper):
    """Test the remove hook logic with mocked lxc calls."""
    instances = [
        {
            "name": f"base-instance-{PROJECT_NAME}-buildd-base-v7-c-a839ea97c42df2065713",
            "created_at": "2024-11-15T03:14:36.041502388Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24",
                "image.version": "24.04",
            },
        },
        {
            "name": f"{PROJECT_NAME}-busybox-gadget-on-amd64-for-amd64-13389833",
            "created_at": "2024-11-15T03:15:33.48330342Z",
            "expanded_config": {
                "image.description": f"base-instance-{PROJECT_NAME}-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24",
                "image.version": "24.04",
            },
        },
    ]
    helper = fake_hookhelper(instances)
    remove_hook(helper)
    assert_instances_deleted(helper, instances)
    helper.delete_all_images.assert_called_once()
    helper.delete_project.assert_called_once()
