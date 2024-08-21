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

import io
import pathlib
import subprocess

import pytest
from craft_providers.multipass import MultipassInstance

from . import conftest

# These tests can be flaky on a sufficiently busy system, because multipass will
# sometime fail to talk to the VM. If they fail, retry them after a short delay.
pytestmark = pytest.mark.flaky(reruns=3, reruns_delay=2)


@pytest.fixture
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


@pytest.fixture
def simple_file(home_tmp_path):
    """Create a file in the home directory (accessible by Multipass)."""
    file = home_tmp_path / "src.txt"
    file.write_text("this is a test")
    return file


@pytest.mark.parametrize("content", [b"", b"\x00\xaa\xbb\xcc", b"test-string"])
@pytest.mark.parametrize("mode", ["644", "600", "755"])
@pytest.mark.parametrize(("user", "group"), [("root", "root"), ("ubuntu", "ubuntu")])
def test_push_file_io(reusable_instance, content, mode, user, group):
    reusable_instance.push_file_io(
        destination=pathlib.PurePosixPath("/tmp/create-file-test.txt"),
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


@pytest.mark.parametrize(
    "destination",
    [
        pathlib.PurePosixPath("/tmp/push-file.txt"),
        pathlib.PurePosixPath("/home/ubuntu/push-file.txt"),
        pathlib.PurePosixPath("/root/push-file.txt"),
        pathlib.PurePosixPath("/push-file.txt"),
    ],
)
@pytest.mark.parametrize("mode", ["644", "600", "755"])
def test_push_file(destination, mode, reusable_instance, simple_file):
    """Push a file into a Multipass instance."""
    simple_file.chmod(int(mode, 8))

    reusable_instance.push_file(source=simple_file, destination=destination)

    # check file contents
    proc = reusable_instance.execute_run(
        command=["cat", str(destination)], capture_output=True
    )
    assert proc.stdout.decode() == "this is a test"
    # check file ownership
    proc = reusable_instance.execute_run(
        command=["stat", "--format", "%a:%U:%G", str(destination)],
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == f"{mode}:ubuntu:ubuntu"

    # clean up before the next test
    reusable_instance.execute_run(["rm", str(destination)])


@pytest.mark.parametrize(
    "destination",
    [
        pathlib.PurePosixPath("/"),
        pathlib.PurePosixPath("/home/ubuntu/"),
        pathlib.PurePosixPath("/root/"),
        pathlib.PurePosixPath("/tmp/"),
    ],
)
@pytest.mark.parametrize("mode", ["644", "600", "755"])
def test_push_file_to_directory(destination, mode, reusable_instance, simple_file):
    """Push a file to a directory in a multipass instance."""
    simple_file.chmod(int(mode, 8))
    final_destination = str(destination / simple_file.name)

    reusable_instance.push_file(source=simple_file, destination=destination)

    # check file contents
    proc = reusable_instance.execute_run(
        command=["cat", final_destination], capture_output=True
    )
    assert proc.stdout.decode() == "this is a test"
    # check file permissions
    proc = reusable_instance.execute_run(
        command=["stat", "--format", "%a:%U:%G", final_destination],
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == f"{mode}:ubuntu:ubuntu"

    # clean up before the next test
    reusable_instance.execute_run(["rm", final_destination])


def test_push_file_source_directory_error(reusable_instance, home_tmp_path):
    """Raise an error if the source is a directory."""
    with pytest.raises(IsADirectoryError) as exc_info:
        reusable_instance.push_file(
            source=home_tmp_path,
            destination=pathlib.PurePosixPath("/path/to/non/existent/directory"),
        )

    assert str(exc_info.value) == (
        f"Source cannot be a directory: {str(home_tmp_path)!r}"
    )


def test_push_file_no_source_error(reusable_instance, home_tmp_path):
    """Raise an error if the source file does not exist."""
    source = home_tmp_path / "src.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        reusable_instance.push_file(
            source=source,
            destination=pathlib.PurePosixPath("/path/to/non/existent/directory"),
        )

    assert str(exc_info.value) == f"File not found: {str(source)!r}"


def test_push_file_no_parent_directory_error(reusable_instance, simple_file):
    """Raise an error if the parent directory of the destination does not exist."""
    with pytest.raises(FileNotFoundError) as exc_info:
        reusable_instance.push_file(
            source=simple_file,
            destination=pathlib.PurePosixPath("/path/to/non/existent/directory"),
        )

    assert str(exc_info.value) == (
        "Directory not found in instance: '/path/to/non/existent'"
    )


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
        cwd=pathlib.PurePosixPath("/"),
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
        cwd=pathlib.PurePosixPath("/"),
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
        image="snapcraft:core22",
        cpus=4,
        disk_gb=16,
        mem_gb=1,
    )

    assert instance.exists() is True


def test_mount_unmount(reusable_instance, home_tmp_path):
    host_source = home_tmp_path
    target = pathlib.PurePosixPath("/tmp/mnt")

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
    target_1 = pathlib.PurePosixPath("/tmp/mnt/1")

    host_source_2 = home_tmp_path / "2"
    host_source_2.mkdir()
    target_2 = pathlib.PurePosixPath("/tmp/mnt/2")

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
