# Copyright 2021 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""LXD Instance Provider."""

import logging

from craft_providers import Base, bases

from .lxd_instance import LXDInstance

logger = logging.getLogger(__name__)


def launch(
    name: str,
    *,
    base_configuration: Base,
    image_name: str,
    image_remote: str,
    auto_clean: bool = False,
    ephemeral: bool = False,
    map_user_uid: bool = False,
) -> LXDInstance:
    """Create, start, and configure instance.

    If auto_clean is enabled, automatically delete an existing instance that is
    deemed to be incompatible, rebuilding it with the specified environment.

    :param name: Name of instance.
    :param base_configuration: Base configuration to apply to instance.
    :param image_name: LXD image to use, e.g. "20.04".
    :param image_remote: LXD image to use, e.g. "ubuntu".
    :param auto_clean: Automatically clean instance, if incompatible.
    :param ephemeral: Create ephemeral instance.
    :param map_user_uid: Map current uid/gid to instance's root uid/gid.

    :returns: LXD instance.

    :raises BaseConfigurationError: on unexpected error configuration base.
    :raises LXDError: on unexpected LXD error.
    """
    instance = LXDInstance(name=name)

    if instance.exists():
        # TODO: warn (or auto clean) if ephemeral or map_user_uid is mismatched.
        if not instance.is_running():
            instance.start()

        try:
            base_configuration.setup(executor=instance)
            return instance
        except bases.BaseCompatibilityError as error:
            if auto_clean:
                logger.debug(
                    "Cleaning incompatible container %r (reason: %s).",
                    instance.name,
                    error.reason,
                )
                instance.delete()
            else:
                raise

    instance.launch(
        image=image_name,
        image_remote=image_remote,
        ephemeral=ephemeral,
        map_user_uid=map_user_uid,
    )
    base_configuration.setup(executor=instance)
    return instance
