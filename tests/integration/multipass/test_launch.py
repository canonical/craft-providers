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

from craft_providers import bases, multipass

from . import conftest


@pytest.fixture()
def core20_instance(instance_name):
    with conftest.tmp_instance(
        instance_name=instance_name,
        image_name="snapcraft:core20",
    ) as tmp_instance:
        instance = multipass.MultipassInstance(name=tmp_instance)

        yield instance

        if instance.exists():
            instance.delete()


@pytest.mark.parametrize(
    "alias,image_name",
    [
        (bases.BuilddBaseAlias.BIONIC, "snapcraft:core18"),
        (bases.BuilddBaseAlias.FOCAL, "snapcraft:core20"),
        (bases.BuilddBaseAlias.JAMMY, "snapcraft:core22"),
    ],
)
def test_launch(instance_name, alias, image_name):
    base_configuration = bases.BuilddBase(alias=alias)

    instance = multipass.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name=image_name,
    )

    try:
        assert isinstance(instance, multipass.MultipassInstance)
        assert instance.exists() is True
        assert instance.is_running() is True

        proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

        assert proc.stdout == b"hi\n"
    finally:
        instance.delete()


def test_launch_existing_instance(core20_instance):
    base_configuration = bases.BuilddBase(alias=bases.BuilddBaseAlias.FOCAL)

    instance = multipass.launch(
        name=core20_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core20",
    )

    assert isinstance(instance, multipass.MultipassInstance)
    assert instance.exists() is True
    assert instance.is_running() is True

    proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

    assert proc.stdout == b"hi\n"


def test_launch_os_incompatible_instance(core20_instance):
    base_configuration = bases.BuilddBase(alias=bases.BuilddBaseAlias.FOCAL)

    core20_instance.push_file_io(
        destination=pathlib.Path("/etc/os-release"),
        content=io.BytesIO(b"NAME=Fedora\nVERSION_ID=32\n"),
        file_mode="0644",
    )

    # Should raise compatibility error with auto_clean=False.
    with pytest.raises(bases.BaseCompatibilityError) as exc_info:
        multipass.launch(
            name=core20_instance.name,
            base_configuration=base_configuration,
            image_name="snapcraft:core20",
        )

    assert (
        exc_info.value.brief
        == "Incompatible base detected: Expected OS 'Ubuntu', found 'Fedora'."
    )

    # Retry with auto_clean=True.
    multipass.launch(
        name=core20_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core20",
        auto_clean=True,
    )

    assert core20_instance.exists() is True
    assert core20_instance.is_running() is True


def test_launch_instance_config_incompatible_instance(core20_instance):
    base_configuration = bases.BuilddBase(alias=bases.BuilddBaseAlias.FOCAL)

    core20_instance.push_file_io(
        destination=base_configuration.instance_config_path,
        content=io.BytesIO(b"compatibility_tag: invalid\n"),
        file_mode="0644",
    )

    # Should raise compatibility error with auto_clean=False.
    with pytest.raises(bases.BaseCompatibilityError) as exc_info:
        multipass.launch(
            name=core20_instance.name,
            base_configuration=base_configuration,
            image_name="snapcraft:core20",
        )

    assert exc_info.value.brief == (
        "Incompatible base detected:"
        " Expected image compatibility tag 'buildd-base-v0', found 'invalid'."
    )

    # Retry with auto_clean=True.
    multipass.launch(
        name=core20_instance.name,
        base_configuration=base_configuration,
        image_name="snapcraft:core20",
        auto_clean=True,
    )

    assert core20_instance.exists() is True
    assert core20_instance.is_running() is True
