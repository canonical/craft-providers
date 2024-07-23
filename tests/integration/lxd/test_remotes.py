#
# Copyright 2021-2024 Canonical Ltd.
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
from craft_providers.bases import ubuntu

from .conftest import UBUNTU_BASES_PARAM

# The LXD tests can be flaky, erroring out with a BaseCompatibilityError:
# "Clean incompatible instance and retry the requested operation."
# This is due to an upstream LXD bug that appears to still be present in LXD 5.14:
# https://github.com/lxc/lxd/issues/11422
pytestmark = pytest.mark.flaky(reruns=3, reruns_delay=2)


@pytest.mark.parametrize("alias", UBUNTU_BASES_PARAM)
def test_configure_and_launch_remote(instance_name, alias):
    """Verify remotes are configured and images can be launched."""
    base_configuration = ubuntu.BuilddBase(alias=alias)
    remote_image = lxd.get_remote_image(base_configuration)
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
