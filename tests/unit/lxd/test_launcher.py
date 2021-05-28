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

from unittest import mock

import pytest

from craft_providers import Base, bases, lxd


@pytest.fixture
def mock_base_configuration():
    mock_base = mock.Mock(spec=Base)
    mock_base.compatibility_tag = "mock-compat-tag-v100"
    yield mock_base


@pytest.fixture
def mock_lxc():
    with mock.patch(
        "craft_providers.lxd.launcher.LXC",
        spec=lxd.LXC,
    ) as mock_lxc:
        yield mock_lxc.return_value


@pytest.fixture
def mock_lxd_instance():
    with mock.patch(
        "craft_providers.lxd.launcher.LXDInstance",
        spec=lxd.LXDInstance,
    ) as mock_instance:
        mock_instance.return_value.name = "test-instance"
        yield mock_instance.return_value


def test_launch(mock_base_configuration, mock_lxd_instance):
    mock_lxd_instance.exists.return_value = False

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
    )

    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance)
    ]


def test_launch_making_initial_snapshot(
    mock_base_configuration, mock_lxc, mock_lxd_instance
):
    mock_lxd_instance.exists.return_value = False
    mock_lxc.has_image.return_value = False

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_snapshots=True,
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [
        mock.call.has_image(
            image_name="snapshot-image-remote-image-name-mock-compat-tag-v100"
        ),
        mock.call.publish(
            alias="snapshot-image-remote-image-name-mock-compat-tag-v100",
            instance_name="test-instance",
            force=True,
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
        ),
        mock.call.stop(),
        mock.call.start(),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance),
        mock.call.wait_until_ready(executor=mock_lxd_instance),
    ]


def test_launch_using_existing_snapshot(
    mock_base_configuration, mock_lxc, mock_lxd_instance
):
    mock_lxd_instance.exists.return_value = False
    mock_lxc.has_image.return_value = True

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        use_snapshots=True,
        lxc=mock_lxc,
    )

    assert mock_lxc.mock_calls == [
        mock.call.has_image(
            image_name="snapshot-image-remote-image-name-mock-compat-tag-v100"
        ),
    ]
    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.launch(
            image="snapshot-image-remote-image-name-mock-compat-tag-v100",
            image_remote="local",
            ephemeral=False,
            map_user_uid=False,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance),
    ]


def test_launch_all_opts(mock_base_configuration, mock_lxd_instance):
    mock_lxd_instance.exists.return_value = False

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        ephemeral=True,
        map_user_uid=True,
    )

    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=True,
            map_user_uid=True,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance)
    ]


def test_launch_with_existing_instance_not_running(
    mock_base_configuration, mock_lxd_instance
):
    mock_lxd_instance.exists.return_value = True
    mock_lxd_instance.is_running.return_value = False

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
    )

    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.is_running(),
        mock.call.start(),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance)
    ]


def test_launch_with_existing_instance_running(
    mock_base_configuration, mock_lxd_instance
):
    mock_lxd_instance.exists.return_value = True
    mock_lxd_instance.is_running.return_value = True

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
    )

    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.is_running(),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance)
    ]


def test_launch_with_existing_instance_incompatible_with_auto_clean(
    mock_base_configuration, mock_lxd_instance
):
    mock_lxd_instance.exists.return_value = True
    mock_lxd_instance.is_running.return_value = False
    mock_base_configuration.setup.side_effect = [
        bases.BaseCompatibilityError(reason="foo"),
        None,
    ]

    lxd.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        image_name="image-name",
        image_remote="image-remote",
        auto_clean=True,
    )

    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.is_running(),
        mock.call.start(),
        mock.call.delete(),
        mock.call.launch(
            image="image-name",
            image_remote="image-remote",
            ephemeral=False,
            map_user_uid=False,
        ),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance),
        mock.call.setup(executor=mock_lxd_instance),
    ]


def test_launch_with_existing_instance_incompatible_without_auto_clean(
    mock_base_configuration, mock_lxd_instance
):
    mock_lxd_instance.exists.return_value = True
    mock_lxd_instance.is_running.return_value = False
    mock_base_configuration.setup.side_effect = [
        bases.BaseCompatibilityError(reason="foo")
    ]

    with pytest.raises(bases.BaseCompatibilityError):
        lxd.launch(
            "test-instance",
            base_configuration=mock_base_configuration,
            image_name="image-name",
            image_remote="image-remote",
            auto_clean=False,
        )

    assert mock_lxd_instance.mock_calls == [
        mock.call.exists(),
        mock.call.is_running(),
        mock.call.start(),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_lxd_instance)
    ]
