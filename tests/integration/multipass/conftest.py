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

"""Fixtures for Multipass integration tests."""
import os
import pathlib
import random
import string
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager

import pytest

from craft_providers import multipass


@pytest.fixture()
def home_tmp_path():
    """Multipass doesn't have access to /tmp."""
    with tempfile.TemporaryDirectory(
        suffix=".tmp-pytest", dir=pathlib.Path.home()
    ) as temp_dir:
        yield pathlib.Path(temp_dir)


def generate_instance_name():
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


@pytest.fixture()
def instance_name():
    yield generate_instance_name()


@contextmanager
def tmp_instance(
    *,
    instance_name: str,
    image_name: str = "20.04",
    cpus: str = "2",
    disk: str = "64G",
    mem: str = "1G",
):
    subprocess.run(
        [
            "multipass",
            "launch",
            image_name,
            "--name",
            instance_name,
            "--cpus",
            cpus,
            "--mem",
            mem,
            "--disk",
            disk,
        ],
        capture_output=True,
        check=True,
    )

    # Make sure container is ready
    for _ in range(0, 2400):
        proc = subprocess.run(
            [
                "multipass",
                "exec",
                instance_name,
                "--",
                "systemctl",
                "is-system-running",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        running_state = proc.stdout.strip()
        if running_state in ["running", "degraded"]:
            break
        time.sleep(0.1)

    yield instance_name

    # Cleanup if not purged by the test.
    subprocess.run(
        ["multipass", "delete", "--purge", instance_name],
        capture_output=True,
        check=False,
    )


@pytest.fixture(autouse=True, scope="module")
def installed_multipass():
    """Ensure multipass is installed, or skip the test if we cannot.

    If the environment has CRAFT_PROVIDERS_TESTS_ENABLE_MULTIPASS_INSTALL=1,
    force the installation of Multipass if uninstalled.
    """
    if multipass.is_installed():
        return

    if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_MULTIPASS_INSTALL") == "1":
        multipass.install()
    else:
        pytest.skip("multipass not installed, skipped")


@pytest.fixture
def uninstalled_multipass():
    """Uninstall Multipass prior to test, if environment allows it.

    Environment may enable this fixture with:
    CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL=1
    """
    if not multipass.is_installed():
        pytest.skip("multipass not installed, skipped")

    if not os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_MULTIPASS_UNINSTALL") == "1":
        pytest.skip("not configured to uninstall multipass, skipped")

    if sys.platform == "linux":
        subprocess.run(["sudo", "snap", "remove", "multipass", "--purge"], check=True)
    elif sys.platform == "darwin":
        subprocess.run(["brew", "uninstall", "multipass"], check=True)
    else:
        pytest.skip("platform not supported to uninstall multipass, skipped")

    yield

    # Ensure it is installed after test.
    if not multipass.is_installed():
        multipass.install()
