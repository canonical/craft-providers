# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
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


import sys
from datetime import timedelta
from unittest.mock import MagicMock, Mock, call

import pytest
from craft_providers import Base, ProviderError, bases, lxd
from freezegun import freeze_time
from logassert import Exact  # type: ignore


@pytest.fixture()
def mock_base_configuration():
    mock_base = Mock(spec=Base)
    mock_base.compatibility_tag = "mock-compat-tag-v100"
    mock_base.get_command_environment.return_value = {"foo": "bar"}
    return mock_base


@pytest.fixture()
def mock_lxc(mocker):
    _mock_lxc = mocker.patch("craft_providers.lxd.launcher.LXC", spec=lxd.LXC)
    _mock_lxc.return_value.project_list.return_value = ["default", "test-project"]
    return _mock_lxc.return_value


@pytest.fixture()
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


@pytest.fixture()
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


@pytest.fixture()
def mock_lxd_instance(fake_instance, fake_base_instance, mocker):
    """Mock LXD instance to return fake_instance then fake_base_instance."""
    return mocker.patch(
        "craft_providers.lxd.launcher.LXDInstance",
        spec=lxd.LXDInstance,
        side_effect=[fake_instance, fake_base_instance],
    )


@pytest.fixture()
def mock_is_valid(mocker):
    return mocker.patch("craft_providers.lxd.launcher._is_valid", return_value=True)


@pytest.fixture()
def mock_check_id_map(mocker):
    return mocker.patch("craft_providers.lxd.launcher._check_id_map", return_value=True)


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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=False),
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
        call.config_set(
            instance_name="test-base-instance-e14661a426076717fa04",
            key="image.description",
            value="test-base-instance-$",
            project="test-project",
            remote="test-remote",
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=False),
        call.stop(),
        call.start(),
    ]
    assert fake_base_instance.mock_calls == [
        call.exists(),
        call.__bool__(),
        call.__bool__(),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.get_command_environment(),
        call.setup(executor=fake_instance),
        call.wait_until_ready(executor=fake_instance),
    ]


@pytest.mark.parametrize(("map_user_uid", "uid"), [(True, 1234), (False, None)])
def test_launch_use_existing_base_instance(
    fake_instance,
    fake_base_instance,
    mock_base_configuration,
    mock_is_valid,
    mock_lxc,
    mock_lxd_instance,
    map_user_uid,
    uid,
):
    """Create instance from an existing base instance."""
    fake_base_instance.exists.return_value = True

    lxd.launch(
        name=fake_instance.name,
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        map_user_uid=map_user_uid,
        uid=uid,
        use_base_instance=True,
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
    )

    expected_mock_lxc_calls = [
        call.project_list("test-remote"),
        call.copy(
            source_remote="test-remote",
            source_instance_name=fake_base_instance.instance_name,
            destination_remote="test-remote",
            destination_instance_name=fake_instance.instance_name,
            project="test-project",
        ),
    ]
    if map_user_uid:
        expected_mock_lxc_calls.append(
            call.config_set(
                instance_name=fake_instance.instance_name,
                key="raw.idmap",
                value="both 1234 0",
                project="test-project",
                remote="test-remote",
            ),
        )
    assert mock_lxc.mock_calls == expected_mock_lxc_calls
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
        call.config_set(
            instance_name="test-base-instance-e14661a426076717fa04",
            key="image.description",
            value="test-base-instance-$",
            project="test-project",
            remote="test-remote",
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=False),
        call.stop(),
        call.start(),
    ]
    assert fake_base_instance.mock_calls == [
        call.exists(),
        call.delete(),
        call.__bool__(),
        call.__bool__(),
    ]
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

    assert mock_lxc.mock_calls == [
        call.project_list("test-remote"),
        call.config_set(
            instance_name=fake_instance.instance_name,
            key="raw.idmap",
            value="both 1234 0",
            project="test-project",
            remote="test-remote",
        ),
    ]
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=True),
        call.stop(),
        call.start(),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
        call.wait_until_ready(executor=fake_instance),
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=False),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
    ]


def test_launch_with_existing_instance_not_running(
    fake_instance,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
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
    fake_instance,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
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
    fake_instance,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=False),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.warmup(executor=fake_instance),
        call.setup(executor=fake_instance),
    ]


def test_launch_with_existing_instance_incompatible_without_auto_clean_error(
    fake_instance,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
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
    fake_instance,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=True),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.setup(executor=fake_instance),
    ]


def test_launch_existing_instance_id_map_mismatch_with_auto_clean(
    fake_instance,
    logs,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
):
    """If the id map is incorrect and auto_clean is true, return False."""
    fake_instance.exists.return_value = True
    mock_check_id_map.return_value = False

    result = lxd.launcher._launch_existing_instance(
        instance=fake_instance,
        lxc=mock_lxc,
        base_configuration=mock_base_configuration,
        project="test-project",
        remote="test-remote",
        auto_clean=True,
        ephemeral=False,
        map_user_uid=True,
        uid=1234,
    )

    assert not result

    assert (
        Exact(
            f"Cleaning incompatible instance '{fake_instance.instance_name}' (reason: "
            "the instance's id map ('raw.idmap') is not configured as expected)."
        )
        in logs.warning
    )


def test_launch_existing_instance_id_map_mismatch_without_auto_clean(
    fake_instance,
    mock_base_configuration,
    mock_check_id_map,
    mock_lxc,
    mock_lxd_instance,
):
    """If the id map is incorrect and auto_clean is False, raise an error."""
    fake_instance.exists.return_value = True
    mock_check_id_map.return_value = False

    with pytest.raises(bases.BaseCompatibilityError) as raised:
        lxd.launcher._launch_existing_instance(
            instance=fake_instance,
            lxc=mock_lxc,
            base_configuration=mock_base_configuration,
            project="test-project",
            remote="test-remote",
            auto_clean=False,
            ephemeral=False,
            map_user_uid=True,
            uid=1234,
        )

    assert raised.value.brief == (
        "Incompatible base detected: "
        "the instance's id map ('raw.idmap') is not configured as expected."
    )


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
        call.config_set(
            instance_name="test-base-instance-e14661a426076717fa04",
            key="image.description",
            value="test-base-instance-$",
            project="test-project",
            remote="test-remote",
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
        call.launch(image="image-name", image_remote="image-remote", ephemeral=False),
        call.stop(),
        call.start(),
    ]
    assert fake_base_instance.mock_calls == [
        call.exists(),
        call.__bool__(),
        call.__bool__(),
    ]
    assert mock_base_configuration.mock_calls == [
        call.get_command_environment(),
        call.get_command_environment(),
        call.setup(executor=fake_instance),
        call.wait_until_ready(executor=fake_instance),
    ]


@freeze_time("2022/12/07 11:05:00 UTC")
@pytest.mark.parametrize(
    "creation_date",
    [
        "2022/09/08 11:05 UTC",  # 90 days old
        "2022/12/06 11:05 UTC",  # 1 day old
        "2022/12/08 11:05 UTC",  # 1 day in the future (improbable but valid)
    ],
)
def test_is_valid(creation_date, mocker, mock_lxc):
    """Instances younger than the expiration date (inclusive) are valid."""
    mock_lxc.info.return_value = {"Created": creation_date}

    is_valid = lxd.launcher._is_valid(
        instance_name="test-name",
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
        expiration=timedelta(days=90),
    )

    assert is_valid


@freeze_time("2022/12/07 11:05:00 UTC")
def test_is_valid_expired(mocker, mock_lxc):
    """Instances older than the expiration date are not valid."""
    # 91 days old
    mock_lxc.info.return_value = {"Created": "2022/09/07 11:05 UTC"}

    is_valid = lxd.launcher._is_valid(
        instance_name="test-name",
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
        expiration=timedelta(days=90),
    )

    assert not is_valid


def test_is_valid_lxd_error(logs, mocker, mock_lxc):
    """Warn if the instance's info cannot be retrieved."""
    mock_lxc.info.side_effect = lxd.LXDError("test error")

    is_valid = lxd.launcher._is_valid(
        instance_name="test-name",
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
        expiration=timedelta(days=1),
    )

    assert not is_valid
    assert Exact("Could not get instance info with error: test error") in logs.warning


def test_is_valid_key_error(logs, mocker, mock_lxc):
    """Warn if the instance does not have a creation date."""
    mock_lxc.info.return_value = {}

    is_valid = lxd.launcher._is_valid(
        instance_name="test-name",
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
        expiration=timedelta(days=1),
    )

    assert not is_valid
    assert Exact("Instance does not have a 'Created' date.") in logs.warning


def test_is_valid_value_error(logs, mocker, mock_lxc):
    """Warn if the instance's creation date cannot be parsed."""
    mock_lxc.info.return_value = {"Created": "bad-datetime-value"}

    is_valid = lxd.launcher._is_valid(
        instance_name="test-name",
        project="test-project",
        remote="test-remote",
        lxc=mock_lxc,
        expiration=timedelta(days=1),
    )

    assert not is_valid
    assert (
        Exact(
            "Could not parse instance's 'Created' date with error: ValueError(\"time "
            "data 'bad-datetime-value' does not match format '%Y/%m/%d %H:%M %Z'\")"
        )
        in logs.warning
    )


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on windows")
def test_set_id_map_default(fake_base_instance, mock_lxc, mocker):
    """Verify `_set_id_map()` sets the id map with default arguments."""
    mocker.patch("craft_providers.lxd.launcher.os.getuid", return_value=101)

    lxd.launcher._set_id_map(instance=fake_base_instance, lxc=mock_lxc)

    assert mock_lxc.config_set.mock_calls == [
        call(
            instance_name=fake_base_instance.instance_name,
            key="raw.idmap",
            value="both 101 0",
            project="default",
            remote="local",
        )
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on windows")
def test_set_id_map_all_options(fake_base_instance, mock_lxc, mocker):
    """Verify `_set_id_map()` sets the id map with all parameters specified."""
    mocker.patch("craft_providers.lxd.launcher.os.getuid", return_value=101)

    lxd.launcher._set_id_map(
        instance=fake_base_instance,
        lxc=mock_lxc,
        project="test-project",
        remote="test-remote",
        uid=202,
    )

    assert mock_lxc.config_set.mock_calls == [
        call(
            instance_name=fake_base_instance.instance_name,
            key="raw.idmap",
            value="both 202 0",
            project="test-project",
            remote="test-remote",
        )
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on windows")
@pytest.mark.parametrize(
    ("map_user_uid", "actual_uid", "expected_uid", "expected_result"),
    [
        # return True if an id map is not expected and there is no id map
        (False, None, None, True),
        # return False if an id map is expected and there is no id map
        (True, None, 5678, False),
        # return False if id map is not expected and there is an id map
        (False, 1234, None, False),
        # return True if an id map is expected and the uid matches
        (True, 1234, 1234, True),
        # return False if an id map is expected and the uid does not match
        (True, 1234, 5678, False),
        # return True if an id map is expected and the uid matches the current users uid
        (True, 101, None, True),
    ],
)
def test_check_id_map(
    map_user_uid,
    expected_uid,
    actual_uid,
    expected_result,
    fake_base_instance,
    mock_lxc,
    mocker,
):
    """Verify the instances id map is properly checked."""
    mocker.patch("craft_providers.lxd.launcher.os.getuid", return_value=101)

    if actual_uid:
        mock_lxc.config_get.return_value = f"both {actual_uid} 0"
    else:
        mock_lxc.config_get.return_value = ""

    result = lxd.launcher._check_id_map(
        instance=fake_base_instance,
        lxc=mock_lxc,
        project="test-project",
        remote="test-remote",
        map_user_uid=map_user_uid,
        uid=expected_uid,
    )

    assert result == expected_result


def test_check_id_map_wrong_format(fake_base_instance, logs, mock_lxc, mocker):
    """Return false if the id map is not formatted as expected."""
    mock_lxc.config_get.return_value = "gid 100-200 300-400"

    result = lxd.launcher._check_id_map(
        instance=fake_base_instance,
        lxc=mock_lxc,
        project="test-project",
        remote="test-remote",
        map_user_uid=True,
        uid=1234,
    )

    assert not result
    assert (
        Exact(
            f"Unexpected id map for '{fake_base_instance.instance_name}' "
            "(expected 'both 1234 0', got 'gid 100-200 300-400')."
        )
        in logs.debug
    )
