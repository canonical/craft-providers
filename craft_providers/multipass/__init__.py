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

"""Multipass provider support package."""

from ._launch import launch  # noqa: F401
from ._ready import ensure_multipass_is_ready  # noqa: F401
from .errors import MultipassError, MultipassInstallationError  # noqa: F401
from .installer import install, is_installed  # noqa: F401
from .multipass import Multipass  # noqa: F401
from .multipass_instance import MultipassInstance  # noqa: F401
from .multipass_provider import (  # noqa: F401
    PROVIDER_BASE_TO_MULTIPASS_BASE,
    MultipassProvider,
)

__all__ = [
    "Multipass",
    "MultipassInstance",
    "MultipassError",
    "MultipassInstallationError",
    "MultipassProvider",
    "PROVIDER_BASE_TO_MULTIPASS_BASE",
    "install",
    "is_installed",
    "ensure_multipass_is_ready",
    "launch",
]
