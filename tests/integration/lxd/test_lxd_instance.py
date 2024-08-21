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
from craft_providers.lxd import LXDInstance

from . import conftest

pytestmark = [
    # These tests are flaky on very busy systems.
    # https://github.com/lxc/lxd/issues/11422
    # https://github.com/lxc/lxd/issues/11890
    pytest.mark.flaky(reruns=2, reruns_delay=1),
]


@pytest.fixture
def instance(instance_name, project):
    with conftest.tmp_instance(
        name=instance_name,
        project=project,
    ):
        instance = LXDInstance(name=instance_name, project=project)

        yield instance


@pytest.fixture(
    scope="module",
    params=[
        pytest.param(version, marks=pytest.mark.xdist_group(name=version))
        for version in ["18.04", "20.04", "22.04", "23.04"]
    ],
)
def reusable_instance(reusable_instance_name, request):
    """Reusable instance for tests that don't require a fresh instance."""
    name = f"{reusable_instance_name}-reusable-{request.param}"
    with conftest.tmp_instance(
        name=name,
        image=request.param,
        ephemeral=False,
        project="default",
    ):
        instance = LXDInstance(name=name, project="default")

        yield instance


@pytest.mark.parametrize("content", [b"", b"\x00\xaa\xbb\xcc", b"test-string"])
@pytest.mark.parametrize("mode", ["644", "600", "755"])
@pytest.mark.parametrize(("user", "group"), [("root", "root"), ("ubuntu", "ubuntu")])
def test_push_file_io(reusable_instance, content, mode, user, group):
    try:
        reusable_instance.push_file_io(
            destination=pathlib.PurePosixPath("/tmp/file-test.txt"),
            content=io.BytesIO(content),
            file_mode=mode,
            user=user,
            group=group,
        )

        proc = reusable_instance.execute_run(
            command=["cat", "/tmp/file-test.txt"],
            capture_output=True,
        )

        assert proc.stdout == content

        proc = reusable_instance.execute_run(
            command=["stat", "--format", "%a:%U:%G", "/tmp/file-test.txt"],
            capture_output=True,
            text=True,
        )

        assert proc.stdout.strip() == f"{mode}:{user}:{group}"
    finally:
        reusable_instance.execute_run(
            command=["rm", "-f", "/tmp/file-test.txt"],
            capture_output=True,
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

    assert stdout.strip() == "/root"


def test_execute_popen_cwd(reusable_instance):
    with reusable_instance.execute_popen(
        command=["pwd"],
        cwd=pathlib.PurePosixPath("/tmp"),
        stdout=subprocess.PIPE,
        text=True,
    ) as proc:
        stdout, _ = proc.communicate()

    assert stdout.strip() == "/tmp"


def test_execute_run(reusable_instance):
    proc = reusable_instance.execute_run(
        command=["pwd"],
        capture_output=True,
        text=True,
    )

    assert proc.stdout.strip() == "/root"


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
    fake_instance = LXDInstance(name="does-not-exist")

    assert fake_instance.exists() is False


def test_launch(instance_name):
    instance = LXDInstance(name=instance_name)

    assert instance.exists() is False

    instance.launch(
        image="20.04",
        image_remote="ubuntu",
    )

    try:
        assert instance.exists() is True
    finally:
        instance.delete()


@pytest.mark.parametrize(
    "name",
    [
        "test-name",
        "more-than-63-characters-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "more-than-63-characters-and-invalid-characters-$$$xxxxxxxxxxxxxxxxxxxx",
        "invalid-characters-$$$",
    ],
)
def test_launch_with_name(instance_name, name):
    """Verify we can launch an instance even when we pass in an invalid name."""
    # prepend the tester's random instance name
    name = f"{instance_name}-{name}"
    instance = LXDInstance(name=name)

    assert instance.exists() is False

    instance.launch(
        image="20.04",
        image_remote="ubuntu",
    )

    try:
        assert instance.exists() is True
    finally:
        instance.delete()


def test_mount_unmount(reusable_instance, tmp_path):
    tmp_path.chmod(0o755)

    host_source = tmp_path
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


def test_mount_unmount_all(reusable_instance, tmp_path):
    tmp_path.chmod(0o755)

    source1 = tmp_path / "1"
    source1.mkdir()
    target_1 = pathlib.PurePosixPath("/tmp/mnt/1")

    source2 = tmp_path / "2"
    source2.mkdir()
    target_2 = pathlib.PurePosixPath("/tmp/mnt/2")

    reusable_instance.mount(host_source=source1, target=target_1)
    reusable_instance.mount(host_source=source2, target=target_2)

    assert reusable_instance.is_mounted(host_source=source1, target=target_1) is True
    assert reusable_instance.is_mounted(host_source=source2, target=target_2) is True

    reusable_instance.unmount_all()

    assert reusable_instance.is_mounted(host_source=source1, target=target_1) is False
    assert reusable_instance.is_mounted(host_source=source2, target=target_2) is False


def test_start_stop(reusable_instance):
    assert reusable_instance.is_running() is True

    reusable_instance.stop()

    assert reusable_instance.is_running() is False

    reusable_instance.start()

    assert reusable_instance.is_running() is True


def test_info(reusable_instance):
    info = reusable_instance.info()

    assert info.get("Name") == reusable_instance.instance_name
