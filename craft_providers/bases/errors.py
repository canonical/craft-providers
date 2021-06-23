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

"""Base errors."""

from typing import Optional

from craft_providers.errors import ProviderError


class BaseConfigurationError(ProviderError):
    """Error configuring the base."""


class BaseCompatibilityError(ProviderError):
    """Base configuration compatibility error.

    :param reason: Reason for incompatibility.
    """

    def __init__(self, reason: str, *, details: Optional[str] = None) -> None:
        self.reason = reason

        brief = f"Incompatible base detected: {reason}."
        resolution = "Clean incompatible instance and retry the requested operation."

        super().__init__(brief=brief, details=details, resolution=resolution)
