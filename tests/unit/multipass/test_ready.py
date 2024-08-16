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

import re
from unittest import mock

import pytest
from craft_providers.multipass import (
    Multipass,
    MultipassError,
    ensure_multipass_is_ready,
)


@pytest.fixture
def mock_is_installed():
    with mock.patch(
        "craft_providers.multipass._ready.is_installed", return_value=True
    ) as mock_is_installed:
        yield mock_is_installed


@pytest.fixture
def mock_multipass():
    mock_client = mock.Mock(spec=Multipass)
    mock_client.is_supported_version.return_value = True
    mock_client.version.return_value = "actual-version.0"
    mock_client.minimum_required_version = "min-required-version.0"
    return mock_client


def test_ensure_multipass_is_ready(mock_is_installed, mock_multipass):
    ensure_multipass_is_ready(multipass=mock_multipass)


def test_ensure_multipass_is_ready_fails_incompatible_version(
    mock_is_installed, mock_multipass
):
    mock_multipass.is_supported_version.return_value = False
    match = re.escape(
        "Multipass 'actual-version.0' does not meet the minimum required version "
        "'min-required-version.0'.\nVisit https://multipass.run for instructions "
        "on installing Multipass for your operating system."
    )

    with pytest.raises(MultipassError, match=match):
        ensure_multipass_is_ready(multipass=mock_multipass)


def test_ensure_multipass_is_ready_fails_not_installed(
    mock_is_installed, mock_multipass
):
    mock_is_installed.return_value = False

    match = re.escape(
        "Multipass is required, but not installed.\n"
        "Visit https://multipass.run for instructions "
        "on installing Multipass for your operating system."
    )

    with pytest.raises(MultipassError, match=match):
        ensure_multipass_is_ready(multipass=mock_multipass)
