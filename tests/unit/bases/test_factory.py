# Copyright 2025 Canonical Ltd.
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
"""Tests for the base factory."""

from typing import Literal

import pytest
from craft_providers import get_base
from craft_providers.bases.almalinux import AlmaLinuxBase, AlmaLinuxBaseAlias
from craft_providers.bases.centos import CentOSBase, CentOSBaseAlias
from craft_providers.bases.ubuntu import BuilddBase, BuilddBaseAlias


@pytest.mark.parametrize(
    ("distribution", "series", "base_cls"),
    [
        *(("ubuntu", alias.value, BuilddBase) for alias in BuilddBaseAlias),
        *(("centos", alias.value, CentOSBase) for alias in CentOSBaseAlias),
        *(("almalinux", alias.value, AlmaLinuxBase) for alias in AlmaLinuxBaseAlias),
    ],
)
def test_get_base_correct(
    distribution: Literal["ubuntu", "centos", "almalinux"], series: str, base_cls: type
):
    assert isinstance(get_base(distribution=distribution, series=series), base_cls)


def test_unknown_distribution():
    with pytest.raises(ValueError, match="Unknown distribution 'invalid'"):
        get_base(distribution="invalid", series="4")


def test_bad_series():
    with pytest.raises(ValueError, match="Unknown Ubuntu series: 4.04"):
        get_base(distribution="ubuntu", series="4.04")
