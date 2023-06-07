#
# Copyright 2021 Canonical Ltd.
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

from unittest import mock

import pytest
from craft_providers import lxd
from craft_providers.lxd import project


@pytest.fixture(autouse=True)
def mock_lxc():
    with mock.patch("craft_providers.lxd.LXC", spec=lxd.LXC) as lxc_mock:
        lxc_mock.return_value.profile_show.return_value = {"test": "config"}
        yield lxc_mock.return_value


def test_create_with_default_profile(mock_lxc):
    project.create_with_default_profile(
        lxc=mock_lxc,
        project="test-project",
        profile="test-profile",
        profile_project="test-profile-project",
        remote="test-remote",
    )

    assert mock_lxc.mock_calls == [
        mock.call.project_create(project="test-project", remote="test-remote"),
        mock.call.profile_show(
            profile="test-profile", project="test-profile-project", remote="test-remote"
        ),
        mock.call.profile_edit(
            profile="default",
            project="test-project",
            config={"test": "config"},
            remote="test-remote",
        ),
    ]


def test_purge(mock_lxc):
    mock_lxc.project_list.return_value = ["test-project", "default"]
    mock_lxc.list_names.return_value = ["test-instance1", "test-instance2"]
    mock_lxc.image_list.return_value = [{"fingerprint": "i1"}, {"fingerprint": "i2"}]

    project.purge(lxc=mock_lxc, project="test-project", remote="test-remote")

    assert mock_lxc.mock_calls == [
        mock.call.project_list(remote="test-remote"),
        mock.call.list_names(project="test-project", remote="test-remote"),
        mock.call.delete(
            instance_name="test-instance1",
            project="test-project",
            remote="test-remote",
            force=True,
        ),
        mock.call.delete(
            instance_name="test-instance2",
            project="test-project",
            remote="test-remote",
            force=True,
        ),
        mock.call.image_list(project="test-project"),
        mock.call.image_delete(
            image="i1", project="test-project", remote="test-remote"
        ),
        mock.call.image_delete(
            image="i2", project="test-project", remote="test-remote"
        ),
        mock.call.project_delete(project="test-project", remote="test-remote"),
    ]


def test_purge_no_project(mock_lxc):
    mock_lxc.project_list.return_value = ["default"]
    mock_lxc.list.return_value = ["test-instance1", "test-instance2"]
    mock_lxc.image_list.return_value = [{"fingerprint": "i1"}, {"fingerprint": "i2"}]

    project.purge(lxc=mock_lxc, project="test-project", remote="test-remote")

    assert mock_lxc.mock_calls == [
        mock.call.project_list(remote="test-remote"),
    ]
