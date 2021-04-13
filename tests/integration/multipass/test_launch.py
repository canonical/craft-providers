# Copyright 2021 Canonical Ltd.
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

import subprocess
import sys

import pytest

from craft_providers import multipass
from craft_providers.bases import BuilddBase, BuilddBaseAlias

from . import conftest


@pytest.fixture()
def core20_instance():
    with conftest.tmp_instance(
        instance_name=conftest.generate_instance_name(),
        image_name="snapcraft:core20",
    ) as tmp_instance:
        yield multipass.MultipassInstance(name=tmp_instance)


@pytest.mark.parametrize(
    "alias,image_name",
    [
        # TODO: add test when Multipass supports core on Windows
        pytest.param(
            BuilddBaseAlias.XENIAL,
            "snapcraft:core",
            marks=pytest.mark.skipif(
                sys.platform == "win32", reason="unsupported on windows"
            ),
        ),
        (BuilddBaseAlias.BIONIC, "snapcraft:core18"),
        (BuilddBaseAlias.FOCAL, "snapcraft:core20"),
    ],
)
def test_launch(instance_name, alias, image_name):
    base_configuration = BuilddBase(alias=alias)

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
    base_configuration = BuilddBase(alias=BuilddBaseAlias.FOCAL)

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
