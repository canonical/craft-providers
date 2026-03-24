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

import pytest
from craft_providers.lxd import LXDProvider
from craft_providers.lxd import project as lxc_project


@pytest.mark.slow
@pytest.mark.lxd_instance
def test_prune(lxc, project):
    """Verify prune deletes instances in a project.

    Criteria:
    1. Create multiple instances in the project.
    2. run prune, check all instances were destroyed.
    3. Ensure that you do not delete instances from another project.
    """
    provider = LXDProvider(lxd_project=project)

    instance_name_1 = "test-instance-1"
    instance_name_2 = "test-instance-2"

    other_project = f"{project}-other"
    lxc_project.create_with_default_profile(lxc=lxc, project=other_project)
    other_instance = "other-instance"

    def launch_instance(name, proj):
        lxc.launch(
            instance_name=name,
            project=proj,
            image="22.04",
            image_remote="ubuntu",
        )

    try:
        launch_instance(instance_name_1, project)
        launch_instance(instance_name_2, project)
        launch_instance(other_instance, other_project)

        assert instance_name_1 in lxc.list_names(project=project)
        assert instance_name_2 in lxc.list_names(project=project)
        assert other_instance in lxc.list_names(project=other_project)

        provider.prune()

        remaining_names = lxc.list_names(project=project)
        assert instance_name_1 not in remaining_names
        assert instance_name_2 not in remaining_names

        assert other_instance not in lxc.list_names(project=other_project)

    finally:
        # Cleanup
        for name, proj in [
            (instance_name_1, project),
            (instance_name_2, project),
            (other_instance, other_project),
        ]:
            if name in lxc.list_names(project=proj):
                lxc.delete(instance_name=name, project=proj, force=True)

        lxc_project.purge(lxc=lxc, project=other_project)
