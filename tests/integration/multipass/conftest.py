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
import pathlib
import random
import string
import subprocess
import tempfile
import time
from contextlib import contextmanager

import pytest


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
