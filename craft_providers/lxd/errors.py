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
"""LXD Errors."""

from typing import Optional

from craft_providers.errors import ProviderError


class LXDError(ProviderError):
    """Unexpected LXD error."""


class LXDInstallationError(LXDError):
    """LXD Installation Error.

    :param reason: Reason for install failure.
    :param details: Optional details to include.
    """

    def __init__(
        self,
        reason: str,
        *,
        details: Optional[str] = None,
    ) -> None:
        brief = f"Failed to install LXD: {reason}."
        resolution = "Please visit https://linuxcontainers.org/lxd/getting-started-cli/ for instructions on installing LXD for your operating system."

        super().__init__(brief=brief, details=details, resolution=resolution)
