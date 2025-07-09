# Copyright 2025 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import pytest
from craft_providers import errors, lxd
from craft_providers.bases import ubuntu


@pytest.mark.slow
def test_ubuntu_eol_sources(installed_lxd, instance_name, session_lxd_project, mocker):
    """Update EOL sources when setting up an Ubuntu instance."""
    # There are no working EOL buildd bases, so mock the base and use the error to validate the sources were updated.
    mocker.patch.object(ubuntu.BuilddBase, "_get_codename", return_value="mantic")
    base_configuration = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.NOBLE)
    instance = lxd.LXDInstance(name="test-instance", project=session_lxd_project)

    try:
        with pytest.raises(errors.BaseConfigurationError) as raised:
            lxd.launch(
                name="test-instance",
                project=session_lxd_project,
                base_configuration=base_configuration,
                image_name="24.04",
                image_remote="ubuntu",
                ephemeral=True,
            )

        assert (
            "The repository 'http://old-releases.ubuntu.com/ubuntu noble Release' does not have a Release file."
            in str(raised.value.details)
        )

    finally:
        instance.delete(force=True)
