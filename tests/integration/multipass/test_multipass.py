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
import subprocess

import pytest
from craft_providers.multipass import Multipass

from . import conftest


@pytest.fixture
def instance(instance_name):
    with conftest.tmp_instance(
        instance_name=instance_name,
    ) as tmp_instance:
        yield tmp_instance


@pytest.fixture
def multipass():
    return Multipass()


def test_delete(instance, multipass):
    multipass.delete(instance_name=instance, purge=False)

    info = multipass.info(instance_name=instance)

    assert info["info"][instance]["state"] == "Deleted"


def test_delete_purge(instance, multipass):
    multipass.delete(instance_name=instance, purge=True)

    instances = multipass.list()

    assert instance not in instances


def test_exec(instance, multipass):
    proc = multipass.exec(
        instance_name=instance,
        command=["echo", "this is a test"],
        capture_output=True,
    )

    assert proc.stdout == b"this is a test\n"


def test_is_supported_version(multipass):
    assert multipass.is_supported_version() is True


def test_list(instance, multipass):
    instances = multipass.list()

    assert instance in instances


def test_mount_umount(instance, multipass, home_tmp_path):
    mount_target = f"{instance}:/tmp/mount-dir"
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.mount(
        source=home_tmp_path,
        target=mount_target,
    )

    proc = multipass.exec(
        command=["cat", "/tmp/mount-dir/test.txt"],
        instance_name=instance,
        capture_output=True,
        check=True,
    )

    assert proc.stdout == b"this is a test"

    multipass.umount(
        mount=mount_target,
    )

    with pytest.raises(subprocess.CalledProcessError):
        proc = multipass.exec(
            command=["test", "-f", "/tmp/mount-dir/test.txt"],
            instance_name=instance,
            check=True,
        )


def test_stop_start(instance, multipass):
    info = multipass.info(instance_name=instance)
    assert info["info"][instance]["state"] == "Running"

    multipass.stop(instance_name=instance)

    info = multipass.info(instance_name=instance)
    assert info["info"][instance]["state"] == "Stopped"

    multipass.start(instance_name=instance)

    info = multipass.info(instance_name=instance)
    assert info["info"][instance]["state"] == "Running"

    multipass.stop(instance_name=instance)

    info = multipass.info(instance_name=instance)
    assert info["info"][instance]["state"] == "Stopped"


def test_transfer_in(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance}:/tmp/foo",
    )

    proc = multipass.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance,
        capture_output=True,
        check=True,
    )

    assert proc.stdout == b"this is a test"


def test_transfer_out(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance}:/tmp/foo",
    )

    out_path = home_tmp_path / "out.txt"

    multipass.transfer(
        source=f"{instance}:/tmp/foo",
        destination=str(out_path),
    )

    assert out_path.read_text() == "this is a test"


def test_transfer_destination_io(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"
    test_file.write_text("this is a test")

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance}:/tmp/foo",
    )

    out_path = home_tmp_path / "out.txt"
    with out_path.open("wb") as stream:
        multipass.transfer_destination_io(
            source=f"{instance}:/tmp/foo",
            destination=stream,
        )

    assert out_path.read_text() == "this is a test"


@pytest.mark.slow
def test_transfer_destination_io_large(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"

    with test_file.open("wb") as stream:
        stream.seek(1024 * 1024 * 100)
        stream.write(b"test")

    assert test_file.stat().st_size == 104857604

    multipass.transfer(
        source=str(test_file),
        destination=f"{instance}:/tmp/foo",
    )

    out_path = home_tmp_path / "out.txt"
    with out_path.open("wb") as stream:
        multipass.transfer_destination_io(
            source=f"{instance}:/tmp/foo",
            destination=stream,
        )

    assert out_path.stat().st_size == 104857604


def test_transfer_source_io(instance, multipass):
    test_io = io.BytesIO(b"this is a test")

    multipass.transfer_source_io(
        source=test_io,
        destination=f"{instance}:/tmp/foo",
    )

    proc = multipass.exec(
        command=["cat", "/tmp/foo"],
        instance_name=instance,
        capture_output=True,
        check=True,
    )

    assert proc.stdout == b"this is a test"


@pytest.mark.slow
def test_transfer_source_io_large(instance, multipass, home_tmp_path):
    test_file = home_tmp_path / "test.txt"

    with test_file.open("wb") as stream:
        stream.seek(1024 * 1024 * 100)
        stream.write(b"test")

    with test_file.open("rb") as stream:
        multipass.transfer_source_io(
            source=stream,
            destination=f"{instance}:/tmp/foo",
        )

    proc = multipass.exec(
        command=["du", "--bytes", "/tmp/foo"],
        instance_name=instance,
        capture_output=True,
        check=True,
    )

    assert proc.stdout == b"104857604\t/tmp/foo\n"


def test_wait_until_ready(multipass):
    multipass_version, multipassd_version = multipass.wait_until_ready()

    assert multipass_version is not None
    assert multipassd_version is not None


def test_version(multipass):
    multipass_version, multipassd_version = multipass.version()

    assert multipass_version is not None
    assert multipassd_version is not None
