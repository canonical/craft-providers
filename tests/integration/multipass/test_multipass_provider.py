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
import subprocess
import textwrap

import pytest

from craft_providers import images
from craft_providers.images import BuilddImage, BuilddImageAlias
from craft_providers.multipass import MultipassInstance, MultipassProvider


@pytest.mark.parametrize(
    "alias,image_name",
    [
        (BuilddImageAlias.XENIAL, "snapcraft:core"),
        (BuilddImageAlias.BIONIC, "snapcraft:core18"),
        (BuilddImageAlias.FOCAL, "snapcraft:core20"),
    ],
)
def test_multipass_provider(instance_name, alias, image_name):
    image_configuration = BuilddImage(alias=alias)
    provider = MultipassProvider()

    instance = provider.create_instance(
        name=instance_name,
        image_configuration=image_configuration,
        image_name=image_name,
        auto_clean=True,
    )

    assert isinstance(instance, MultipassInstance)
    assert instance.exists() is True
    assert instance.is_running() is True

    proc = instance.execute_run(["echo", "hi"], check=True, stdout=subprocess.PIPE)

    assert proc.stdout == b"hi\n"

    instance.execute_run(["sudo", "apt", "update"], check=True)


@pytest.mark.parametrize(
    "auto_clean",
    [False, True],
)
def test_incompatible_instance_tag(instance_launcher, instance_name, auto_clean):
    alias = BuilddImageAlias.XENIAL
    image = BuilddImage(alias=alias)
    image_name = "snapcraft:core"

    with instance_launcher(
        image_name=image_name,
        name=instance_name,
    ) as instance:
        # Insert incompatible config.
        instance.create_file(
            destination=pathlib.Path("/etc/craft-image.conf"),
            content="compatibility_tag: craft-buildd-image-vX".encode(),
            file_mode="0644",
            user="root",
            group="root",
        )

        provider = MultipassProvider()

        if auto_clean:
            provider.create_instance(
                name=instance_name,
                image_configuration=image,
                image_name=image_name,
                auto_clean=auto_clean,
            )
        else:
            with pytest.raises(images.CompatibilityError) as exc_info:
                provider.create_instance(
                    name=instance_name,
                    image_configuration=image,
                    image_name=image_name,
                    auto_clean=auto_clean,
                )

            assert (
                exc_info.value.reason
                == "Expected image compatibility tag 'craft-buildd-image-v0', found 'craft-buildd-image-vX'"
            )


@pytest.mark.parametrize(
    "auto_clean",
    [False, True],
)
def test_incompatible_instance_os(instance_launcher, instance_name, auto_clean):
    alias = BuilddImageAlias.XENIAL
    image = BuilddImage(alias=alias)
    image_name = "snapcraft:core"

    with instance_launcher(
        image_name=image_name,
        name=instance_name,
    ) as instance:
        # Insert incompatible os-release.
        instance.create_file(
            destination=pathlib.Path("/etc/os-release"),
            content=textwrap.dedent(
                """
                NAME="Ubuntu"
                VERSION="20.10 (Groovy Gorilla)"
                ID=ubuntu
                ID_LIKE=debian
                PRETTY_NAME="Ubuntu 20.10"
                VERSION_ID="20.10"
                HOME_URL="https://www.ubuntu.com/"
                SUPPORT_URL="https://help.ubuntu.com/"
                BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
                PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
                VERSION_CODENAME=groovy
                UBUNTU_CODENAME=groovy
                """
            ).encode(),
            file_mode="0644",
            user="root",
            group="root",
        )

        provider = MultipassProvider()

        if auto_clean:
            provider.create_instance(
                name=instance_name,
                image_configuration=image,
                image_name=image_name,
                auto_clean=auto_clean,
            )
        else:
            with pytest.raises(images.CompatibilityError) as exc_info:
                provider.create_instance(
                    name=instance_name,
                    image_configuration=image,
                    image_name=image_name,
                    auto_clean=auto_clean,
                )

            assert (
                exc_info.value.reason
                == f"Expected OS version '{alias.value!s}', found '20.10'"
            )
