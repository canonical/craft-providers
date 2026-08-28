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
    BASE_INSTANCE_START_STRING,
    HookError,
    HookHelper,
    LXDInstance,
    configure_hook,
    remove_hook,
)

PROJECT_NAME = "fakeproj"


def test_base_instance_start_string():
    """Verify BASE_INSTANCE_START_STRING is exported and correct."""
    assert BASE_INSTANCE_START_STRING == "base-instance"


def test_no_projects(monkeypatch: pytest.MonkeyPatch):
    """Make sure HookError is raised if there is no corresponding lxc project."""
    monkeypatch.setattr(HookHelper, "_check_has_lxd", MagicMock())

    helper = object.__new__(HookHelper)
    helper._project_name = PROJECT_NAME
    helper._lxc = MagicMock()
    helper._lxc.project_list.return_value = []

    with pytest.raises(HookError) as e:
        HookHelper._check_project_exists(helper)
    assert f"Project {PROJECT_NAME} does not exist in LXD" in str(e)


@pytest.mark.parametrize(
    ("method_name", "invoke"),
    [
        ("delete", lambda h: h.delete_instance(
            LXDInstance(name="i", expanded_config={})
        )),
        ("image_list", lambda h: h.delete_all_images()),
        ("project_delete", lambda h: h.delete_project()),
        ("list", lambda h: h.list_instances()),
    ],
)
def test_file_not_found_wrapped_as_hookerror(
    monkeypatch: pytest.MonkeyPatch, method_name, invoke
):
    """FileNotFoundError from LXC calls is surfaced as HookError('LXD is not installed.')."""
    monkeypatch.setattr(HookHelper, "_check_has_lxd", MagicMock())
    monkeypatch.setattr(HookHelper, "_check_project_exists", MagicMock())

    helper = HookHelper(project_name=PROJECT_NAME, simulate=False, debug=False)
    helper._lxc = MagicMock()
    getattr(helper._lxc, method_name).side_effect = FileNotFoundError()

    with pytest.raises(HookError, match="LXD is not installed."):
        invoke(helper)


def test_check_project_exists_file_not_found(monkeypatch: pytest.MonkeyPatch):
    """FileNotFoundError from project_list is surfaced as HookError."""
    monkeypatch.setattr(HookHelper, "_check_has_lxd", MagicMock())

    helper = object.__new__(HookHelper)
    helper._project_name = PROJECT_NAME
    helper._lxc = MagicMock()
    helper._lxc.project_list.side_effect = FileNotFoundError()

    with pytest.raises(HookError, match="LXD is not installed."):
        HookHelper._check_project_exists(helper)


@pytest.fixture
def fake_hookhelper(monkeypatch: pytest.MonkeyPatch):
    def fake_hookhelper(instance_list):
        monkeypatch.setattr(
            HookHelper, "_check_project_exists", MagicMock()
        )
        monkeypatch.setattr(HookHelper, "_check_has_lxd", MagicMock())
        helper = HookHelper(project_name=PROJECT_NAME, simulate=False, debug=True)

        helper._lxc = MagicMock()
        helper._lxc.list.return_value = instance_list
        helper._lxc.image_list.return_value = []

        monkeypatch.setattr(helper, "delete_instance", MagicMock())
        monkeypatch.setattr(helper, "delete_project", MagicMock())
        monkeypatch.setattr(helper, "delete_all_images", MagicMock())
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
