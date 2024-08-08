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

"""Collection of bases used to configure build environments."""

# Backward compatible, will be removed in 2.0
import sys
from typing import Dict, Literal, NamedTuple, Tuple, Type, Union, overload

from craft_providers.errors import BaseCompatibilityError, BaseConfigurationError
from craft_providers.base import Base

from . import almalinux, centos
from . import ubuntu
from . import ubuntu as buildd
from .ubuntu import BuilddBase, BuilddBaseAlias

sys.modules["craft_providers.bases.buildd"] = buildd

BaseAlias = Union[
    ubuntu.BuilddBaseAlias, almalinux.AlmaLinuxBaseAlias, centos.CentOSBaseAlias
]

__all__ = [
    "ubuntu",
    "centos",
    "BaseAlias",
    "BaseName",
    "BuilddBase",
    "BuilddBaseAlias",
    "BaseCompatibilityError",
    "BaseConfigurationError",
]


class BaseName(NamedTuple):
    """A base image, by distribution and version."""

    name: str
    version: str


BASE_NAME_TO_BASE_ALIAS: Dict[BaseName, BaseAlias] = {
    BaseName("ubuntu", "16.04"): ubuntu.BuilddBaseAlias.XENIAL,
    BaseName("ubuntu", "18.04"): ubuntu.BuilddBaseAlias.BIONIC,
    BaseName("ubuntu", "20.04"): ubuntu.BuilddBaseAlias.FOCAL,
    BaseName("ubuntu", "22.04"): ubuntu.BuilddBaseAlias.JAMMY,
    BaseName("ubuntu", "24.04"): ubuntu.BuilddBaseAlias.NOBLE,
    BaseName("ubuntu", "24.10"): ubuntu.BuilddBaseAlias.ORACULAR,
    BaseName("ubuntu", "devel"): ubuntu.BuilddBaseAlias.DEVEL,
    BaseName("centos", "7"): centos.CentOSBaseAlias.SEVEN,
    BaseName("almalinux", "9"): almalinux.AlmaLinuxBaseAlias.NINE,
}


@overload
def get_base_alias(
    base_name: Tuple[Literal["ubuntu"], str]
) -> ubuntu.BuilddBaseAlias: ...
@overload
def get_base_alias(
    base_name: Tuple[Literal["centos"], str]
) -> centos.CentOSBaseAlias: ...
@overload
def get_base_alias(
    base_name: Tuple[Literal["almalinux"], str]
) -> almalinux.AlmaLinuxBaseAlias: ...
@overload
def get_base_alias(base_name: BaseName) -> BaseAlias: ...
def get_base_alias(base_name):
    """Return a Base alias from a base (name, version) tuple."""
    base_name = BaseName(*base_name)
    if base_name.name == "ubuntu" and base_name in BASE_NAME_TO_BASE_ALIAS:
        return BASE_NAME_TO_BASE_ALIAS[base_name]

    # match other distributions sub-versions like 9.1 to 9
    _base_name = BaseName(base_name.name, base_name.version.split(".")[0])
    if _base_name in BASE_NAME_TO_BASE_ALIAS:
        return BASE_NAME_TO_BASE_ALIAS[_base_name]

    raise BaseConfigurationError(f"Base alias not found for {base_name}")


@overload
def get_base_from_alias(alias: ubuntu.BuilddBaseAlias) -> Type[ubuntu.BuilddBase]: ...
@overload
def get_base_from_alias(alias: centos.CentOSBaseAlias) -> Type[centos.CentOSBase]: ...
@overload
def get_base_from_alias(
    alias: almalinux.AlmaLinuxBaseAlias,
) -> Type[almalinux.AlmaLinuxBase]: ...
def get_base_from_alias(alias: BaseAlias) -> Type[Base]:
    """Return a Base class from a known base alias."""
    if isinstance(alias, ubuntu.BuilddBaseAlias):
        return ubuntu.BuilddBase

    if isinstance(alias, centos.CentOSBaseAlias):
        return centos.CentOSBase

    if isinstance(alias, almalinux.AlmaLinuxBaseAlias):
        return almalinux.AlmaLinuxBase

    raise BaseConfigurationError(f"Base not found for alias {alias}")
