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

"""Fixtures for Multipass integration tests."""
import subprocess
import time
from contextlib import contextmanager

import pytest


@pytest.fixture(autouse=True, scope="session")
def installed_multipass_required(installed_multipass):
    """All Multipass integration tests required multipass to be installed."""


@contextmanager
def tmp_instance(
    *,
    instance_name: str,
    image_name: str = "22.04",
    cpus: str = "2",
    disk: str = "16G",
    mem: str = "4G",
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
            "--memory",
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
