#
# Copyright 2023 Canonical Ltd.
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

"""LXD Instance Status."""

from enum import Enum


class ProviderInstanceStatus(Enum):
    """Status of craft-providers setup of a LXD instance.

    This value is controlled by craft-providers and configured under
    `user.craft-providers.status` in the instance's config.

    This is different from the instance state, which is controlled by LXD.
    """

    PREPARING = "PREPARING"
    FINISHED = "FINISHED"
    STARTING = "STARTING"
    IN_USE = "IN_USE"


class LXDInstanceState(Enum):
    """State of a LXD instance as reported by LXD.

    The value is displayed either as `State` or `Status`, depending on the
    command and output format.

    The capitalization also varies. For example, `lxc list --format table`
    prints uppercase values but `lxc list --format yaml` gives title case values.

    Ref: https://github.com/lxc/lxc/blob/9e95451ecc718b88de46134527b1e46aee2586cd/src/lxc/state.c#L29
    """

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ABORTING = "ABORTING"
    FREEZING = "FREEZING"
    FROZEN = "FROZEN"
    THAWED = "THAWED"
