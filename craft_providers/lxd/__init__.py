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

"""LXD environment provider."""

from .errors import LXDError, LXDInstallationError, LXDUnstableImageError
from .installer import (
    ensure_lxd_is_ready,
    install,
    is_initialized,
    is_installed,
    is_user_permitted,
)
from .launcher import launch
from .lxc import LXC
from .lxd import LXD
from .lxd_instance import LXDInstance
from .lxd_provider import LXDProvider
from .remotes import get_remote_image

__all__ = [
    "LXC",
    "LXD",
    "LXDInstance",
    "LXDError",
    "LXDInstallationError",
    "LXDUnstableImageError",
    "LXDProvider",
    "get_remote_image",
    "install",
    "is_installed",
    "is_initialized",
    "is_user_permitted",
    "ensure_lxd_is_ready",
    "launch",
]
