#
# Copyright 2021 Canonical Ltd.
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

import io
import pathlib
import subprocess

import pytest

from craft_providers.multipass import MultipassInstance

from . import conftest


@pytest.fixture()
def instance(instance_name):
    with conftest.tmp_instance(
        instance_name=instance_name,
    ) as tmp_instance:
        yield MultipassInstance(name=tmp_instance)


@pytest.fixture(scope="module")
def reusable_instance(reusable_instance_name):
    """Reusable instance for tests that don't require a fresh instance."""
    with conftest.tmp_instance(
        instance_name=reusable_instance_name,
    ) as tmp_instance:
        yield MultipassInstance(name=tmp_instance)


@pytest.mark.parametrize("content", [b"", b"\x00\xaa\xbb\xcc", "test-string".encode()])
@pytest.mark.parametrize("mode", ["644", "600", "755"])
@pytest.mark.parametrize("user,group", [("root", "root"), ("ubuntu", "ubuntu")])
def test_push_file_io(reusable_instance, content, mode, user, group):
    reusable_instance.push_file_io(
        destination=pathlib.Path("/tmp/create-file-test.txt"),
        content=io.BytesIO(content),
        file_mode=mode,
        user=user,
        group=group,
    )

    proc = reusable_instance.execute_run(
        command=["cat", "/tmp/create-file-test.txt"],
        capture_output=True,
    )

    assert proc.stdout == content

    proc = reusable_instance.execute_run(
        command=["stat", "--format", "%a:%U:%G", "/tmp/create-file-test.txt"],
        capture_output=True,
        text=True,
    )

    assert proc.stdout.strip() == f"{mode}:{user}:{group}"


def test_delete(instance):
    assert instance.exists() is True

    instance.delete()

    assert instance.exists() is False


def test_execute_popen(reusable_instance):
    with reusable_instance.execute_popen(
        command=["pwd"],
        stdout=subprocess.PIPE,
        text=True,
    ) as proc:
        stdout, _ = proc.communicate()

    assert stdout.strip() == "/home/ubuntu"


def test_execute_popen_cwd(reusable_instance):
    with reusable_instance.execute_popen(
        command=["pwd"],
        cwd=pathlib.Path("/"),
        stdout=subprocess.PIPE,
        text=True,
    ) as proc:
        stdout, _ = proc.communicate()

    assert stdout.strip() == "/"


def test_execute_run(reusable_instance):
    proc = reusable_instance.execute_run(
        command=["pwd"],
        capture_output=True,
        text=True,
    )

    assert proc.stdout.strip() == "/home/ubuntu"


def test_execute_run_cwd(reusable_instance):
    proc = reusable_instance.execute_run(
        command=["pwd"],
        cwd=pathlib.Path("/"),
        capture_output=True,
        text=True,
    )

    assert proc.stdout.strip() == "/"


def test_exists(reusable_instance):
    assert reusable_instance.exists() is True


def test_exists_false():
    fake_instance = MultipassInstance(name="does-not-exist")

    assert fake_instance.exists() is False


def test_launch(instance_name):
    instance = MultipassInstance(name=instance_name)

    assert instance.exists() is False

    instance.launch(
        image="snapcraft:core20",
        cpus=4,
        disk_gb=128,
        mem_gb=1,
    )

    assert instance.exists() is True


def test_mount_unmount(reusable_instance, home_tmp_path):
    host_source = home_tmp_path
    target = pathlib.Path("/tmp/mnt")

    test_file = host_source / "test.txt"
    test_file.write_text("this is a test")

    assert reusable_instance.is_mounted(host_source=host_source, target=target) is False

    reusable_instance.mount(host_source=host_source, target=target)

    assert reusable_instance.is_mounted(host_source=host_source, target=target) is True

    proc = reusable_instance.execute_run(
        command=["cat", "/tmp/mnt/test.txt"],
        capture_output=True,
    )

    assert proc.stdout == test_file.read_bytes()

    reusable_instance.unmount(target=target)

    assert reusable_instance.is_mounted(host_source=host_source, target=target) is False


def test_mount_unmount_all(reusable_instance, home_tmp_path):
    host_source_1 = home_tmp_path / "1"
    host_source_1.mkdir()
    target_1 = pathlib.Path("/tmp/mnt/1")

    host_source_2 = home_tmp_path / "2"
    host_source_2.mkdir()
    target_2 = pathlib.Path("/tmp/mnt/2")

    reusable_instance.mount(host_source=host_source_1, target=target_1)
    reusable_instance.mount(host_source=host_source_2, target=target_2)

    assert (
        reusable_instance.is_mounted(host_source=host_source_1, target=target_1) is True
    )
    assert (
        reusable_instance.is_mounted(host_source=host_source_2, target=target_2) is True
    )

    reusable_instance.unmount_all()

    assert (
        reusable_instance.is_mounted(host_source=host_source_1, target=target_1)
        is False
    )
    assert (
        reusable_instance.is_mounted(host_source=host_source_2, target=target_2)
        is False
    )


def test_start_stop_is_running(reusable_instance):
    assert reusable_instance.is_running() is True

    reusable_instance.stop()

    assert reusable_instance.is_running() is False

    reusable_instance.start()

    assert reusable_instance.is_running() is True
