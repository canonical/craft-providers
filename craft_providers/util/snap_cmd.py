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

"""Helper(s) for snap command."""

import pathlib
from typing import List


def formulate_install_command(
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
