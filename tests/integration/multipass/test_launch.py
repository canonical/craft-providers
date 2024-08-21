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
from craft_providers import multipass
from craft_providers.bases import ubuntu
from craft_providers.errors import BaseCompatibilityError

from . import conftest

pytestmark = [pytest.mark.xdist_group("multipass_launch_tests")]


@pytest.fixture
def core22_instance(instance_name):
    """Yields a minimally setup core22 instance.

    The yielded instance will be launched, started, and marked as setup, even though
    most of the setup is skipped to speed up test execution.

    Delete instance on fixture teardown.
    """
    with conftest.tmp_instance(
        instance_name=instance_name,
        image_name="snapcraft:core22",
    ) as tmp_instance:
        instance = multipass.MultipassInstance(name=tmp_instance)

        # mark instance as setup in the config file
        instance.push_file_io(
            destination=ubuntu.BuilddBase._instance_config_path,
            content=io.BytesIO(
                f"compatibility_tag: {ubuntu.BuilddBase.compatibility_tag}"
                "\nsetup: true\n".encode()
            ),
            file_mode="0644",
        )

        yield instance

        if instance.exists():
            instance.delete()


def test_launch(instance_name):
    """Launch an instance and run a command inside the instance."""
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    instance = multipass.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name="snapcraft:core22",
        disk_gb=16,
    )

    try:
        assert isinstance(instance, multipass.MultipassInstance)
        assert instance.exists() is True
        assert instance.is_running() is True

        proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

        assert proc.stdout == b"hi\n"
    finally:
        instance.delete()


def test_launch_existing_instance(core22_instance):
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    instance = multipass.launch(
        name=core22_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core22",
        disk_gb=16,
    )

    assert isinstance(instance, multipass.MultipassInstance)
    assert instance.exists() is True
    assert instance.is_running() is True

    proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

    assert proc.stdout == b"hi\n"


def test_launch_os_incompatible_instance(core22_instance):
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    core22_instance.push_file_io(
        destination=pathlib.PurePosixPath("/etc/os-release"),
        content=io.BytesIO(b"NAME=Fedora\nVERSION_ID=32\n"),
        file_mode="0644",
    )

    # Should raise compatibility error with auto_clean=False.
    with pytest.raises(BaseCompatibilityError) as exc_info:
        multipass.launch(
            name=core22_instance.name,
            base_configuration=base_configuration,
            image_name="snapcraft:core22",
        )

    assert (
        exc_info.value.brief
        == "Incompatible base detected: Expected OS 'Ubuntu', found 'Fedora'."
    )

    # Retry with auto_clean=True.
    multipass.launch(
        name=core22_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core22",
        disk_gb=16,
        auto_clean=True,
    )

    assert core22_instance.exists() is True
    assert core22_instance.is_running() is True


def test_launch_instance_config_incompatible_instance(core22_instance):
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    core22_instance.push_file_io(
        destination=base_configuration._instance_config_path,
        content=io.BytesIO(b"compatibility_tag: invalid\nsetup: true\n"),
        file_mode="0644",
    )

    # Should raise compatibility error with auto_clean=False.
    with pytest.raises(BaseCompatibilityError) as exc_info:
        multipass.launch(
            name=core22_instance.name,
            base_configuration=base_configuration,
            image_name="snapcraft:core22",
        )

    assert exc_info.value.brief == (
        "Incompatible base detected:"
        " Expected image compatibility tag 'buildd-base-v7', found 'invalid'."
    )

    # Retry with auto_clean=True.
    multipass.launch(
        name=core22_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core22",
        disk_gb=16,
        auto_clean=True,
    )

    assert core22_instance.exists() is True
    assert core22_instance.is_running() is True


def test_launch_instance_not_setup_without_auto_clean(core22_instance):
    """Raise an error if an existing instance is not setup and auto_clean is False."""
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    core22_instance.push_file_io(
        destination=base_configuration._instance_config_path,
        content=io.BytesIO(b"compatibility_tag: buildd-base-v7\nsetup: false\n"),
        file_mode="0644",
    )

    # will raise a compatibility error
    with pytest.raises(BaseCompatibilityError) as exc_info:
        multipass.launch(
            name=core22_instance.name,
            base_configuration=base_configuration,
            image_name="snapcraft:core22",
            auto_clean=False,
        )

    assert exc_info.value == BaseCompatibilityError("instance is marked as not setup")


def test_launch_instance_not_setup_with_auto_clean(core22_instance):
    """Clean the instance if it is not setup and auto_clean is True."""
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    core22_instance.push_file_io(
        destination=base_configuration._instance_config_path,
        content=io.BytesIO(b"compatibility_tag: buildd-base-v7\nsetup: false\n"),
        file_mode="0644",
    )

    # when auto_clean is true, the instance will be deleted and recreated
    multipass.launch(
        name=core22_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core22",
        disk_gb=16,
        auto_clean=True,
    )

    assert core22_instance.exists() is True
    assert core22_instance.is_running() is True
