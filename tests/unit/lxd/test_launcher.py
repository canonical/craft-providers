# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2021-2022 Canonical Ltd.
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

from unittest.mock import MagicMock, Mock, call

import pytest
from logassert import Exact  # type: ignore

from craft_providers import Base, ProviderError, bases, lxd


@pytest.fixture
def mock_base_configuration():
    mock_base = Mock(spec=Base)
    mock_base.compatibility_tag = "mock-compat-tag-v100"
    mock_base.get_command_environment.return_value = {"foo": "bar"}
    yield mock_base


@pytest.fixture
def mock_lxc(mocker):
    _mock_lxc = mocker.patch("craft_providers.lxd.launcher.LXC", spec=lxd.LXC)
    _mock_lxc.return_value.project_list.return_value = ["default", "test-project"]
    yield _mock_lxc.return_value


@pytest.fixture
def fake_instance():
    """Returns a fake LXD Instance"""
    instance = MagicMock()
    # the name has an invalid character to ensure the instance_name will be different
    # so the two are not conflated in the unit tests
    instance.name = "test-instance-$"
    instance.instance_name = "test-instance-fa2d407652a1c51f6019"
    instance.project = "test-project"
    instance.remote = "test-remote"
    instance.exists.return_value = False
    instance.is_running.return_value = False
    return instance


@pytest.fixture
def fake_base_instance():
    """Returns a fake base LXD Instance"""
    base_instance = MagicMock()
    # the name has an invalid character to ensure the instance_name will be different,
    # so the two are not conflated in the unit tests
    base_instance.name = "test-base-instance-$"
    base_instance.instance_name = "test-base-instance-e14661a426076717fa04"
    base_instance.project = "test-project"
    base_instance.remote = "test-remote"
    base_instance.exists.return_value = False
    base_instance.is_running.return_value = False
    return base_instance


@pytest.fixture
def mock_lxd_instance(fake_instance, fake_base_instance, mocker):
    """Mock LXD instance to return fake_instance then fake_base_instance."""
    yield mocker.patch(
        "craft_providers.lxd.launcher.LXDInstance",
        spec=lxd.LXDInstance,
        side_effect=[fake_instance, fake_base_instance],
    )


@pytest.fixture
def mock_is_valid(mocker):
    yield mocker.patch("craft_providers.lxd.launcher._is_valid", return_value=True)


def test_launch_no_base_instance(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """Create an instance from an image and do not save a copy as the base instance."""
    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_base_instance=False,
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [call.project_list("local")]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="default",
            remote="local",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
            uid=None,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
    ]


def test_launch_use_base_instance(
    fake_instance,
    fake_base_instance,
    mock_base_configuration,
    mock_is_valid,
    mock_lxc,
    mock_lxd_instance,
):
    """Launch an instance from an image and save a copy as the base instance."""
    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_base_instance=True,
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [
        call.project_list("test-remote"),
        call.copy(
            source_remote="test-remote",
            source_instance_name=fake_instance.instance_name,
            destination_remote="test-remote",
            destination_instance_name=fake_base_instance.instance_name,
            project="test-project",
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
        call(
            name="base-instance-mock-compat-tag-v100-image-remote-image-name",
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
            uid=None,
        ),
        call.stop(),
        call.start(),
    ]
    assert fake_base_instance.mock_calls == [call.exists()]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.get_command_environment(),
        call.setup(executor=fake_instance),
        call.wait_until_ready(executor=fake_instance),
    ]


def test_launch_use_existing_base_instance(
    fake_instance,
    fake_base_instance,
    mock_base_configuration,
    mock_is_valid,
    mock_lxc,
    mock_lxd_instance,
):
    """Create instance from an existing base instance."""
    fake_base_instance.exists.return_value = True

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_base_instance=True,
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [
        call.project_list("test-remote"),
        call.copy(
            source_remote="test-remote",
            source_instance_name=fake_base_instance.instance_name,
            destination_remote="test-remote",
            destination_instance_name=fake_instance.instance_name,
            project="test-project",
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
        call(
            name="base-instance-mock-compat-tag-v100-image-remote-image-name",
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [call.exists(), call.is_running(), call.start()]
    assert fake_base_instance.mock_calls == [call.exists(), call.is_running()]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.get_command_environment(),
        call.warmup(executor=fake_instance),
    ]


def test_launch_existing_base_instance_invalid(
    fake_instance,
    fake_base_instance,
    mock_base_configuration,
    mock_is_valid,
    mock_lxc,
    mock_lxd_instance,
):
    """If the existing base instance is invalid, delete it and create a new instance."""
    fake_base_instance.exists.return_value = True
    mock_is_valid.return_value = False

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_base_instance=True,
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [
        call.project_list("test-remote"),
        call.copy(
            source_remote="test-remote",
            source_instance_name=fake_instance.instance_name,
            destination_remote="test-remote",
            destination_instance_name=fake_base_instance.instance_name,
            project="test-project",
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
        call(
            name="base-instance-mock-compat-tag-v100-image-remote-image-name",
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
            uid=None,
        ),
        call.stop(),
        call.start(),
    ]
    assert fake_base_instance.mock_calls == [call.exists(), call.delete()]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.get_command_environment(),
        call.setup(executor=fake_instance),
        call.wait_until_ready(executor=fake_instance),
    ]


def test_launch_all_opts(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """Parse all parameters."""
    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        auto_clean=True,
        auto_create_project=True,
        ephemeral=True,
        map_user_uid=True,
        uid=1234,
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [call.project_list("test-remote")]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=True,
            map_user_uid=True,
            uid=1234,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
    ]


def test_launch_missing_project(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """Raise an error if project does not exist and auto_create_project if false."""
    with pytest.raises(lxd.LXDError) as exc_info:
        lxd.launch(
            name=fake_instance.name,
            base_configuration=mock_base_configuration,
            image_name="image-name",
            image_remote="image-remote",
            auto_create_project=False,
            project="invalid-project",
            remote="test-remote",
            lxc=mock_lxc,
        )

    assert (
        exc_info.value.brief
        == "LXD project 'invalid-project' not found on remote 'test-remote'."
    )
    assert exc_info.value.details == "Available projects: ['default', 'test-project']"


def test_launch_create_project(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """Create a project if it does not exist and auto_create_project is true."""
    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        auto_create_project=True,
        project="project-to-create",
        remote="test-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [
        call.project_list("test-remote"),
        call.project_create(project="project-to-create", remote="test-remote"),
        call.profile_show(profile="default", project="default", remote="test-remote"),
        call.profile_edit(
            profile="default",
            project="project-to-create",
            config=mock_lxc.profile_show.return_value,
            remote="test-remote",
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="project-to-create",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
            uid=None,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
    ]


def test_launch_with_existing_instance_not_running(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """If the existing instance is not running, start it."""
    fake_instance.exists.return_value = True

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [call.project_list("local")]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="default",
            remote="local",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [call.exists(), call.is_running(), call.start()]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.warmup(executor=fake_instance),
    ]


def test_launch_with_existing_instance_running(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """If the existing instance is running, do not start it."""
    fake_instance.exists.return_value = True
    fake_instance.is_running.return_value = True

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [call.project_list("local")]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="default",
            remote="local",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [call.exists(), call.is_running()]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.warmup(executor=fake_instance),
    ]


def test_launch_with_existing_instance_incompatible_with_auto_clean(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """If instance is incompatible and auto_clean is true, launch a new instance."""
    fake_instance.exists.return_value = True
    fake_instance.is_running.return_value = False

    mock_base_configuration.warmup.side_effect = [
        bases.BaseCompatibilityError(reason="foo"),
        None,
    ]

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        auto_clean=True,
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [call.project_list("local")]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="default",
            remote="local",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.is_running(),
        call.start(),
        call.delete(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
            uid=None,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.warmup(executor=fake_instance),
        call.setup(executor=fake_instance),
    ]


def test_launch_with_existing_instance_incompatible_without_auto_clean_error(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """If instance is incompatible and auto_clean is False, raise an error."""
    fake_instance.exists.return_value = True
    mock_base_configuration.warmup.side_effect = [
        bases.BaseCompatibilityError(reason="foo")
    ]

    with pytest.raises(bases.BaseCompatibilityError) as raised:
        lxd.launch(
            name=fake_instance.name,
            base_configuration=mock_base_configuration,
            image_name="image-name",
            image_remote="image-remote",
            auto_clean=False,
            lxc=mock_lxc,
        )

    assert raised.value.brief == "Incompatible base detected: foo."
    assert raised.value.resolution == (
        "Clean incompatible instance and retry the requested operation."
    )


def test_launch_with_existing_ephemeral_instance(
    fake_instance, mock_base_configuration, mock_lxc, mock_lxd_instance
):
    """Delete and recreate existing ephemeral instances."""
    fake_instance.exists.return_value = True

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        ephemeral=True,
        use_base_instance=False,
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [call.project_list("local")]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="default",
            remote="local",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.delete(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=True,
            map_user_uid=False,
            uid=None,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
    ]


def test_name_matches_base_name(
    fake_instance,
    fake_base_instance,
    mock_base_configuration,
    mock_lxc,
    mock_lxd_instance,
):
    """Raise an error if the instance name matches the base instance name."""
    # force the names to be equal
    fake_instance.instance_name = fake_base_instance.instance_name

    with pytest.raises(ProviderError) as raised:
        lxd.launch(
            name=fake_instance.name,
            base_configuration=mock_base_configuration,
            image_name="image-name",
            image_remote="image-remote",
            use_base_instance=True,
            lxc=mock_lxc,
        )

    assert raised.value.brief == (
        f"instance name cannot match the base instance name: "
        f"{fake_base_instance.instance_name!r}"
    )
    assert raised.value.resolution == "change name of instance"


def test_use_snapshots_deprecated(
    fake_instance,
    fake_base_instance,
    logs,
    mock_is_valid,
    mock_base_configuration,
    mock_lxc,
    mock_lxd_instance,
):
    """Log deprecation warning for `use_snapshots` and continue to launch."""
    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_snapshots=True,
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
    )

    assert (
        Exact(
            "Deprecated: Parameter 'use_snapshots' is deprecated. "
            "Use parameter 'use_base_instance' instead."
        )
        in logs.warning
    )

    assert mock_lxc.mock_calls == [
        call.project_list("test-remote"),
        call.copy(
            source_remote="test-remote",
            source_instance_name=fake_instance.instance_name,
            destination_remote="test-remote",
            destination_instance_name=fake_base_instance.instance_name,
            project="test-project",
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        call(
            name=fake_instance.name,
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
        call(
            name="base-instance-mock-compat-tag-v100-image-remote-image-name",
            project="test-project",
            remote="test-remote",
            default_command_environment={"foo": "bar"},
        ),
    ]
    assert fake_instance.mock_calls == [
        call.exists(),
        call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
            uid=None,
        ),
        call.stop(),
        call.start(),
    ]
    assert fake_base_instance.mock_calls == [call.exists()]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.get_command_environment(),
        call.setup(executor=fake_instance),
        call.wait_until_ready(executor=fake_instance),
    ]
