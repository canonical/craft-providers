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

import io
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

from craft_providers.bases import BaseCompatibilityError, BuilddBase, BuilddBaseAlias
from craft_providers.multipass import MultipassInstance, MultipassProvider

from . import conftest

pytestmark = pytest.mark.skipif(
    shutil.which("multipass") is None, reason="multipass not installed"
)


@pytest.fixture()
def instance():
    with conftest.tmp_instance(
        instance_name=conftest.generate_instance_name(),
    ) as tmp_instance:
        yield MultipassInstance(name=tmp_instance)


@pytest.fixture
def uninstalled_multipass():
    """Uninstall Multipass prior to test, if environment allows it.

    Environment may enable this fixture with:
    CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL=1
    """
    provider = MultipassProvider()
    if not provider.is_installed():
        return

    if not os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_MULTIPASS_UNINSTALL") == "1":
        pytest.skip("not configured to uninstall multipass, skipped")

    if sys.platform == "linux":
        subprocess.run(["sudo", "snap", "remove", "multipass", "--purge"], check=True)
    elif sys.platform == "darwin":
        subprocess.run(["brew", "uninstall", "multipass"], check=True)
    else:
        pytest.skip("platform not supported to uninstall multipass, skipped")


@pytest.mark.parametrize(
    "alias,image_name",
    [
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
def test_multipass_provider(instance_name, alias, image_name):
    base_configuration = BuilddBase(alias=alias)
    provider = MultipassProvider()

    instance = provider.create_instance(
        name=instance_name,
        base_configuration=base_configuration,
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
def test_incompatible_instance_tag(instance, auto_clean):
    alias = BuilddBaseAlias.FOCAL
    base_configuration = BuilddBase(alias=alias)
    image_name = "snapcraft:core20"

    # Insert incompatible config.
    instance.create_file(
        destination=pathlib.Path("/etc/craft.conf"),
        content=io.BytesIO("compatibility_tag: craft-buildd-image-vX\n".encode()),
        file_mode="0644",
        user="root",
        group="root",
    )

    provider = MultipassProvider()

    if auto_clean:
        provider.create_instance(
            name=instance.name,
            base_configuration=base_configuration,
            image_name=image_name,
            auto_clean=auto_clean,
        )
    else:
        with pytest.raises(BaseCompatibilityError) as exc_info:
            provider.create_instance(
                name=instance.name,
                base_configuration=base_configuration,
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
def test_incompatible_instance_os(instance, auto_clean):
    alias = BuilddBaseAlias.FOCAL
    base_configuration = BuilddBase(alias=alias)
    image_name = "snapcraft:core20"

    # Insert incompatible os-release.
    instance.create_file(
        destination=pathlib.Path("/etc/os-release"),
        content=io.BytesIO(
            textwrap.dedent(
                """\
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
            ).encode()
        ),
        file_mode="0644",
        user="root",
        group="root",
    )

    provider = MultipassProvider()

    if auto_clean:
        provider.create_instance(
            name=instance.name,
            base_configuration=base_configuration,
            image_name=image_name,
            auto_clean=auto_clean,
        )
    else:
        with pytest.raises(BaseCompatibilityError) as exc_info:
            provider.create_instance(
                name=instance.name,
                base_configuration=base_configuration,
                image_name=image_name,
                auto_clean=auto_clean,
            )

        assert (
            exc_info.value.reason
            == f"Expected OS version {alias.value!r}, found '20.10'"
        )


def test_install(uninstalled_multipass):  # pylint: disable=unused-argument
    provider = MultipassProvider()

    assert provider.is_installed() is False

    multipass_version = provider.install()

    assert provider.is_installed() is True
    assert multipass_version is not None
