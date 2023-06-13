#
# Copyright 2023 Canonical Ltd.
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
from craft_providers.bases import get_base_alias, get_base_from_alias, ubuntu
from craft_providers.errors import BaseConfigurationError


def test_get_base_alias():
    assert get_base_alias(("ubuntu", "22.04")) == ubuntu.BuilddBaseAlias.JAMMY


def test_get_base_alias_does_not_exist():
    with pytest.raises(BaseConfigurationError) as exc_info:
        get_base_alias(("ubuntu", "8.04"))

    assert exc_info.value == BaseConfigurationError(
        brief="Base alias not found for BaseName(name='ubuntu', version='8.04')"
    )


def test_get_base_from_alias():
    assert get_base_from_alias(ubuntu.BuilddBaseAlias.JAMMY) == ubuntu.BuilddBase


def test_get_base_from_alias_does_not_exist():
    with pytest.raises(BaseConfigurationError) as exc_info:
        get_base_from_alias("ubuntu 8")  # type: ignore

    assert exc_info.value == BaseConfigurationError(
        brief="Base not found for alias ubuntu 8"
    )
