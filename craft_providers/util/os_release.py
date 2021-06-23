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

"""Parser for /etc/os-release."""
from typing import Dict


def parse_os_release(content: str) -> Dict[str, str]:
    """Parser for /etc/os-release.

    Format documentation at:

    https://www.freedesktop.org/software/systemd/man/os-release.html

    Example os-release contents::

        NAME="Ubuntu"
        VERSION="20.10 (Groovy Gorilla)"
        ID=ubuntu
        ID_LIKE=debian
        PRETTY_NAME="Ubuntu 20.10"
        VERSION_ID="20.10"
        HOME_URL="https://www.ubuntu.com/"
        SUPPORT_URL="https://help.ubuntu.com/"
        BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
        PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
        VERSION_CODENAME=groovy
        UBUNTU_CODENAME=groovy

    :param content: String contents of os-release file.

    :returns: Dictionary of key-mappings found in os-release. Values are
              stripped of encapsulating quotes.

    """
    mappings: Dict[str, str] = dict()

    for line in content.splitlines():
        line = line.strip()

        # Ignore commented lines.
        if line.startswith("#"):
            continue

        # Ignore empty lines.
        if not line:
            continue

        if "=" in line:
            key, value = line.split("=", maxsplit=1)

            # Strip encapsulating quotes, single or double.
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            mappings[key] = value

    return mappings
