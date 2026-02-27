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
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""Pydantic models for snap metadata returned by snapd."""

import pydantic


class SnapPublisher(pydantic.BaseModel, extra="ignore"):
    """Publisher information returned by snapd."""

    id: str


class SnapInfo(pydantic.BaseModel, extra="ignore"):
    """Information about an installed snap returned by snapd."""

    id: str
    name: str | None = None
    type: str | None = None
    version: str | None = None
    channel: str | None = None
    confinement: str | None = None
    revision: str
    publisher: SnapPublisher | None = None
    base: str | None = None
