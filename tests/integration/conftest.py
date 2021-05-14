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

"""Fixtures for integration tests."""
import os
import pathlib
import random
import string
import subprocess
import sys
import tempfile

import pytest

from craft_providers import lxd, multipass


def generate_instance_name():
    """Generate a random instance name."""
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


@pytest.fixture()
def home_tmp_path():
    """Provide a temporary directory located in user's home directory.

    Multipass doesn't have access to /tmp, this fixture provides an equivalent
    to tmp_path for tests that require it.
    """
    with tempfile.TemporaryDirectory(
        suffix=".tmp-pytest", dir=pathlib.Path.home()
    ) as temp_dir:
        yield pathlib.Path(temp_dir)


@pytest.fixture()
def instance_name():
    """Provide a random name for an instance to launch."""
    yield generate_instance_name()


@pytest.fixture(scope="module")
def reusable_instance_name():
    """Provide a random name for an instance to launch with scope=module."""
    yield generate_instance_name()


@pytest.fixture(scope="module")
def installed_lxd():
    """Ensure lxd is installed, or skip the test if we cannot.

    If the environment has CRAFT_PROVIDERS_TESTS_ENABLE_LXD_INSTALL=1,
    force the installation of LXD if uninstalled.
    """
    if sys.platform != "linux":
        pytest.skip(f"lxd not supported on {sys.platform}")

    if lxd.is_installed():
        return

    if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_LXD_INSTALL") == "1":
        lxd.install()
    else:
        pytest.skip("lxd not installed, skipped")


@pytest.fixture
def uninstalled_lxd():
    """Uninstall Lxd prior to test, if environment allows it.

    For consistency with installed_lxd fixture, LXD must be installed prior to
    this, signaling that LXD will run OK.

    Environment may enable this fixture with:
    CRAFT_PROVIDERS_TESTS_ENABLE_LXD_UNINSTALL=1
    """
    if sys.platform != "linux":
        pytest.skip(f"lxd not supported on {sys.platform}")

    if not lxd.is_installed():
        pytest.skip("lxd not installed, skipped")

    if not os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_LXD_UNINSTALL") == "1":
        pytest.skip("not configured to uninstall lxd, skipped")

    if sys.platform == "linux":
        subprocess.run(["sudo", "snap", "remove", "lxd", "--purge"], check=True)

    yield

    # Ensure it is installed after test.
    if not lxd.is_installed():
        lxd.install()


@pytest.fixture(scope="module")
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

    For consistency with installed_multipass fixture, Multipass must be
    installed prior to this, signaling that Multipass will run OK.

    Environment may enable this fixture with:
    CRAFT_PROVIDERS_TESTS_ENABLE_MULTIPASS_UNINSTALL=1
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
