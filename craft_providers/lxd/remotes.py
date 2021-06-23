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

"""Remote helper utilities."""
import logging

from .lxc import LXC

logger = logging.getLogger(__name__)


BUILDD_REMOTE_NAME = "craft-com.ubuntu.cloud-buildd"
BUILDD_REMOTE_ADDR = "https://cloud-images.ubuntu.com/buildd/releases"


def configure_buildd_image_remote(
    lxc: LXC = LXC(),
) -> str:
    """Configure buildd remote, adding remote as required.

    :param lxc: LXC client.

    :returns: Name of remote to pass to launcher.
    """
    if BUILDD_REMOTE_NAME in lxc.remote_list():
        logger.debug("Remote %r already exists.", BUILDD_REMOTE_NAME)
    else:
        lxc.remote_add(
            remote=BUILDD_REMOTE_NAME,
            addr=BUILDD_REMOTE_ADDR,
            protocol="simplestreams",
        )
        logger.debug("Remote %r was successfully added.", BUILDD_REMOTE_NAME)

    return BUILDD_REMOTE_NAME
