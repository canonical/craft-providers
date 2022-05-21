#
# Copyright 2021-2022 Canonical Ltd.
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

"""Helper(s) for snap command."""

import pathlib
from typing import List


def formulate_local_install_command(
    classic: bool, dangerous: bool, snap_path: pathlib.Path
) -> List[str]:
    """Formulate snap install command.

    :param classic: Flag to enable installation of classic snap.
    :param dangerous: Flag to enable installation of snap without ack.

    :returns: List of command parts.
    """
    install_cmd = ["snap", "install", snap_path.as_posix()]

    if classic:
        install_cmd.append("--classic")

    if dangerous:
        install_cmd.append("--dangerous")

    return install_cmd


def formulate_remote_install_command(
    snap_name: str, channel: str, classic: bool
) -> List[str]:
    """Formulate the command to snap install from Store.

    :param snap_name: The name of the channel.
    :param channel: The channel to install the snap from.
    :param classic: Flag to enable installation of classic snap.
    :param dangerous: Flag to enable installation of snap without ack.

    :returns: List of command parts.
    """
    install_cmd = ["snap", "install", snap_name, "--channel", channel]

    if classic:
        install_cmd.append("--classic")

    return install_cmd


def formulate_refresh_command(snap_name: str, channel: str) -> List[str]:
    """Formulate snap refresh command.

    :param snap_name: The name of the channel.
    :param channel: The channel to install the snap from.

    :returns: List of command parts.
    """
    install_cmd = ["snap", "refresh", snap_name, "--channel", channel]
    return install_cmd


def formulate_remove_command(snap_name: str) -> List[str]:
    """Formulate snap remove command.

    :param snap_name: The name of the channel.

    :returns: List of command parts.
    """
    install_cmd = ["snap", "remove", snap_name]
    return install_cmd
