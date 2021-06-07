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

from .lxc import LXC
from .lxd_instance import LXDInstance

logger = logging.getLogger(__name__)


def _formulate_snapshot_image_name(
    *, image_name: str, image_remote: str, compatibility_tag: str
) -> str:
    """Compute snapshot image's name.

    It must take into account each of the following params list below.  Note
    that the image_name should incorporate the architecture to ensure uniqueness
    in case more than one arch is supported on the platform (e.g. LXD cluster).

    :param image_remote: Name of source image's remote (e.g. ubuntu).
    :param image_name: Name of source imag (e.g. 20.04)
    :param compatibility_tag: Compatibility tag of base configuration applied to
        image.

    :returns: Name of (compatible) snapshot to use.
    """
    return "-".join(
        [
            "snapshot",
            image_remote,
            image_name,
            compatibility_tag,
        ]
    )


def _publish_snapshot(
    *,
    lxc: LXC,
    snapshot_name: str,
    instance: LXDInstance,
    base_configuration: Base,
) -> None:
    """Publish snapshot from instance.

    Stop instance and publish its contents to an image with the specified alias.
    Once published, restart instance and ensure it is ready for use.

    :param lxc: LXC client.
    :param snapshot_name: Alias to use for snapshot.
    :param instance: LXD instance to snapshot from.
    :param base_configuration: Base configuration for instance.
    """
    instance.stop()

    lxc.publish(
        alias=snapshot_name,
        instance_name=instance.name,
        force=True,
    )

    # Restart container and ensure it is ready.
    instance.start()
    base_configuration.wait_until_ready(executor=instance)


def launch(
    name: str,
    *,
    base_configuration: Base,
    image_name: str,
    image_remote: str,
    auto_clean: bool = False,
    ephemeral: bool = False,
    map_user_uid: bool = False,
    use_snapshots: bool = False,
    lxc: LXC = LXC(),
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
    :param use_snapshots: Use LXD snapshots for bootstrapping images.
    :param lxc: LXC client.

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

    # Create from snapshot, if available.
    snapshot_name = _formulate_snapshot_image_name(
        image_name=image_name,
        image_remote=image_remote,
        compatibility_tag=base_configuration.compatibility_tag,
    )
    if use_snapshots and lxc.has_image(image_name=snapshot_name):
        logger.debug("Using compatible snapshot %r.", snapshot_name)
        image_name = snapshot_name
        image_remote = "local"

        # Don't re-publish this snapshot later.
        use_snapshots = False

    instance.launch(
        image=image_name,
        image_remote=image_remote,
        ephemeral=ephemeral,
        map_user_uid=map_user_uid,
    )
    base_configuration.setup(executor=instance)

    # Publish snapshot if enabled and instance is not ephemeral.
    if use_snapshots:
        if ephemeral:
            logger.debug("Refusing to publish snapshot for ephemeral instance.")
        else:
            logger.debug("Publishing snapshot from instance %r.", snapshot_name)
            _publish_snapshot(
                lxc=lxc,
                snapshot_name=snapshot_name,
                instance=instance,
                base_configuration=base_configuration,
            )

    return instance
