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
from craft_platforms import DistroBase
from craft_providers.bases import (
    BaseName,
    almalinux,
    centos,
    get_base_alias,
    get_base_from_alias,
    ubuntu,
)
from craft_providers.errors import BaseConfigurationError


@pytest.mark.parametrize(
    ("base_name", "expected"),
    [
        (("ubuntu", "22.04"), ubuntu.BuilddBaseAlias.JAMMY),
        (("ubuntu", "24.04"), ubuntu.BuilddBaseAlias.NOBLE),
        (BaseName("ubuntu", "devel"), ubuntu.BuilddBaseAlias.DEVEL),
        (DistroBase("centos", "7"), centos.CentOSBaseAlias.SEVEN),
        (DistroBase("centos", "7.4"), centos.CentOSBaseAlias.SEVEN),
    ],
)
def test_get_base_alias(base_name, expected):
    assert get_base_alias(base_name) == expected


@pytest.mark.parametrize(
    "base_name",
    [
        ("ubuntu", "8.04"),
        ("debian", "1"),
        ("ubuntu", "24"),
        ("centos", "6"),
    ],
)
def test_get_base_alias_does_not_exist(base_name):
    with pytest.raises(
        BaseConfigurationError, match=r"^Base alias not found for BaseName\(name='"
    ):
        get_base_alias(base_name)


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        *((alias, ubuntu.BuilddBase) for alias in ubuntu.BuilddBaseAlias),
        *((alias, centos.CentOSBase) for alias in centos.CentOSBaseAlias),
        *((alias, almalinux.AlmaLinuxBase) for alias in almalinux.AlmaLinuxBaseAlias),
    ],
)
def test_get_base_from_alias(alias, expected):
    assert get_base_from_alias(alias) == expected


def test_get_base_from_alias_does_not_exist():
    with pytest.raises(BaseConfigurationError) as exc_info:
        get_base_from_alias("ubuntu 8")  # type: ignore

    assert exc_info.value == BaseConfigurationError(
        brief="Base not found for alias 'ubuntu 8'"
    )
