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
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Union

from craft_providers import Base
from craft_providers.bases import centos, get_base_alias, ubuntu

from .errors import LXDError
from .lxc import LXC

logger = logging.getLogger(__name__)

BUILDD_RELEASES_REMOTE_NAME = "craft-com.ubuntu.cloud-buildd"
BUILDD_RELEASES_REMOTE_ADDRESS = "https://cloud-images.ubuntu.com/buildd/releases"

# XXX: lunar and kinetic buildd daily images are not working (LP #2007419)
BUILDD_DAILY_REMOTE_NAME = "craft-com.ubuntu.cloud-buildd-daily"
BUILDD_DAILY_REMOTE_ADDRESS = "https://cloud-images.ubuntu.com/buildd/daily"

# temporarily use the cloud release images until daily buildd images are fixed
DAILY_REMOTE_NAME = "ubuntu-daily"
DAILY_REMOTE_ADDRESS = "https://cloud-images.ubuntu.com/daily"


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
    """

    image_name: str
    remote_name: str
    remote_address: str
    remote_protocol: ProtocolType

    @property
    def is_stable(self) -> bool:
        """Check if the image is stable.

        Images are stable if they are from a release remote.
        Images from daily, devel, and any other remotes are not stable.

        :returns: True if the image is stable.
        """
        if (
            self.remote_name == BUILDD_RELEASES_REMOTE_NAME
            and self.remote_address == BUILDD_RELEASES_REMOTE_ADDRESS
        ):
            # Ubuntu official buildd images
            return True

        if self.remote_name == "images":
            # LXD daily images
            return False

        return False

    def add_remote(self, lxc: LXC) -> None:
        """Add the LXD remote for an image.

        If the remote already exists, it will not be re-added.

        :param lxc: LXC client.
        """
        # TODO verify both the remote name and address
        if self.remote_name in lxc.remote_list():
            logger.debug("Remote %r already exists.", self.remote_name)
        else:
            try:
                lxc.remote_add(
                    remote=self.remote_name,
                    addr=self.remote_address,
                    protocol=self.remote_protocol.value,
                )

            except Exception as exc:  # pylint: disable=broad-except
                # the remote adding failed, no matter really how: if it was because a
                # race condition on remote creation (it's not idempotent) and now the
                # remote is there, the purpose of this function is done (otherwise we
                # let the original exception fly)
                if self.remote_name in lxc.remote_list():
                    logger.debug(
                        "Remote %r is present on second check, ignoring exception %r.",
                        self.remote_name,
                        exc,
                    )
                else:
                    raise
            else:
                logger.debug("Remote %r was successfully added.", self.remote_name)


# XXX: support xenial?
# mapping from supported bases to actual lxd remote images
_PROVIDER_BASE_TO_LXD_REMOTE_IMAGE: Dict[Enum, RemoteImage] = {
    ubuntu.BuilddBaseAlias.BIONIC: RemoteImage(
        image_name="core18",
        remote_name=BUILDD_RELEASES_REMOTE_NAME,
        remote_address=BUILDD_RELEASES_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
    ubuntu.BuilddBaseAlias.FOCAL: RemoteImage(
        image_name="core20",
        remote_name=BUILDD_RELEASES_REMOTE_NAME,
        remote_address=BUILDD_RELEASES_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
    ubuntu.BuilddBaseAlias.JAMMY: RemoteImage(
        image_name="core22",
        remote_name=BUILDD_RELEASES_REMOTE_NAME,
        remote_address=BUILDD_RELEASES_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
    ubuntu.BuilddBaseAlias.KINETIC: RemoteImage(
        image_name="kinetic",
        remote_name=DAILY_REMOTE_NAME,
        remote_address=DAILY_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
    ubuntu.BuilddBaseAlias.LUNAR: RemoteImage(
        image_name="lunar",
        remote_name=DAILY_REMOTE_NAME,
        remote_address=DAILY_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
    ubuntu.BuilddBaseAlias.DEVEL: RemoteImage(
        image_name="devel",
        remote_name=DAILY_REMOTE_NAME,
        remote_address=DAILY_REMOTE_ADDRESS,
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
    centos.CentOSBaseAlias.SEVEN: RemoteImage(
        image_name="centos/7",
        remote_name="images",
        remote_address="https://images.linuxcontainers.org/images/",
        remote_protocol=ProtocolType.SIMPLESTREAMS,
    ),
}


def get_remote_image(provider_base: Union[Base, str]) -> RemoteImage:
    """Get a RemoteImage for a particular provider base.

    :param provider_base: string containing the provider base

    :returns: the RemoteImage for the provider base
    """
    # temporary backward compatibility before 2.0
    if isinstance(provider_base, str):
        alias = get_base_alias(("ubuntu", provider_base))
        provider_base = ubuntu.BuilddBase(alias=alias)  # type: ignore

    image = _PROVIDER_BASE_TO_LXD_REMOTE_IMAGE.get(provider_base.alias)
    if not image:
        raise LXDError(
            brief=(
                "could not find a lxd remote image for the provider base "
                f"{provider_base!r}"
            )
        )

    return image


def configure_buildd_image_remote(lxc: LXC = LXC()) -> str:
    """Configure the default buildd image remote.

    This is a deprecated function to maintain the existing API. It will be
    removed with the release of craft-providers 2.0.

    :param lxc: LXC client.

    :returns: Name of remote to pass to launcher.
    """
    warnings.warn(
        message=(
            "configure_buildd_image_remote() is deprecated. "
            "Use configure_image_remote()."
        ),
        category=DeprecationWarning,
    )
    # configure the buildd remote for core22
    base = ubuntu.BuilddBase(alias=ubuntu.BuilddBaseAlias.JAMMY)
    image = get_remote_image(base)
    image.add_remote(lxc)

    return BUILDD_RELEASES_REMOTE_NAME
