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

import pathlib
import time

import craft_providers
import pytest
from craft_providers import bases
from craft_providers.bases.almalinux import AlmaLinuxBaseAlias
from craft_providers.bases.centos import CentOSBaseAlias
from craft_providers.bases.ubuntu import BuilddBaseAlias
from craft_providers.multipass.multipass_provider import MultipassProvider


@pytest.mark.slow
@pytest.mark.parametrize(
    "base_alias",
    [
        bases.BuilddBaseAlias.NOBLE,
        # https://github.com/canonical/craft-providers/issues/765
        # We should enable all of these for weekly tests instead of just Noble.
        # *bases.ubuntu.BuilddBaseAlias,
        # *bases.almalinux.AlmaLinuxBaseAlias,
    ],
)
def test_relaunch(
    session_provider: craft_providers.Provider,
    base_alias: BuilddBaseAlias | CentOSBaseAlias | AlmaLinuxBaseAlias,
    tmp_path: pathlib.Path,
):
    if (
        isinstance(session_provider, MultipassProvider)
        and base_alias not in bases.ubuntu.BuilddBaseAlias
    ):
        pytest.skip("Non-Ubuntu bases not supported with Multipass.")
    if base_alias == bases.ubuntu.BuilddBaseAlias.XENIAL:
        pytest.skip(
            "Xenial not supported: https://github.com/canonical/craft-providers/issues/582"
        )
    if base_alias == bases.ubuntu.BuilddBaseAlias.ORACULAR:
        pytest.skip(
            "Oracular is unsupported: https://github.com/canonical/craft-providers/issues/598"
        )

    base_cls = bases.get_base_from_alias(base_alias)
    base = base_cls(alias=base_alias)  # pyright: ignore[reportArgumentType]
    project_name = f"relaunch-{base_alias.name}"

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
        instance = locals().get("instance")
        if instance is not None:
            instance.delete()
