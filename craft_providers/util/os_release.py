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

"""Parser for /etc/os-release."""

import shlex
from pathlib import Path

OS_RELEASE_FILE = Path("/etc/os-release")


def parse_os_release(content: str | None = None) -> dict[str, str]:
    """Parser for /etc/os-release.

    Format documentation at:

    https://www.freedesktop.org/software/systemd/man/os-release.html

    :param content: String contents of os-release file.  If None, will read contents of
    file from host.

    :returns: Dictionary of key-mappings found in os-release. Values are
    stripped of encapsulating quotes.
    """
    if content is None:
        with OS_RELEASE_FILE.open() as f:
            content = f.read()

    mappings: dict[str, str] = {}

    for line in shlex.split(content):
        key, eq, value = line.partition("=")
        if eq != "=":  # Not a variable getting set; ignore.
            continue
        mappings[key] = value

    return mappings
