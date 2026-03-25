# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022-2024 Canonical Ltd.
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

import json
import subprocess

import pytest
from craft_providers.multipass import MultipassProvider

from tests.integration.multipass.conftest import tmp_instance


@pytest.mark.slow
@pytest.mark.multipass_instance
def test_prune(installed_multipass):
    """Verify prune deletes instances."""
    provider = MultipassProvider()

    instance_name_1 = "instance-test-prune-1"
    instance_name_2 = "instance-test-prune-2"

    with (
        tmp_instance(instance_name=instance_name_1),
        tmp_instance(instance_name=instance_name_2),
    ):
        # Verify instances exist
        proc = subprocess.run(
            ["multipass", "list", "--format", "json"],
            capture_output=True,
            check=True,
            text=True,
        )

        instances = json.loads(proc.stdout).get("list", [])
        instance_names = [i["name"] for i in instances]
        assert instance_name_1 in instance_names
        assert instance_name_2 in instance_names

        provider.prune()

        # Verify instances are gone
        proc = subprocess.run(
            ["multipass", "list", "--format", "json"],
            capture_output=True,
            check=True,
            text=True,
        )
        instances = json.loads(proc.stdout).get("list", [])
        instance_names = [i["name"] for i in instances]
        assert instance_name_1 not in instance_names
        assert instance_name_2 not in instance_names
