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

"""Tests for snap installer."""
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from craft_providers.actions import snap_installer


@pytest.fixture()
def empty_test_snap(tmp_path):
    """Fixture to provide an empty local-only snap for test purposes.

    Requires:
    CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL=1
    """
    snap_name = "craft-integration-test-snap"

    if shutil.which("snap") is None or sys.platform != "linux":
        pytest.skip("requires linux and snapd")

    if not os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_SNAP_INSTALL") == "1":
        pytest.skip("need permission to install snaps, skipped")

    if pathlib.Path("/snap", snap_name).exists():
        pytest.skip(f"test snap {snap_name} already exists, please remove")

    tmp_path.chmod(0o755)

    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    snap_yaml = meta_dir / "snap.yaml"
    snap_yaml.write_text(
        f"name: {snap_name}\nversion: 1.0\ntype: base\nsummary: test snap\n"
    )

    subprocess.run(["sudo", "snap", "try", str(tmp_path)], check=True)

    yield snap_name

    subprocess.run(["sudo", "snap", "remove", snap_name], check=True)


def test_inject_from_host(core20_lxd_instance, installed_snap, caplog):
    core20_lxd_instance.execute_run(
        ["test", "!", "-d", "/snap/hello-world"], check=True
    )

    with installed_snap("hello-world"):
        snap_installer.inject_from_host(
            executor=core20_lxd_instance, snap_name="hello-world", classic=False
        )

    core20_lxd_instance.execute_run(["test", "-d", "/snap/hello-world"], check=True)

    assert caplog.records == []


def test_inject_from_host_using_pack_fallback(
    core20_lxd_instance, empty_test_snap, caplog
):
    snap_installer.inject_from_host(
        executor=core20_lxd_instance,
        snap_name=empty_test_snap,
        classic=False,
    )

    core20_lxd_instance.execute_run(
        ["test", "-d", f"/snap/{empty_test_snap}"], check=True
    )

    log_messages = [r.message for r in caplog.records]
    assert log_messages == [
        "Failed to fetch snap from snapd, falling back to `snap pack` to recreate."
    ]


def test_install_from_store_strict(core20_lxd_instance, installed_snap, caplog):
    core20_lxd_instance.execute_run(
        ["test", "!", "-d", "/snap/hello-world"], check=True
    )

    snap_installer.install_from_store(
        executor=core20_lxd_instance,
        snap_name="hello-world",
        channel="latest/stable",
        classic=False,
    )

    core20_lxd_instance.execute_run(["test", "-f", "/snap/bin/hello-world"], check=True)

    assert caplog.records == []


def test_install_from_store_classic(core20_lxd_instance, installed_snap, caplog):
    core20_lxd_instance.execute_run(["test", "!", "-d", "/snap/charmcraft"], check=True)

    snap_installer.install_from_store(
        executor=core20_lxd_instance,
        snap_name="charmcraft",
        channel="latest/stable",
        classic=True,
    )

    core20_lxd_instance.execute_run(["test", "-f", "/snap/bin/charmcraft"], check=True)

    assert caplog.records == []


def test_install_from_store_channel(core20_lxd_instance, installed_snap, caplog):
    core20_lxd_instance.execute_run(["test", "!", "-d", "/snap/go"], check=True)

    snap_installer.install_from_store(
        executor=core20_lxd_instance,
        snap_name="go",
        channel="1.15/stable",
        classic=True,
    )

    proc = core20_lxd_instance.execute_run(
        ["/snap/bin/go", "version"], capture_output=True, check=True, text=True
    )

    assert "go1.15" in proc.stdout
    assert caplog.records == []
