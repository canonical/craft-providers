#
# Copyright 2021-2023 Canonical Ltd.
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

import pathlib
import subprocess
from datetime import datetime

import pytest
from craft_providers.lxd import LXDError, lxd_instance_status

from . import conftest


@pytest.fixture
def instance(instance_name, session_project):
    with conftest.tmp_instance(
        name=instance_name, project=session_project
    ) as tmp_instance:
        yield tmp_instance


def test_launch_default_config(instance, lxc, session_project):
    """Verify default config values when launching."""
    status = lxc.config_get(
        instance_name=instance,
        key="user.craft_providers.status",
        project=session_project,
    )
    timer = lxc.config_get(
        instance_name=instance,
        key="user.craft_providers.timer",
        project=session_project,
    )
    pid = lxc.config_get(
        instance_name=instance,
        key="user.craft_providers.pid",
        project=session_project,
    )

    assert status in [
        status.value for status in lxd_instance_status.ProviderInstanceStatus
    ]
    # assert timer is a valid ISO datetime
    datetime.fromisoformat(timer)
    # assert PID is an integer
    int(pid)


def test_exec(instance, lxc, session_project):
    proc = lxc.exec(
        instance_name=instance,
        command=["echo", "this is a test"],
        project=session_project,
        capture_output=True,
    )

    assert proc.stdout == b"this is a test\n"


def test_config_get_and_set(instance, instance_name, lxc, session_project):
    """Set and get config key/value pairs."""
    lxc.config_set(
        instance_name=instance,
        key="user.test-key",  # `user` namespace is for arbitrary config values
        value="test-value",
        project=session_project,
    )

    value = lxc.config_get(
        instance_name=instance, key="user.test-key", project=session_project
    )

    assert value == "test-value"


def test_config_get_non_existent_key(instance, instance_name, lxc, session_project):
    """Get a non-existent key and confirm the value is an empty string."""
    value = lxc.config_get(
        instance_name=instance, key="non-existant-key", project=session_project
    )

    assert not value


def test_copy(instance, instance_name, lxc, session_project):
    """Test `copy()` with default arguments."""
    destination_instance_name = instance_name + "-destination"

    # copy the instance to a new instance
    lxc.copy(
        source_instance_name=instance,
        destination_instance_name=destination_instance_name,
        project=session_project,
    )

    instances = lxc.list_names(project=session_project)

    # verify both instances exist
    assert instances == [instance, destination_instance_name]


def test_copy_error(instance, instance_name, lxc, session_project):
    """Raise a LXDError when the copy command fails."""
    # the source and destination cannot be same, so LXC will fail to copy
    with pytest.raises(LXDError) as raised:
        lxc.copy(
            source_instance_name=instance,
            destination_instance_name=instance,
            project=session_project,
        )

    assert raised.value == LXDError(
        brief=(
            f"Failed to copy instance 'local:{instance_name}' to 'local:"
            f"{instance_name}'."
        ),
        details=(
            f"* Command that failed: 'lxc --project {session_project} copy local:"
            f"{instance_name} local:{instance_name}'\n"
            "* Command exit code: 1\n"
            "* Command standard error output: b'Error: Failed creating instance "
            f'record: Instance "{instance_name}" already exists\\n\''
        ),
    )


def test_delete(instance, lxc, session_project):
    with pytest.raises(LXDError):
        lxc.delete(instance_name=instance, force=False, project=session_project)

    instances = lxc.list_names(project=session_project)
    assert instance in instances


def test_delete_force(instance, lxc, session_project):
    lxc.delete(instance_name=instance, force=True, project=session_project)

    instances = lxc.list_names(project=session_project)
    assert instance not in instances


def test_image_copy(lxc, session_project):
    lxc.image_copy(
        image="22.04",
        image_remote="ubuntu",
        alias="test-2204",
        project=session_project,
    )

    images = lxc.image_list(project=session_project)
    assert len(images) == 1


def test_image_delete(lxc, session_project):
    lxc.image_copy(
        image="22.04",
        image_remote="ubuntu",
        alias="test-2204",
        project=session_project,
    )

    lxc.image_delete(image="test-2204", project=session_project)

    images = lxc.image_list(project=session_project)
    assert images == []


def test_file_push(instance, lxc, session_project, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.file_push(
        instance_name=instance,
        project=session_project,
        source=test_file,
        destination=pathlib.PurePosixPath("/tmp/foo"),
    )

    proc = lxc.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance,
        project=session_project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"


def test_file_pull(instance, lxc, session_project, tmp_path):
    out_path = tmp_path / "out.txt"
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.file_push(
        instance_name=instance,
        project=session_project,
        source=test_file,
        destination=pathlib.PurePosixPath("/tmp/foo"),
    )

    lxc.file_pull(
        instance_name=instance,
        project=session_project,
        source=pathlib.PurePosixPath("/tmp/foo"),
        destination=out_path,
    )

    assert out_path.read_text() == "this is a test"


def test_disk_add_remove(instance, lxc, tmp_path, session_project):
    mount_target = pathlib.PurePosixPath("/mnt")

    # Make sure permissions allow read from inside guest without mappings.
    tmp_path.chmod(0o755)

    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.config_device_add_disk(
        instance_name=instance,
        source=tmp_path,
        path=mount_target,
        device="test_mount",
        project=session_project,
    )

    proc = lxc.exec(
        command=["cat", "/mnt/test.txt"],
        instance_name=instance,
        capture_output=True,
        check=True,
        project=session_project,
    )

    assert proc.stdout == b"this is a test"

    lxc.config_device_remove(
        instance_name=instance,
        device="test_mount",
        project=session_project,
    )

    with pytest.raises(subprocess.CalledProcessError):
        lxc.exec(
            command=["test", "-f", "/mnt/test.txt"],
            project=session_project,
            instance_name=instance,
            check=True,
        )


def test_info(instance, lxc, session_project):
    """Test `info()` method works as expected."""
    data = lxc.info(instance_name=instance, project=session_project)

    assert data["Name"] == instance
