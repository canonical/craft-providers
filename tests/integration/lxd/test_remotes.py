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

import subprocess

import pytest

from craft_providers import lxd
from craft_providers.bases import BuilddBase, BuilddBaseAlias


# exclude XENIAL because it is not supported for LXD
@pytest.mark.parametrize("alias", set(BuilddBaseAlias) - {BuilddBaseAlias.XENIAL})
def test_configure_and_launch_remote(instance_name, alias):
    """Verify remotes are configured and images can be launched."""
    remote_image = lxd.get_remote_image(alias.value)
    base_configuration = BuilddBase(alias=alias)
    instance = lxd.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name=remote_image.image_name,
        image_remote=remote_image.remote_name,
    )

    try:
        assert isinstance(instance, lxd.LXDInstance)
        assert instance.exists() is True
        assert instance.is_running() is True

        proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

        assert proc.stdout == b"hi\n"
    finally:
        instance.delete()


@pytest.mark.parametrize(
    "alias",
    [BuilddBaseAlias.BIONIC, BuilddBaseAlias.FOCAL, BuilddBaseAlias.JAMMY],
)
def test_configure_and_launch_buildd_remotes(instance_name, alias):
    """Verify function `configure_buildd_image_remote()` can launch core 18|20|22."""
    image_remote = lxd.configure_buildd_image_remote()
    assert image_remote == "craft-com.ubuntu.cloud-buildd"

    base_configuration = BuilddBase(alias=alias)
    instance = lxd.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name=alias.value,
        image_remote=image_remote,
    )

    try:
        assert isinstance(instance, lxd.LXDInstance)
        assert instance.exists() is True
        assert instance.is_running() is True

        proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

        assert proc.stdout == b"hi\n"
    finally:
        instance.delete()
