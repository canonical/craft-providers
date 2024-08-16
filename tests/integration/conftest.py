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

"""Fixtures for integration tests."""

import contextlib
import os
import pathlib
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
from typing import Optional

import pytest
from craft_providers import lxd, multipass
from craft_providers.actions.snap_installer import get_host_snap_info
from craft_providers.bases import ubuntu


def pytest_runtest_setup(item: pytest.Item):
    """Configuration for tests."""
    with_sudo = item.get_closest_marker("with_sudo")
    if (
        with_sudo
        and not os.getenv("CI")
        and not os.getenv("CRAFT_PROVIDERS_TESTS_ENABLE_SUDO")
    ):
        pytest.skip("Not running in CI and CRAFT_PROVIDERS_TESTS_ENABLE_SUDO not set.")


def generate_instance_name():
    """Generate a random instance name."""
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


def snap_exists(snap_name: str) -> bool:
    """Returns true if a snap exists."""
    return os.path.exists(f"/snap/{snap_name}/current")


def is_installed_dangerously(snap_name: str) -> bool:
    """Returns true if a snap is installed dangerously."""
    return get_host_snap_info(snap_name)["revision"].startswith("x")


@pytest.fixture
def home_tmp_path():
    """Provide a temporary directory located in user's home directory.

    Multipass doesn't have access to /tmp, this fixture provides an equivalent
    to tmp_path for tests that require it.
    """
    with tempfile.TemporaryDirectory(
        suffix=".tmp-pytest", dir=pathlib.Path.home()
    ) as temp_dir:
        yield pathlib.Path(temp_dir)


@pytest.fixture
def instance_name():
    """Provide a random name for an instance to launch."""
    return generate_instance_name()


@pytest.fixture(scope="module")
def reusable_instance_name():
    """Provide a random name for an instance to launch with scope=module."""
    return generate_instance_name()


@pytest.fixture(scope="session")
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

    if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_LXD_UNINSTALL") != "1":
        pytest.skip("not configured to uninstall lxd, skipped")

    if sys.platform == "linux":
        subprocess.run(["sudo", "snap", "remove", "lxd", "--purge"], check=True)

    yield

    # Ensure it is installed after test.
    if not lxd.is_installed():
        lxd.install()


@pytest.fixture(scope="session")
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

    if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_MULTIPASS_UNINSTALL") != "1":
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


@pytest.fixture
def core22_lxd_instance(installed_lxd, instance_name):
    """Fully configured buildd-based core22 LXD instance."""
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)

    instance = lxd.launch(
        name=instance_name,
        base_configuration=base_configuration,
        image_name="22.04",
        image_remote="ubuntu",
        ephemeral=True,
    )

    yield instance

    if instance.exists():
        instance.delete()


@pytest.fixture(scope="session")
def installed_snap():
    """Fixture to provide contextmanager to install a specified snap.

    If a snap is not installed, it would be installed automatically with:
    CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL=1
    """

    if shutil.which("snap") is None or sys.platform != "linux":
        pytest.skip("requires linux and snapd")

    @contextlib.contextmanager
    def _installed_snap(snap_name, *, try_path: Optional[pathlib.Path] = None):
        """Ensure snap is installed or skip test."""
        # do nothing if already installed and not dangerous
        if snap_exists(snap_name) and not is_installed_dangerously(snap_name):
            yield
        else:
            # Install it, if enabled to do so by environment.
            if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL") != "1":
                pytest.skip(f"{snap_name!r} snap not installed, skipped")

            if try_path:
                subprocess.run(["sudo", "snap", "try", str(try_path)], check=True)
            # if snap is already installed dangerously, use 'snap refresh'
            elif snap_exists(snap_name) and is_installed_dangerously(snap_name):
                subprocess.run(
                    ["sudo", "snap", "refresh", "--amend", snap_name], check=True
                )
            # else use 'snap install'
            else:
                subprocess.run(["sudo", "snap", "install", snap_name], check=True)
            yield
            subprocess.run(["sudo", "snap", "remove", snap_name], check=True)

    return _installed_snap


@pytest.fixture
def dangerously_installed_snap(tmpdir):
    """Fixture to provide contextmanager for a dangerously installed snap.

    If the snap is not installed, it would be installed automatically with:
    CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL=1
    """

    @contextlib.contextmanager
    def _dangerously_installed_snap(snap_name):
        """Ensure snap is installed or skip test."""
        if shutil.which("snap") is None or sys.platform != "linux":
            pytest.skip("requires linux and snapd")

        # do nothing if the snap is already installed dangerously
        if snap_exists(snap_name) and is_installed_dangerously(snap_name):
            yield
        else:
            if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL") != "1":
                pytest.skip(f"{snap_name!r} snap not installed, skipped")

            # download the snap
            output = subprocess.run(
                ["snap", "download", "--target-directory", tmpdir, snap_name],
                check=True,
                capture_output=True,
            )

            # collect the file name
            match = re.search(f"{snap_name}_\\d+.snap", str(output))
            if not match:
                raise Exception(
                    "could not parse snap file name from output of "
                    f"'snap download {snap_name}' (output = {output!r})"
                )
            snap_file_path = pathlib.Path(tmpdir / match.group())

            # the `--dangerous` flag will force the snap to be installed dangerously,
            # even if the assertions exist in snapd
            subprocess.run(
                ["sudo", "snap", "install", snap_file_path, "--dangerous"], check=True
            )
            yield
            subprocess.run(["sudo", "snap", "remove", snap_name], check=True)

    return _dangerously_installed_snap


@pytest.fixture(scope="session")
def empty_test_snap(installed_snap):
    """Fixture to provide an empty local-only snap for test purposes.

    Requires:
    CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL=1
    """
    snap_name = "craft-integration-test-snap"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        tmp_path.chmod(0o755)

        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        snap_yaml = meta_dir / "snap.yaml"
        snap_yaml.write_text(
            f"name: {snap_name}\nversion: 1.0\ntype: base\nsummary: test snap\n"
        )

        with installed_snap(snap_name, try_path=tmp_path):
            yield snap_name
