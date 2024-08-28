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

import pytest
from craft_providers import multipass
from craft_providers.bases import ubuntu


@pytest.fixture
def simple_file(home_tmp_path):
    """Create a file in the home directory (accessible by Multipass)."""
    file = home_tmp_path / "src.txt"
    file.write_text("this is a test")
    return file


@pytest.mark.smoketest
def test_smoketest(instance_name, home_tmp_path):
    """Launch an instance and run some basic tasks."""

    assert multipass.is_installed()

    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    instance = multipass.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name="snapcraft:core22",
        cpus=2,
        disk_gb=8,
        mem_gb=4,
    )

    try:
        assert isinstance(instance, multipass.MultipassInstance)
        assert instance.exists() is True
        assert instance.is_running() is True

        # test execute command
        proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)
        assert proc.stdout == b"hi\n"

        # test push file
        test_file = pathlib.Path(home_tmp_path / "src.txt")
        test_file.write_text("this is a test")
        test_file.chmod(0o755)
        destination = pathlib.Path("/tmp/test.txt")
        test_file_pull = pathlib.Path(home_tmp_path / "src2.txt")

        instance.push_file(source=test_file, destination=destination)

        proc = instance.execute_run(
            command=["cat", str(destination)], capture_output=True
        )
        assert proc.stdout.decode() == "this is a test"

        proc = instance.execute_run(
            command=["stat", "--format", "%a:%U:%G", str(destination)],
            capture_output=True,
            text=True,
        )
        assert proc.stdout.strip() == "755:ubuntu:ubuntu"

        # test pull file
        instance.pull_file(source=destination, destination=test_file_pull)
        assert test_file.read_bytes() == test_file_pull.read_bytes()

        # test mount and unmount
        target = pathlib.Path("/tmp/mnt")
        assert instance.is_mounted(host_source=home_tmp_path, target=target) is False

        instance.mount(host_source=home_tmp_path, target=target)
        assert instance.is_mounted(host_source=home_tmp_path, target=target) is True

        proc = instance.execute_run(
            command=["cat", "/tmp/mnt/src.txt"],
            capture_output=True,
        )
        assert proc.stdout == test_file.read_bytes()

        instance.unmount(target=target)
        assert instance.is_mounted(host_source=home_tmp_path, target=target) is False

        # test stop instance
        instance.stop()
        assert instance.is_running() is False
    finally:
        instance.delete()

    # test delete instance
    assert instance.exists() is False


@pytest.mark.smoketest
def test_multipass_noble_failure(instance_name):
    """Test that Multipass<1.14.1 fails for Ubuntu 24.04 (Noble).

    This test acts as an xfail - it will start failing once Multipass 1.14.1 is released
    on homebrew and can be removed (#628).
    """
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.NOBLE)
    error = (
        r"Multipass '\d+\.\d+\.\d+' does not support Ubuntu 24\.04 \(Noble\)\.\n"
        r"Upgrade to Multipass 1\.14\.1 or newer\."
    )

    assert multipass.is_installed()

    with pytest.raises(multipass.MultipassError, match=error):
        multipass.launch(
            name=instance_name,
            base_configuration=base_configuration,
            image_name="snapcraft:core24",
            cpus=2,
            disk_gb=8,
            mem_gb=4,
        )
