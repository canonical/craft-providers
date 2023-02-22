# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
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

"""Manages LXD remotes and provides access to remote images."""

import logging
from dataclasses import dataclass
from enum import Enum

from craft_providers.bases import BuilddBaseAlias

from .errors import LXDError
from .lxc import LXC

logger = logging.getLogger(__name__)

BUILDD_RELEASES_REMOTE_NAME = "craft-com.ubuntu.cloud-buildd"
BUILDD_RELEASES_REMOTE_ADDRESS = "https://cloud-images.ubuntu.com/buildd/releases"


class ProtocolType(Enum):
    """Enumeration of protocols for LXD remotes."""

    LXD = "lxd"
    SIMPLESTREAMS = "simplestreams"


@dataclass
class RemoteImage:
    """Contains the name, location, and details of a remote LXD image.

    :param image_name: Name of the image on the remote (e.g. `core22` or `lunar`).
    :param remote_name: Name of the remote server.
    :param remote_address: Address of the remote (can be an IP, FDQN, URL, or token)
    :param remote_protocol: Remote protocol (options are `lxd` and `simplestreams`)
    :param is_stable: True if the image is a stable release. Daily and devel images
    are not stable.
    """

    image_name: str
    remote_name: str
    remote_address: str
    remote_protocol: ProtocolType
    is_stable: bool


# XXX: support xenial?
# mapping from supported bases to actual lxd remote images
_PROVIDER_BASE_TO_LXD_REMOTE_IMAGE = {
    BuilddBaseAlias.BIONIC.value: RemoteImage(
        image_name="core18",
        remote_name=BUILDD_RELEASES_REMOTE_NAME,
        remote_address=BUILDD_RELEASES_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
        is_stable=True,
    ),
    BuilddBaseAlias.FOCAL.value: RemoteImage(
        image_name="core20",
        remote_name=BUILDD_RELEASES_REMOTE_NAME,
        remote_address=BUILDD_RELEASES_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
        is_stable=True,
    ),
    BuilddBaseAlias.JAMMY.value: RemoteImage(
        image_name="core22",
        remote_name=BUILDD_RELEASES_REMOTE_NAME,
        remote_address=BUILDD_RELEASES_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
        is_stable=True,
    ),
}


def get_remote_image(provider_base: str) -> RemoteImage:
    """Get a RemoteImage for a particular provider base.

    :param provider_base: string containing the provider base

    :returns: the RemoteImage for the provider base
    """
    image = _PROVIDER_BASE_TO_LXD_REMOTE_IMAGE.get(provider_base)
    if not image:
        raise LXDError(
            brief=(
                "could not find a lxd remote image for the provider base "
                f"{provider_base!r}"
            )
        )

    return image


def configure_buildd_image_remote(
    lxc: LXC = LXC(),
) -> str:
    """Configure buildd remote, adding remote as required.
    :param lxc: LXC client.
    :returns: Name of remote to pass to launcher.
    """
    if BUILDD_RELEASES_REMOTE_NAME in lxc.remote_list():
        logger.debug("Remote %r already exists.", BUILDD_RELEASES_REMOTE_NAME)
    else:
        try:
            lxc.remote_add(
                remote=BUILDD_RELEASES_REMOTE_NAME,
                addr=BUILDD_RELEASES_REMOTE_ADDRESS,
                protocol="simplestreams",
            )
        except Exception as exc:  # pylint: disable=broad-except
            # the remote adding failed, no matter really how: if it was because a race
            # condition on remote creation (it's not idempotent) and now the remote is
            # there, the purpose of this function is done (otherwise we let the
            # original exception fly)
            if BUILDD_RELEASES_REMOTE_NAME in lxc.remote_list():
                logger.debug(
                    "Remote %r is present on second check, ignoring exception %r.",
                    BUILDD_RELEASES_REMOTE_NAME,
                    exc,
                )
            else:
                raise
        else:
            logger.debug("Remote %r was successfully added.", BUILDD_RELEASES_REMOTE_NAME)

    return BUILDD_RELEASES_REMOTE_NAME
