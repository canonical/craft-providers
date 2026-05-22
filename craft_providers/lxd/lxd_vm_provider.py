# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2026 Canonical Ltd.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""LXD VM Provider class."""

from __future__ import annotations

from typing import Literal

from .lxd_provider import LXDProvider


class LXDVMProvider(LXDProvider):
    """LXD provider variant that launches virtual machines."""

    _instance_type: Literal["container", "virtual-machine"] = "virtual-machine"

    @property
    def name(self) -> str:
        """Name of the provider."""
        return "LXD VM"
