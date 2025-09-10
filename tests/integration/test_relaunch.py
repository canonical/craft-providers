# Copyright 2025 Canonical Ltd.
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
"""Integration tests to test the shutdown/relaunch workflow."""

import io
import pathlib
import time
from typing import TYPE_CHECKING, cast

import craft_providers
import pytest
from craft_providers.bases.almalinux import AlmaLinuxBaseAlias
from craft_providers.multipass.multipass_provider import MultipassProvider

if TYPE_CHECKING:
    from craft_providers.executor import Executor


@pytest.mark.slow
@pytest.mark.parametrize(
    ("distribution", "series"),
    [
        ("almalinux", "9"),
        ("ubuntu", "24.04"),
        # https://github.com/canonical/craft-providers/issues/765
        # We should enable all of these for weekly tests.
        # Uncomment: *(("ubuntu", alias.value) for alias in BuilddBaseAlias)
    ],
)
def test_relaunch(
    session_provider: craft_providers.Provider,
    distribution: str,
    series: str,
    tmp_path: pathlib.Path,
):
    if isinstance(session_provider, MultipassProvider) and distribution != "ubuntu":
        pytest.skip("Non-Ubuntu bases not supported with Multipass.")
    match (distribution, series):
        case ("ubuntu", "16.04"):
            pytest.skip(
                "Xenial not supported: https://github.com/canonical/craft-providers/issues/582"
            )
        case ("ubuntu", "24.10"):
            pytest.skip(
                "Oracular is unsupported: https://github.com/canonical/craft-providers/issues/598"
            )

    base = craft_providers.get_base(distribution=distribution, series=series)

    project_name = f"relaunch-{base.alias.name}"

    try:
        # Set up both a file that should exist for the whole run and one that should
        # disappear after a proper shutdown.
        with session_provider.launched_environment(
            project_name=project_name,
            project_path=tmp_path,
            base_configuration=base,
            instance_name="relaunch-test",
            allow_unstable=True,
            shutdown_delay_mins=1,
        ) as instance:
            instance.execute_run(["touch", "/tmp/session-file"], check=True)
            instance.execute_run(["touch", "/root/permanent-file"], check=True)

            # Alma Linux only clears tmp files after 10 days by default.
            # This configures systemd-tmpfiles to clear them on every boot.
            if isinstance(base.alias, AlmaLinuxBaseAlias):
                content = io.BytesIO(b"r! /tmp/* 1777 root root 0")
                instance.push_file_io(
                    destination=pathlib.PurePosixPath(
                        "/etc/tmpfiles.d/craft-tempfiles.conf"
                    ),
                    content=content,
                    file_mode="644",
                )

        assert instance.is_running()

        # Check that both files still exist after a delayed shutdown
        with session_provider.launched_environment(
            project_name=project_name,
            project_path=tmp_path,
            base_configuration=base,
            instance_name="relaunch-test",
            allow_unstable=True,
            shutdown_delay_mins=0,
        ) as instance:
            instance.execute_run(["ls", "/tmp/session-file"], check=True)
            instance.execute_run(["ls", "/root/permanent-file"], check=True)
            # Check that the shutdown was properly cancelled.
            result = instance.execute_run(["shutdown", "--show"], check=False)
            assert result.returncode == 1

        # Instance will take a little while to shut down asynchronously. Wait until
        # it's no longer running before moving on.
        for _ in range(100):
            if instance.is_running():
                time.sleep(0.1)
        assert not instance.is_running()

        # Check that the file in /tmp got deleted after a real shutdown, but that the
        # permanent file is still there.
        with session_provider.launched_environment(
            project_name="craft-providers-integration-relaunch",
            project_path=tmp_path,
            base_configuration=base,
            instance_name="relaunch-test",
            allow_unstable=True,
            shutdown_delay_mins=None,
        ) as instance:
            result = instance.execute_run(["ls", "/tmp/session-file"], check=False)
            assert result.returncode == 2
            instance.execute_run(["ls", "/root/permanent-file"], check=True)

    finally:
        instance = cast("Executor", locals().get("instance"))
        if instance is not None:
            instance.delete()
