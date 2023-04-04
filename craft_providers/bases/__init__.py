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

from craft_providers.errors import BaseCompatibilityError, BaseConfigurationError

from . import ubuntu as buildd
from .ubuntu import BuilddBase, BuilddBaseAlias

sys.modules["craft_providers.bases.buildd"] = buildd

__all__ = [
    "BuilddBase",
    "BuilddBaseAlias",
    "BaseCompatibilityError",
    "BaseConfigurationError",
]
