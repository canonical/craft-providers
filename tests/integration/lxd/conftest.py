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

"""Fixtures for LXD integration tests."""
import os
import random
import string
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

import pytest

from craft_providers import lxd
from craft_providers.lxd import LXC
from craft_providers.lxd import project as lxc_project


def generate_instance_name():
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


@pytest.fixture()
def instance_name():
    yield generate_instance_name()


@contextmanager
def tmp_instance(
    *,
    instance_name: str,
    config_keys: Optional[Dict[str, Any]] = None,
    ephemeral: bool = True,
    image: str = "16.04",
    image_remote: str = "ubuntu",
    project: str,
    remote: str = "local",
    lxc: LXC = LXC(),
):
    if config_keys is None:
        config_keys = dict()

    lxc.launch(
        instance_name=instance_name,
        config_keys=config_keys,
        ephemeral=ephemeral,
        image=image,
        image_remote=image_remote,
        project=project,
        remote=remote,
    )

    # Make sure container is ready
    for _ in range(0, 60):
        proc = lxc.exec(
            command=["systemctl", "is-system-running"],
            instance_name=instance_name,
            project=project,
            remote=remote,
            capture_output=True,
            check=False,
            text=True,
        )

        running_state = proc.stdout.strip()
        if running_state in ["running", "degraded"]:
            break

        time.sleep(0.1)

    yield instance_name

    if instance_name in lxc.list_names(project=project, remote=remote):
        lxc.delete(
            instance_name=instance_name, project=project, remote=remote, force=True
        )

    assert instance_name not in lxc.list_names(project=project, remote=remote)


@pytest.fixture(autouse=True, scope="module")
def installed_lxd():
    """Ensure lxd is installed, or skip the test if we cannot.

    If the environment has CRAFT_PROVIDERS_TESTS_ENABLE_LXD_INSTALL=1,
    force the installation of LXD if uninstalled.
    """
    if sys.platform != "linux":
        pytest.skip(f"lxd not supported on {sys.platform}")

    if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_LXD_INSTALL") == "1":
        lxd.install()
    elif not lxd.is_installed():
        pytest.skip("lxd not installed, skipped")


@pytest.fixture
def uninstalled_lxd():
    """Uninstall Lxd prior to test, if environment allows it.

    Environment may enable this fixture with:
    CRAFT_PROVIDER_TESTS_ENABLE_LXD_UNINSTALL=1
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


@pytest.fixture()
def lxc():
    yield LXC()


@pytest.fixture()
def project(lxc):
    """Create temporary LXD project and assert expected properties."""
    project_name = "ptest-" + "".join(random.choices(string.ascii_uppercase, k=4))
    lxc_project.create_with_default_profile(lxc=lxc, project=project_name)

    projects = lxc.project_list()
    assert project_name in projects

    instances = lxc.list(project=project_name)
    assert instances == []

    expected_cfg = lxc.profile_show(profile="default", project="default")
    expected_cfg["used_by"] = []

    assert lxc.profile_show(profile="default", project=project_name) == expected_cfg

    yield project_name

    lxc_project.purge(lxc=lxc, project=project_name)
