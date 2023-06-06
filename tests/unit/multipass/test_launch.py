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

from unittest import mock

import pytest
from craft_providers import Base, bases, multipass


@pytest.fixture()
def mock_base_configuration():
    return mock.Mock(spec=Base)


@pytest.fixture()
def mock_multipass_instance():
    with mock.patch(
        "craft_providers.multipass._launch.MultipassInstance",
        spec=multipass.MultipassInstance,
    ) as mock_instance:
        mock_instance.return_value.name = "test-instance"
        yield mock_instance.return_value


def test_launch_fresh(mock_base_configuration, mock_multipass_instance):
    mock_multipass_instance.exists.return_value = False

    multipass.launch(
        "test-instance", base_configuration=mock_base_configuration, image_name="30.04"
    )

    assert mock_multipass_instance.mock_calls == [
        mock.call.exists(),
        mock.call.launch(cpus=2, disk_gb=64, mem_gb=2, image="30.04"),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.setup(executor=mock_multipass_instance)
    ]


def test_launch_with_existing_instance(
    mock_base_configuration, mock_multipass_instance
):
    mock_multipass_instance.exists.return_value = True

    multipass.launch(
        "test-instance", base_configuration=mock_base_configuration, image_name="30.04"
    )

    assert mock_multipass_instance.mock_calls == [
        mock.call.exists(),
        mock.call.start(),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.warmup(executor=mock_multipass_instance)
    ]


def test_launch_with_existing_instance_incompatible_with_auto_clean(
    mock_base_configuration, mock_multipass_instance
):
    mock_multipass_instance.exists.return_value = True
    mock_base_configuration.warmup.side_effect = [
        bases.BaseCompatibilityError(reason="foo"),
        None,
    ]

    multipass.launch(
        "test-instance",
        base_configuration=mock_base_configuration,
        cpus=2,
        disk_gb=64,
        mem_gb=2,
        image_name="30.04",
        auto_clean=True,
    )

    assert mock_multipass_instance.mock_calls == [
        mock.call.exists(),
        mock.call.start(),
        mock.call.delete(),
        mock.call.launch(cpus=2, disk_gb=64, mem_gb=2, image="30.04"),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.warmup(executor=mock_multipass_instance),
        mock.call.setup(executor=mock_multipass_instance),
    ]


def test_launch_with_existing_instance_incompatible_without_auto_clean(
    mock_base_configuration, mock_multipass_instance
):
    mock_multipass_instance.exists.return_value = True
    mock_base_configuration.warmup.side_effect = [
        bases.BaseCompatibilityError(reason="foo")
    ]

    with pytest.raises(bases.BaseCompatibilityError):
        multipass.launch(
            "test-instance",
            base_configuration=mock_base_configuration,
            image_name="30.04",
            auto_clean=False,
        )

    assert mock_multipass_instance.mock_calls == [
        mock.call.exists(),
        mock.call.start(),
    ]
    assert mock_base_configuration.mock_calls == [
        mock.call.warmup(executor=mock_multipass_instance)
    ]
