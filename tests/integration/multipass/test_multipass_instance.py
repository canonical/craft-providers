# Copyright (C) 2021 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pathlib

import pytest

from craft_providers.multipass import MultipassInstance


@pytest.mark.parametrize("user,group", [("root", "root"), ("ubuntu", "ubuntu")])
@pytest.mark.parametrize("mode", ["0644", "0600", "0755"])
def test_create_file(reusable_instance, user, group, mode):
    reusable_instance.create_file(
        destination=pathlib.Path("/tmp/create-file-test.txt"),
        content="test data".encode(),
        file_mode=mode,
        user=user,
        group=group,
    )

    proc = reusable_instance.execute_run(
        command=["cat", "/tmp/create-file-test.txt"],
        capture_output=True,
    )

    assert proc.stdout == b"test data"


def test_delete(instance):
    instance.delete(purge=False)

    info = instance.get_info()

    assert info["state"] == "Deleted"


def test_delete_purge(instance):
    instance.delete(purge=True)

    info = instance.get_info()

    assert info is None
    assert instance.exists() is False


def test_exists(reusable_instance):
    assert reusable_instance.exists() is True


def test_exists_false(multipass):
    fake_instance = MultipassInstance(name="does-not-exist", multipass=multipass)

    assert fake_instance.exists() is False


def test_get_info(reusable_instance):
    assert reusable_instance.get_info()


def test_get_info_none(multipass):
    fake_instance = MultipassInstance(name="does-not-exist", multipass=multipass)

    assert fake_instance.get_info() is None


def test_launch(multipass, instance_name):
    instance = MultipassInstance(name=instance_name, multipass=multipass)

    assert instance.exists() is False

    instance.launch(
        image="snapcraft:core",
        cpus=4,
        disk_gb=128,
        mem_gb=1,
    )

    assert instance.exists() is True


def test_mount_is_mounted(instance, home_tmp_path):
    host_source = home_tmp_path
    target = pathlib.Path("/tmp/mnt")

    test_file = host_source / "test.txt"
    test_file.write_text("this is a test")

    assert instance.is_mounted(host_source=host_source, target=target) is False

    instance.mount(host_source=host_source, target=target)

    assert instance.is_mounted(host_source=host_source, target=target) is True

    proc = instance.execute_run(
        command=["cat", "/tmp/mnt/test.txt"],
        capture_output=True,
    )

    assert proc.stdout == test_file.read_bytes()


def test_start_stop_is_running(instance):
    assert instance.is_running() is True

    instance.stop()

    assert instance.is_running() is False

    instance.start()

    assert instance.is_running() is True


def test_supports_mount(reusable_instance):
    assert reusable_instance.supports_mount() is True
