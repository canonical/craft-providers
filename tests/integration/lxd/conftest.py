#
# Copyright 2021-2024 Canonical Ltd.
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

"""Fixtures for LXD integration tests."""
import os
import random
import string
import subprocess
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

import pytest
from craft_providers.bases import ubuntu
from craft_providers.lxd import LXC
from craft_providers.lxd import project as lxc_project
from craft_providers.lxd.lxd_instance import LXDInstance
from craft_providers.lxd.lxd_provider import LXDProvider

_xfail_bases = {
    ubuntu.BuilddBaseAlias.XENIAL: "Fails to setup snapd (#582)",
    ubuntu.BuilddBaseAlias.ORACULAR: "24.10 fails setup (#598)",
    ubuntu.BuilddBaseAlias.DEVEL: "24.10 fails setup (#598)",
}
"""List of bases that are expected to fail and a reason why."""

UBUNTU_BASES_PARAM = [
    (
        pytest.param(
            base, marks=pytest.mark.xfail(reason=_xfail_bases[base], strict=True)
        )
        if base in _xfail_bases
        else base
    )
    for base in ubuntu.BuilddBaseAlias
]
"""List of testable Ubuntu bases."""


@pytest.fixture(autouse=True, scope="module")
def installed_lxd_required(installed_lxd):
    """All LXD integration tests required LXD to be installed."""


@pytest.fixture
@pytest.mark.with_sudo
def installed_lxd_without_init(uninstalled_lxd):
    """Ensure lxd is installed, but not initialized.

    Initialize LXD on cleanup to ensure it is functional for other tests.

    Requires CRAFT_PROVIDERS_TESTS_ENABLE_LXD_INSTALL=1.
    """
    if os.environ.get("CRAFT_PROVIDERS_TESTS_ENABLE_LXD_INSTALL") != "1":
        pytest.skip("lxd not installed, skipped")
    subprocess.run(["sudo", "snap", "install", "lxd"], check=True)
    subprocess.run(["sudo", "lxd", "waitready"], check=True)
    yield
    subprocess.run(["sudo", "lxd", "init", "--auto"], check=True)


@contextmanager
def tmp_instance(
    *,
    name: str,
    config_keys: Optional[Dict[str, Any]] = None,
    ephemeral: bool = True,
    image: str = "22.04",
    image_remote: str = "ubuntu",
    project: str,
    remote: str = "local",
    lxc: LXC = LXC(),
):
    if config_keys is None:
        config_keys = {}

    instance = LXDInstance(
        name=name,
        project=project,
        remote=remote,
        lxc=lxc,
    )
    instance_name = instance.instance_name

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


@pytest.fixture
def lxc():
    return LXC()


@pytest.fixture
def project_name():
    """Create temporary LXD project and assert expected properties."""
    return "ptest-" + "".join(random.choices(string.ascii_uppercase, k=4))


@pytest.fixture
def project(lxc, project_name):
    """Create temporary LXD project and assert expected properties."""
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


@pytest.fixture(scope="session")
def session_project(installed_lxd):
    lxc = LXC()
    project_name = "craft-providers-test-session"
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


@pytest.fixture(scope="session")
def session_provider(session_project):
    return LXDProvider(lxd_project=session_project)
