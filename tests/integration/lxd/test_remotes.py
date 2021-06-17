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

import pytest

from craft_providers import bases, lxd


@pytest.mark.parametrize(
    "alias,image_name",
    [
        (bases.BuilddBaseAlias.BIONIC, "18.04"),
        (bases.BuilddBaseAlias.FOCAL, "20.04"),
    ],
)
def test_configure_and_launch_buildd_remotes(instance_name, alias, image_name):
    image_remote = lxd.configure_buildd_image_remote()
    assert image_remote == "com.cloud-images.buildd.releases"

    base_configuration = bases.BuilddBase(alias=alias)
    instance = lxd.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name=image_name,
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
