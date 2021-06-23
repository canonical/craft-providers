#
# Copyright 2021 Canonical Ltd.
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

"""Tests for snap installer."""


from craft_providers.actions import snap_installer


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
