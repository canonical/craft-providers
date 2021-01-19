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

"""Fixtures for MULTIPASS integration tests."""
import pathlib
import random
import string
import subprocess
import tempfile
import time
from contextlib import contextmanager

import pytest

from craft_providers.multipass import Multipass, MultipassInstance, multipass_installer


def run(cmd, check=True, **kwargs):
    return subprocess.run(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=check, **kwargs
    )


@pytest.fixture()
def home_tmp_path():
    """Multipass doesn't have access """
    with tempfile.TemporaryDirectory(
        suffix=".tmp-pytest", dir=pathlib.Path.home()
    ) as temp_dir:
        yield pathlib.Path(temp_dir)


@pytest.fixture(scope="module", autouse=True)
def multipass_path():
    yield multipass_installer.install()


def _multipass(*, multipass_path):
    return Multipass(multipass_path=multipass_path)


@pytest.fixture()
def multipass(multipass_path):  # pylint: disable=unused-argument
    yield _multipass(multipass_path=multipass_path)


@pytest.fixture(scope="module")
def reusable_multipass(multipass_path):  # pylint: disable=unused-argument
    yield _multipass(multipass_path=multipass_path)


def _instance_name():
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


@pytest.fixture()
def instance_name():
    yield _instance_name()


@pytest.fixture(scope="module")
def reusable_instance_name():
    yield _instance_name()


@contextmanager
def _instance(
    *,
    multipass,
    instance_name=instance_name,
    image_name="snapcraft:core20",
    cpus="2",
    disk="128G",
    mem="1G",
):
    multipass.launch(
        instance_name=instance_name,
        image=image_name,
        cpus=cpus,
        disk=disk,
        mem=mem,
    )

    # Make sure container is ready
    for _ in range(0, 2400):
        proc = multipass.exec(
            instance_name=instance_name,
            command=["systemctl", "is-system-running"],
            stdout=subprocess.PIPE,
        )

        running_state = proc.stdout.decode().strip()
        if running_state in ["running", "degraded"]:
            break
        time.sleep(0.1)

    mp_instance = MultipassInstance(name=instance_name, multipass=multipass)

    yield mp_instance

    # Cleanup if not purged by the test.
    if mp_instance.exists():
        mp_instance.delete(purge=True)


@pytest.fixture()
def instance_launcher(multipass, instance_name):
    def __instance(
        *,
        name=instance_name,
        image_name="snapcraft:core20",
        cpus="2",
        disk="128G",
        mem="1G",
    ):
        return _instance(
            multipass=multipass,
            instance_name=name,
            image_name=image_name,
            cpus=cpus,
            disk=disk,
            mem=mem,
        )

    return __instance


@pytest.fixture()
def instance(instance_name, multipass):
    with _instance(
        multipass=multipass,
        instance_name=instance_name,
    ) as mp_instance:

        yield mp_instance


@pytest.fixture(scope="module")
def reusable_instance(reusable_instance_name, reusable_multipass):
    with _instance(
        multipass=reusable_multipass,
        instance_name=reusable_instance_name,
    ) as mp_instance:

        yield mp_instance
