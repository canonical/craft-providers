#
# Copyright 2021 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
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

import pytest

from craft_providers.lxd import LXDError

from . import conftest


@pytest.fixture()
def instance(instance_name, project):
    with conftest.tmp_instance(
        instance_name=instance_name,
        project=project,
    ) as tmp_instance:
        yield tmp_instance


def test_exec(instance, lxc, project):
    proc = lxc.exec(
        instance_name=instance,
        command=["echo", "this is a test"],
        project=project,
        capture_output=True,
    )

    assert proc.stdout == b"this is a test\n"


def test_delete(instance, lxc, project):
    with pytest.raises(LXDError):
        lxc.delete(instance_name=instance, force=False, project=project)

    instances = lxc.list_names(project=project)
    assert instances == [instance]


def test_delete_force(instance, lxc, project):
    lxc.delete(instance_name=instance, force=True, project=project)

    instances = lxc.list_names(project=project)
    assert instances == []


def test_image_copy(lxc, project):
    lxc.image_copy(
        image="16.04",
        image_remote="ubuntu",
        alias="test-1604",
        project=project,
    )

    images = lxc.image_list(project=project)
    assert len(images) == 1


def test_image_delete(lxc, project):
    lxc.image_copy(
        image="16.04",
        image_remote="ubuntu",
        alias="test-1604",
        project=project,
    )

    lxc.image_delete(image="test-1604", project=project)

    images = lxc.image_list(project=project)
    assert images == []


def test_file_push(instance, lxc, project, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.file_push(
        instance_name=instance,
        project=project,
        source=test_file,
        destination=pathlib.Path("/tmp/foo"),
    )

    proc = lxc.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance,
        project=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"


def test_file_pull(instance, lxc, project, tmp_path):
    out_path = tmp_path / "out.txt"
    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.file_push(
        instance_name=instance,
        project=project,
        source=test_file,
        destination=pathlib.Path("/tmp/foo"),
    )

    lxc.file_pull(
        instance_name=instance,
        project=project,
        source=pathlib.Path("/tmp/foo"),
        destination=out_path,
    )

    assert out_path.read_text() == "this is a test"


def test_disk_add_remove(instance, lxc, tmp_path, project):
    mount_target = pathlib.Path("/mnt")

    # Make sure permissions allow read from inside guest without mappings.
    tmp_path.chmod(0o755)

    test_file = tmp_path / "test.txt"
    test_file.write_text("this is a test")

    lxc.config_device_add_disk(
        instance_name=instance,
        source=tmp_path,
        path=mount_target,
        device="test_mount",
        project=project,
    )

    proc = lxc.exec(
        command=["cat", "/mnt/test.txt"],
        instance_name=instance,
        capture_output=True,
        check=True,
        project=project,
    )

    assert proc.stdout == b"this is a test"

    lxc.config_device_remove(
        instance_name=instance,
        device="test_mount",
        project=project,
    )

    with pytest.raises(subprocess.CalledProcessError):
        lxc.exec(
            command=["test", "-f", "/mnt/test.txt"],
            project=project,
            instance_name=instance,
            check=True,
        )
