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

import io
import subprocess

import pytest


def test_exec(instance, multipass):
    proc = multipass.exec(
        instance_name=instance.name,
        command=["echo", "this is a test"],
        capture_output=True,
    )

    assert proc.stdout == b"this is a test\n"


def test_delete(instance, multipass):
    multipass.delete(instance_name=instance.name, purge=False)

    info = multipass.info(instance_name=instance.name)

    assert info["info"][instance.name]["state"] == "Deleted"


def test_delete_purge(instance, multipass):
    multipass.delete(instance_name=instance.name, purge=True)

    instances = multipass.list()

    assert instance.name not in instances


def test_list(instance, multipass):
    instances = multipass.list()

    assert instance.name in instances


def test_mount_umount(instance, multipass, home_tmp_path):
    mount_target = f"{instance.name}:/tmp/mount-dir"
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.mount(
        source=home_tmp_path,
        target=mount_target,
    )

    proc = multipass.exec(
        command=["cat", "/tmp/mount-dir/test.txt"],
        instance_name=instance.name,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"

    multipass.umount(
        mount=mount_target,
    )

    with pytest.raises(subprocess.CalledProcessError):
        proc = multipass.exec(
            command=["test", "-f", "/tmp/mount-dir/test.txt"],
            instance_name=instance.name,
            check=True,
        )


def test_stop_start(instance, multipass):
    info = multipass.info(instance_name=instance.name)
    assert info["info"][instance.name]["state"] == "Running"

    multipass.stop(instance_name=instance.name)

    info = multipass.info(instance_name=instance.name)
    assert info["info"][instance.name]["state"] == "Stopped"

    multipass.start(instance_name=instance.name)

    info = multipass.info(instance_name=instance.name)
    assert info["info"][instance.name]["state"] == "Running"

    multipass.stop(instance_name=instance.name)

    info = multipass.info(instance_name=instance.name)
    assert info["info"][instance.name]["state"] == "Stopped"


def test_transfer_in(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance.name}:/tmp/foo",
    )

    proc = multipass.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance.name,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"


def test_transfer_out(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance.name}:/tmp/foo",
    )

    out_path = home_tmp_path / "out.txt"

    multipass.transfer(
        source=f"{instance.name}:/tmp/foo",
        destination=str(out_path),
    )

    assert out_path.read_text() == "this is a test"


def test_transfer_destination_io(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance.name}:/tmp/foo",
    )

    out_path = home_tmp_path / "out.txt"
    with out_path.open("wb") as stream:
        multipass.transfer_destination_io(
            source=f"{instance.name}:/tmp/foo",
            destination=stream,
        )

    assert out_path.read_text() == "this is a test"


def test_transfer_source_io(instance, multipass):
    test_io = io.BytesIO(b"this is a test")

    multipass.transfer_source_io(
        source=test_io,
        destination=f"{instance.name}:/tmp/foo",
    )

    proc = multipass.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance.name,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    assert proc.stdout == b"this is a test"
