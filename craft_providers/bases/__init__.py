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

"""Collection of bases used to configure build environments."""

# Backward compatible, will be removed in 2.0
import sys
from enum import Enum
from typing import Dict, Tuple, Type

from craft_providers.errors import BaseCompatibilityError, BaseConfigurationError

from ..base import Base
from . import centos
from . import ubuntu
from . import ubuntu as buildd
from .ubuntu import BuilddBase, BuilddBaseAlias

sys.modules["craft_providers.bases.buildd"] = buildd

__all__ = [
    "ubuntu",
    "centos",
    "BuilddBase",
    "BuilddBaseAlias",
    "BaseCompatibilityError",
    "BaseConfigurationError",
]

BASE_NAME_TO_BASE_ALIAS: Dict[Tuple[str, str], Enum] = {
    ("ubuntu", "16.04"): ubuntu.BuilddBaseAlias.XENIAL,
    ("ubuntu", "18.04"): ubuntu.BuilddBaseAlias.BIONIC,
    ("ubuntu", "20.04"): ubuntu.BuilddBaseAlias.FOCAL,
    ("ubuntu", "22.04"): ubuntu.BuilddBaseAlias.JAMMY,
    ("ubuntu", "22.10"): ubuntu.BuilddBaseAlias.KINETIC,
    ("ubuntu", "23.04"): ubuntu.BuilddBaseAlias.LUNAR,
    ("ubuntu", "devel"): ubuntu.BuilddBaseAlias.DEVEL,
    ("centos", "7"): centos.CentOSBaseAlias.SEVEN,
}


def get_base_alias(
    base_name: Tuple[str, str],
) -> Enum:
    """Return a Base alias from a base (name, version) tuple."""
    if base_name in BASE_NAME_TO_BASE_ALIAS:
        return BASE_NAME_TO_BASE_ALIAS[base_name]

    raise BaseConfigurationError(f"Base alias not found for {base_name}")


def get_base_from_alias(
    alias: Enum,
) -> Type[Base]:
    """Return a Base class from a known base alias."""
    if isinstance(alias, ubuntu.BuilddBaseAlias):
        return ubuntu.BuilddBase

    if isinstance(alias, centos.CentOSBaseAlias):
        return centos.CentOSBase

    raise BaseConfigurationError(f"Base not found for alias {alias}")
