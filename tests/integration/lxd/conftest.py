# Copyright (C) 2021 Canonical Ltd
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
import pathlib
import random
import string
import subprocess
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

import pytest

from craft_providers.lxd import LXC, LXDInstance, purge_project


def run(cmd, **kwargs):
    return subprocess.run(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=True, **kwargs
    )


@pytest.fixture()
def lxd():
    lxc_path = pathlib.Path("/snap/bin/lxc")
    if lxc_path.exists():
        already_installed = True
    else:
        already_installed = False
        run(["sudo", "snap", "install", "lxd"])

    yield lxc_path

    if not already_installed:
        run(["sudo", "snap", "remove", "lxd"])


@pytest.fixture()
def lxc(lxd):  # pylint: disable=unused-argument
    yield LXC()


@pytest.fixture()
def project(lxc):
    project_name = "ptest-" + "".join(random.choices(string.ascii_uppercase, k=8))
    lxc.project_create(project=project_name)

    default_cfg = lxc.profile_show(profile="default", project="default")
    lxc.profile_edit(profile="default", project=project_name, config=default_cfg)

    projects = lxc.project_list()
    assert project_name in projects

    instances = lxc.list(project=project_name)
    assert instances == []

    yield project_name

    purge_project(lxc=lxc, project=project_name)


def _instance_name():
    return "itest-" + "".join(random.choices(string.ascii_uppercase, k=8))


@pytest.fixture()
def instance_name():
    yield _instance_name()


@contextmanager
def _instance(
    *,
    instance_name: str,
    lxc: LXC,
    project: str,
    config_keys: Optional[Dict[str, Any]] = None,
    image_remote: str = "ubuntu",
    image: str = "16.04",
    remote: str = "local",
    ephemeral: bool = False,
):
    if config_keys is None:
        config_keys = dict()

    lxc.launch(
        config_keys=config_keys,
        instance_name=instance_name,
        image_remote=image_remote,
        image=image,
        project=project,
        ephemeral=ephemeral,
    )

    # Make sure container is ready
    for _ in range(0, 60):
        proc = lxc.exec(
            instance_name=instance_name,
            command=["systemctl", "is-system-running"],
            project=project,
            stdout=subprocess.PIPE,
        )

        running_state = proc.stdout.strip()
        if running_state in ["running", "degraded"]:
            break
        time.sleep(0.5)

    instance = LXDInstance(name=instance_name, project=project, remote=remote)

    yield instance

    if instance.exists():
        instance.delete(force=True)


@pytest.fixture()
def instance(instance_name, lxc, project):
    with _instance(
        instance_name=instance_name,
        lxc=lxc,
        project=project,
    ) as x_instance:
        yield x_instance


@pytest.fixture()
def instance_launcher(lxc, project, instance_name):
    def launch(
        *,
        lxc=lxc,
        config_keys=None,
        instance_name=instance_name,
        image_remote="ubuntu",
        image="16.04",
        project=project,
        ephemeral=False,
    ) -> str:
        lxc.launch(
            config_keys=config_keys,
            instance_name=instance_name,
            image_remote=image_remote,
            image=image,
            project=project,
            ephemeral=ephemeral,
        )

        # Make sure container is ready
        for _ in range(0, 60):
            proc = lxc.exec(
                instance_name=instance_name,
                command=["systemctl", "is-system-running"],
                project=project,
                stdout=subprocess.PIPE,
            )

            running_state = proc.stdout.decode().strip()
            if running_state in ["running", "degraded"]:
                break
            time.sleep(0.5)

        return instance_name

    yield launch


@pytest.fixture()
def ephemeral_instance(instance_name, lxc, project):
    lxc.launch(
        config_keys=dict(),
        instance_name=instance_name,
        image_remote="ubuntu",
        image="16.04",
        project=project,
        ephemeral=True,
    )

    return instance
