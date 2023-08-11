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

"""Tests for snap installer."""

import logging
import re
from textwrap import dedent

from craft_providers.actions import snap_installer


def test_inject_from_host(core22_lxd_instance, installed_snap, caplog):
    """Verify a snap can be injected from the host."""
    core22_lxd_instance.execute_run(
        ["test", "!", "-d", "/snap/hello-world"], check=True
    )

    with installed_snap("hello-world"):
        snap_installer.inject_from_host(
            executor=core22_lxd_instance, snap_name="hello-world", classic=False
        )

    core22_lxd_instance.execute_run(["test", "-d", "/snap/hello-world"], check=True)

    config = core22_lxd_instance.execute_run(
        ["cat", "/etc/craft-instance.conf"], check=True, capture_output=True
    ).stdout.decode()

    # verify instance config was properly updated
    assert (
        re.fullmatch(
            re.compile(
                dedent(
                    """\
                    compatibility_tag: buildd-base-v\\d+
                    setup: true
                    snaps:
                      hello-world:
                        revision: '\\d+'
                        source: host
                    """
                )
            ),
            config,
        )
        is not None
    )
    assert caplog.records == []


def test_inject_from_host_dangerous(
    core22_lxd_instance, dangerously_installed_snap, caplog
):
    """Verify a dangerously installed snap can be injected from the host."""
    core22_lxd_instance.execute_run(
        ["test", "!", "-d", "/snap/hello-world"], check=True
    )

    with dangerously_installed_snap("hello-world"):
        snap_installer.inject_from_host(
            executor=core22_lxd_instance, snap_name="hello-world", classic=False
        )

    core22_lxd_instance.execute_run(["test", "-d", "/snap/hello-world"], check=True)

    config = core22_lxd_instance.execute_run(
        ["cat", "/etc/craft-instance.conf"], check=True, capture_output=True
    ).stdout.decode()

    # verify instance config was properly updated
    assert (
        re.fullmatch(
            re.compile(
                dedent(
                    """\
                    compatibility_tag: buildd-base-v\\d+
                    setup: true
                    snaps:
                      hello-world:
                        revision: x\\d+
                        source: host
                    """
                )
            ),
            config,
        )
        is not None
    )
    assert caplog.records == []


def test_inject_from_host_using_pack_fallback(
    core22_lxd_instance, empty_test_snap, caplog
):
    """Verify a snap is packed if the local download fails."""
    caplog.set_level(logging.DEBUG)

    snap_installer.inject_from_host(
        executor=core22_lxd_instance,
        snap_name=empty_test_snap,
        classic=False,
    )

    core22_lxd_instance.execute_run(
        ["test", "-d", f"/snap/{empty_test_snap}"], check=True
    )

    log_messages = [r.message for r in caplog.records]
    expected = (
        "Failed to fetch snap from snapd, falling back to `snap pack` to recreate"
    )
    assert expected in log_messages


def test_install_from_store_strict(core22_lxd_instance, installed_snap, caplog):
    """Verify a strictly confined snap from the store can be installed."""
    core22_lxd_instance.execute_run(
        ["test", "!", "-d", "/snap/hello-world"], check=True
    )

    snap_installer.install_from_store(
        executor=core22_lxd_instance,
        snap_name="hello-world",
        channel="latest/stable",
        classic=False,
    )

    core22_lxd_instance.execute_run(["test", "-f", "/snap/bin/hello-world"], check=True)

    config = core22_lxd_instance.execute_run(
        ["cat", "/etc/craft-instance.conf"], check=True, capture_output=True
    ).stdout.decode()

    # verify instance config was properly updated
    assert (
        re.fullmatch(
            re.compile(
                dedent(
                    """\
                    compatibility_tag: buildd-base-v\\d+
                    setup: true
                    snaps:
                      hello-world:
                        revision: '\\d+'
                        source: store
                    """
                )
            ),
            config,
        )
        is not None
    )
    assert caplog.records == []


def test_install_from_store_classic(core22_lxd_instance, installed_snap, caplog):
    """Verify a classicly confined snap from the store can be installed."""
    core22_lxd_instance.execute_run(["test", "!", "-d", "/snap/charmcraft"], check=True)

    snap_installer.install_from_store(
        executor=core22_lxd_instance,
        snap_name="charmcraft",
        channel="latest/stable",
        classic=True,
    )

    core22_lxd_instance.execute_run(["test", "-f", "/snap/bin/charmcraft"], check=True)

    config = core22_lxd_instance.execute_run(
        ["cat", "/etc/craft-instance.conf"], check=True, capture_output=True
    ).stdout.decode()

    # verify instance config was properly updated
    assert (
        re.fullmatch(
            re.compile(
                dedent(
                    """\
                    compatibility_tag: buildd-base-v\\d+
                    setup: true
                    snaps:
                      charmcraft:
                        revision: '\\d+'
                        source: store
                    """
                )
            ),
            config,
        )
        is not None
    )
    assert caplog.records == []


def test_install_from_store_channel(core22_lxd_instance, installed_snap, caplog):
    """Verify a channel can be specified when installing from the store"""
    core22_lxd_instance.execute_run(["test", "!", "-d", "/snap/go"], check=True)

    snap_installer.install_from_store(
        executor=core22_lxd_instance,
        snap_name="go",
        channel="1.15/stable",
        classic=True,
    )

    proc = core22_lxd_instance.execute_run(
        ["/snap/bin/go", "version"], capture_output=True, check=True, text=True
    )

    assert "go1.15" in proc.stdout

    config = core22_lxd_instance.execute_run(
        ["cat", "/etc/craft-instance.conf"], check=True, capture_output=True
    ).stdout.decode()

    # verify instance config was properly updated
    assert (
        re.fullmatch(
            re.compile(
                dedent(
                    """\
                    compatibility_tag: buildd-base-v\\d+
                    setup: true
                    snaps:
                      go:
                        revision: '\\d+'
                        source: store
                    """
                )
            ),
            config,
        )
        is not None
    )
    assert caplog.records == []


def test_install_from_store_snap_name_suffix(
    core22_lxd_instance, installed_snap, caplog
):
    """Verify a snap can be installed from the store when the snap name has a suffix."""
    core22_lxd_instance.execute_run(
        ["test", "!", "-d", "/snap/hello-world"], check=True
    )

    snap_installer.install_from_store(
        executor=core22_lxd_instance,
        snap_name="hello-world_suffix",
        channel="latest/stable",
        classic=False,
    )

    core22_lxd_instance.execute_run(["test", "-f", "/snap/bin/hello-world"], check=True)

    config = core22_lxd_instance.execute_run(
        ["cat", "/etc/craft-instance.conf"], check=True, capture_output=True
    ).stdout.decode()

    # track the `hello-world` snap in the config file, not `hello-world_suffix`
    assert (
        re.fullmatch(
            re.compile(
                dedent(
                    """\
                    compatibility_tag: buildd-base-v\\d+
                    setup: true
                    snaps:
                      hello-world:
                        revision: '\\d+'
                        source: store
                    """
                )
            ),
            config,
        )
        is not None
    )
    assert caplog.records == []
