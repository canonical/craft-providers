#
# Copyright 2021-2025 Canonical Ltd.
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

"""Base compatibility checks."""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING, TypedDict

from craft_providers.bases.ubuntu import BuilddBase, BuilddBaseAlias
from craft_providers.errors import (
    ProviderError,
)
from craft_providers.util.os_release import parse_os_release

if TYPE_CHECKING:
    from enum import Enum

    from craft_providers.base import Base
    from craft_providers.executor import Executor

logger = logging.getLogger(__name__)


class InvalidVersionSet(TypedDict):
    """A set of invalid version combinations for runtime assertions."""

    host_less_than_equal: BuilddBaseAlias
    guest_greater_than_equal: BuilddBaseAlias
    lxd_less_than: list[tuple[int, int, int]]
    kernel_less_than: tuple[int, int]


INVALID_VERSIONS: list[InvalidVersionSet] = [
    {
        "host_less_than_equal": BuilddBaseAlias.FOCAL,
        "guest_greater_than_equal": BuilddBaseAlias.ORACULAR,
        # The system is affected by the cgroups bug if both of the above and either of the below
        "lxd_less_than": [
            (5, 0, 4),
            (5, 21, 2),
        ],
        "kernel_less_than": (5, 15),
    },
]


def _lxd_version_match(
    system_version: tuple[int, int, int],
    affected_versions: list[tuple[int, int, int]],
) -> bool:
    """Compare the system lxd version with the list of affected versions.

    :returns: True if the system lxd version is affected, False if it is not, or if
    whether it is affected can't be determined.
    """
    # First look for matching major/minor, and compare patch
    for affected_version in affected_versions:
        if (
            affected_version[0] == system_version[0]
            and affected_version[1] == system_version[1]
        ):
            return system_version[2] < affected_version[2]

    # Assume major versions below those listed are affected, otherwise either not
    # affected or we can't tell so we won't fail.
    lowest_major = min([v[0] for v in affected_versions])
    return system_version[0] < lowest_major


def ensure_guest_compatible(
    base_configuration: Base[Enum],
    instance: Executor,
    lxd_version: str,
) -> None:
    """Ensure host is compatible with guest instance."""
    if not issubclass(type(base_configuration), BuilddBase):
        # Not ubuntu, not sure how to check
        logger.debug(
            f"Base alias configuration is {base_configuration.alias!r}: no checks for non Buildd"
        )
        return

    host_os_release = parse_os_release()
    # Return early for non Ubuntu hosts
    if host_os_release.get("ID") != "ubuntu":
        logger.debug(
            f"Host is {host_os_release.get('ID')}: no checks for non Ubuntu hosts"
        )
        return

    try:
        host_base_alias = BuilddBaseAlias(host_os_release.get("VERSION_ID"))
    except ValueError:  # Unknown Ubuntu version, don't check.
        logger.warning("Unknown host Ubuntu version, not checking guest compatibility")
        return

    guest_os_release = base_configuration.get_os_release(executor=instance)
    guest_base_alias = BuilddBaseAlias(guest_os_release.get("VERSION_ID"))

    # Strip off anything after the first space - sometimes "LTS" is appended
    lxd_version_split = lxd_version.strip().split(" ")[0].split(".")
    lxd_major = int(lxd_version_split[0])
    lxd_minor = int(lxd_version_split[1])
    try:
        lxd_patch = int(lxd_version_split[2])
    except IndexError:
        # LXD version strings sometimes omit the patch - call it zero
        lxd_patch = 0
    lxd_version_tup = (lxd_major, lxd_minor, lxd_patch)

    kernel_version_tup = tuple([int(v) for v in platform.release().split(".")[0:2]])

    # If the host OS is focal (20.04) or older, and the guest OS is oracular (24.10)
    # or newer, then the host lxd must be >=5.0.4 or >=5.21.2, and kernel must be
    # 5.15 or newer.  Otherwise, weird systemd failures will occur due to a mismatch
    # between cgroupv1 and v2 support.
    # https://discourse.ubuntu.com/t/lxd-5-0-4-lts-has-been-released/49681#p-123331-support-for-ubuntu-oracular-containers-on-cgroupv2-hosts

    for invalid in INVALID_VERSIONS:
        if (
            host_base_alias <= invalid["host_less_than_equal"]
            and guest_base_alias >= invalid["guest_greater_than_equal"]
            and (
                _lxd_version_match(
                    lxd_version_tup,
                    invalid["lxd_less_than"],
                )
                or kernel_version_tup < invalid["kernel_less_than"]
            )
        ):
            raise ProviderError(
                brief="This combination of guest and host OS versions requires a newer kernel and/or lxd.",
                resolution="Ensure you have lxd>=5.21.2 or >= 5.0.4, and kernel>=5.15 - try the lxd snap or HWE kernel.",
            )
