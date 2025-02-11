#
# Copyright 2021-2025 Canonical Ltd.
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
"""Tests for the BaseName class."""

import pytest
from craft_platforms import DistroBase
from craft_providers.bases import BaseName

BASE_MAPPING = {
    BaseName("ubuntu", "16.04"): DistroBase("ubuntu", "16.04"),
    BaseName("ubuntu", "18.04"): DistroBase("ubuntu", "18.04"),
    BaseName("ubuntu", "20.04"): DistroBase("ubuntu", "20.04"),
    BaseName("ubuntu", "22.04"): DistroBase("ubuntu", "22.04"),
    BaseName("ubuntu", "24.04"): DistroBase("ubuntu", "24.04"),
    BaseName("ubuntu", "devel"): DistroBase("ubuntu", "devel"),
    BaseName("centos", "7"): DistroBase("centos", "7"),
}


@pytest.mark.parametrize(("base_name", "distro_base"), [*BASE_MAPPING.items()])
def test_from_distro_base(base_name: BaseName, distro_base: DistroBase):
    assert BaseName.from_distro_base(distro_base) == base_name


@pytest.mark.parametrize(("base_name", "distro_base"), [*BASE_MAPPING.items()])
def test_to_distro_base(base_name: BaseName, distro_base: DistroBase):
    assert base_name.to_distro_base() == distro_base


@pytest.mark.parametrize(("base_name"), [*BASE_MAPPING.keys()])
def test_round_trip_to_from(base_name: BaseName):
    assert BaseName.from_distro_base(base_name.to_distro_base()) == base_name


@pytest.mark.parametrize(("distro_base"), [*BASE_MAPPING.values()])
def test_round_trip_from_to(distro_base: DistroBase):
    assert BaseName.from_distro_base(distro_base).to_distro_base() == distro_base


@pytest.mark.parametrize(("base_name", "distro_base"), [*BASE_MAPPING.items()])
def test_equality(base_name, distro_base):
    assert base_name == distro_base
