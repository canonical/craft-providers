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

"""LXD Instance Provider."""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from craft_providers import Base, ProviderError, bases

from .errors import LXDError
from .lxc import LXC
from .lxd_instance import LXDInstance
from .project import create_with_default_profile

logger = logging.getLogger(__name__)


def _create_instance(
    *,
    instance: LXDInstance,
    base_instance: Optional[LXDInstance],
    base_configuration: Base,
    image_name: str,
    image_remote: str,
    ephemeral: bool,
    map_user_uid: bool,
    uid: Optional[int],
    project: str,
    remote: str,
    lxc: LXC,
) -> None:
    """Launch and setup an instance from an image.

    If a base instance is passed, copy the instance to the base instance.

    Preconditions: The LXD project exists and the instance and base instance (if
    defined) do not exist.

    :param instance: LXD instance to launch and setup
    :param base_instance: LXD instance to be created as a copy of the instance. If the
    base_instance is None, a base instance will not be created.
    :param base_configuration: Base configuration to apply to instance.
    :param image_name: LXD image to use, e.g. "20.04".
    :param image_remote: LXD image to use, e.g. "ubuntu".
    :param ephemeral: After the instance is stopped, delete it.
    :param map_user_uid: Map host uid/gid to instance's root uid/gid.
    :param uid: The uid to be mapped, if ``map_user_uid`` is enabled.
    :param project: LXD project to create instance in.
    :param remote: LXD remote to create instance on.
    :param lxc: LXC client.
    """
    logger.warning(
        "Creating new instance from image %r from remote %r.", image_name, image_remote
    )
    instance.launch(image=image_name, image_remote=image_remote, ephemeral=ephemeral)
    base_configuration.setup(executor=instance)

    # return early if base instances and user id mapping are not specified
    if not base_instance and not map_user_uid:
        return

    # the instance needs to be stopped before copying or updating the id map
    instance.stop()

    if base_instance:
        logger.warning(
            "Creating new base instance %r from instance.", base_instance.instance_name
        )
        lxc.copy(
            source_remote=remote,
            source_instance_name=instance.instance_name,
            destination_remote=remote,
            destination_instance_name=base_instance.instance_name,
            project=project,
        )

        # set the full instance name as image description
        lxc.config_set(
            instance_name=base_instance.instance_name,
            key="image.description",
            value=base_instance.name,
            project=project,
            remote=remote,
        )

    # after creating the base instance, the id map can be set
    if map_user_uid:
        _set_id_map(instance=instance, lxc=lxc, project=project, remote=remote, uid=uid)

    # now restart and wait for the instance to be ready
    instance.start()
    base_configuration.wait_until_ready(executor=instance)


def _ensure_project_exists(
    *, create: bool, project: str, remote: str, lxc: LXC
) -> None:
    """Check if project exists and create it if it does not exist.

    :param create: Create project if not found.
    :param project: LXD project name to create.
    :param remote: LXD remote to create project on.
    :param lxc: LXC client.

    :raises LXDError: on error.
    """
    projects = lxc.project_list(remote)
    if project in projects:
        return

    if create:
        create_with_default_profile(project=project, remote=remote, lxc=lxc)
    else:
        raise LXDError(
            brief=f"LXD project {project!r} not found on remote {remote!r}.",
            details=f"Available projects: {projects!r}",
        )


def _formulate_base_instance_name(
    *, image_name: str, image_remote: str, compatibility_tag: str
) -> str:
    """Compute the base instance name.

    :param image_remote: Name of source image's remote (e.g. ubuntu).
    :param image_name: Name of source image (e.g. 20.04). The image name should include
    the architecture to ensure uniqueness amongst multiple architectures built on the
    same platform.
    :param compatibility_tag: Compatibility tag of base configuration applied to the
    base instance.

    :returns: Name of (compatible) base instance.
    """
    return "-".join(["base-instance", compatibility_tag, image_remote, image_name])


def _is_valid(
    *,
    instance_name: str,
    project: str,
    remote: str,
    lxc: LXC,
    expiration: timedelta,
) -> bool:
    """Check if an instance is valid.

    Instances are valid if they are not expired (too old). An instance's age is measured
    by it's creation date. For example, if the expiration is 90 days, then the instance
    will expire 91 days after it was created.

    If errors occur during the validity check, the instance is assumed to be invalid.

    :param instance_name: Name of instance to check the validity of.
    :param project: LXD project name to create.
    :param remote: LXD remote to create project on.
    :param lxc: LXC client.
    :param expiration: How long an instance will be valid from its creation date.

    :returns: True if the instance is valid. False otherwise.
    """
    logger.debug("Checking validity of instance %r.", instance_name)

    # capture instance info
    try:
        info = lxc.info(instance_name=instance_name, project=project, remote=remote)
    except LXDError as raised:
        # if the base instance info can't be retrieved, consider it invalid
        logger.warning("Could not get instance info with error: %s", raised)
        return False

    creation_date_raw = info.get("Created")

    # if the base instance does not have a creation date, consider it invalid
    if not creation_date_raw:
        logger.warning("Instance does not have a 'Created' date.")
        return False

    # parse datetime
    try:
        creation_date = datetime.strptime(creation_date_raw, "%Y/%m/%d %H:%M %Z")
    except ValueError as raised:
        # if the date can't be parsed, consider it invalid
        logger.warning(
            "Could not parse instance's 'Created' date with error: %r", raised
        )
        return False

    expiration_date = datetime.now() - expiration
    if creation_date < expiration_date:
        logger.warning(
            "Instance is expired (Instance creation date: %s, expiration date: %s).",
            creation_date,
            expiration_date,
        )
        return False

    logger.debug("Instance is valid.")
    return True


def _launch_existing_instance(
    *,
    instance: LXDInstance,
    lxc: LXC,
    project: str,
    remote: str,
    auto_clean: bool,
    base_configuration: Base,
    ephemeral: bool,
    map_user_uid: bool,
    uid: Optional[int],
) -> bool:
    """Start and warmup an existing instance.

    Autocleaning allows for an incompatible instance to be deleted and rebuilt rather
    than raising an error. Autocleaning will be triggered if:
    - the base instance is incompatible for any reason (e.g. wrong OS)
    - the instance's existing id map does not match the id map passed to this function

    :param instance: LXD instance to launch
    :param lxc: LXC client.
    :param project: LXD project of the instance.
    :param remote: LXD remote of the instance.
    :param auto_clean: If true, clean incompatible instances.
    :param base_configuration: Base configuration to apply to the instance.
    :param ephemeral: If the instance is ephemeral, it will not be launched.
    Instead, the instance will be deleted and the function will return false.
    :param map_user_uid: True if host uid/gid should be mapped to the instance's
    root uid/gid.
    :param uid: The host uid that should be mapped, if ``map_user_uid`` is enabled.
    If none, use the current user's uid.

    :returns: True if the instance was started and warmed up. False otherwise.

    :raises BaseCompatibilityError: If the instance is incompatible.
    """
    if not _check_id_map(
        instance=instance,
        lxc=lxc,
        project=project,
        remote=remote,
        map_user_uid=map_user_uid,
        uid=uid,
    ):
        if auto_clean:
            logger.warning(
                "Cleaning incompatible instance %r (reason: %s).",
                instance.instance_name,
                "the instance's id map ('raw.idmap') is not configured as expected",
            )
            # delete the instance so a new instance can be created
            instance.delete()
            return False
        raise bases.BaseCompatibilityError(
            reason="the instance's id map ('raw.idmap') is not configured as expected"
        )

    if ephemeral:
        logger.warning("Instance exists and is ephemeral. Cleaning instance.")
        instance.delete()
        return False

    if instance.is_running():
        logger.warning("Instance exists and is running.")
    else:
        logger.warning("Instance exists and is not running. Starting instance.")
        instance.start()

    try:
        base_configuration.warmup(executor=instance)
        return True
    except bases.BaseCompatibilityError as error:
        # delete the instance so a new instance can be created
        if auto_clean:
            logger.warning(
                "Cleaning incompatible instance %r (reason: %s).",
                instance.instance_name,
                error.reason,
            )
            instance.delete()
            return False
        raise


def _check_id_map(
    *,
    instance: LXDInstance,
    lxc: LXC,
    project: str,
    remote: str,
    map_user_uid: bool,
    uid: Optional[int],
) -> bool:
    """Check if the instance's id map matches the uid passed as an argument.

    :param instance: LXD instance to set the idmap of
    :param lxc: LXC client.
    :param project: LXD project to create instance in.
    :param remote: LXD remote to create instance on.
    :param map_user_uid: If true, check that the instance has an id map.
    If false, check that the instance has no id map.
    :param uid: The uid that should already be mapped. If None, the current user's uid
    is used.

    :returns: True if the instance's id map matches the expected id map.
    """
    if uid is None:
        uid = os.getuid()

    configured_id_map = lxc.config_get(
        instance_name=instance.instance_name,
        key="raw.idmap",
        project=project,
        remote=remote,
    )

    # if the id map is not configured and should not be configured, then return True
    if not configured_id_map and not map_user_uid:
        return True

    match = re.fullmatch("both ([0-9]+) 0", configured_id_map)

    # if the id map is not exactly what craft-providers configured, then return False
    if not match:
        logger.debug(
            "Unexpected id map for %r (expected 'both %s 0', got %r).",
            instance.instance_name,
            uid,
            configured_id_map,
        )
        return False

    # get the configured uid from the id map
    configured_uid = int(match.group(1))

    return configured_uid == uid


def _set_id_map(
    *,
    instance: LXDInstance,
    lxc: LXC = LXC(),
    project: str = "default",
    remote: str = "local",
    uid: Optional[int] = None,
) -> None:
    """Configure the instance's id map.

    By default, LXD creates unprivileged containers by using user namespaces to map
    privileged uid/gids in the instance to unprivileged uid/gids in the host.
    In order to mount a directory from the host in an LXD instance, the host user's ids
    must be mapped before the instance is started.

    The instance needs to be stopped or restarted for the id map to take effect.

    :param instance: LXD instance to set the idmap of
    :param lxc: LXC client.
    :param project: LXD project to create instance in.
    :param remote: LXD remote to create instance on.
    :param uid: The uid to be mapped. If not supplied, the current user's uid is used.
    """
    if uid is None:
        uid = os.getuid()

    lxc.config_set(
        instance_name=instance.instance_name,
        key="raw.idmap",
        value=f"both {uid!s} 0",
        project=project,
        remote=remote,
    )


# pylint: disable-next=too-many-locals
def launch(
    name: str,
    *,
    base_configuration: Base,
    image_name: str,
    image_remote: str,
    auto_clean: bool = False,
    auto_create_project: bool = False,
    ephemeral: bool = False,
    map_user_uid: bool = False,
    uid: Optional[int] = None,
    use_snapshots: Optional[bool] = None,
    use_base_instance: bool = False,
    project: str = "default",
    remote: str = "local",
    lxc: LXC = LXC(),
    expiration: timedelta = timedelta(days=90),
) -> LXDInstance:
    """Create, start, and configure an instance.

    On the first run of an application, an instance will be launched from an image
    (i.e. an image from  https://cloud-images.ubuntu.com). The instance is setup
    according to the Base configuration passed to this function.

    After setup, a copy of this instance is saved (or cached) as a 'base instance'.
    This is done to reduce setup time on subsequent runs. When the application requests
    a new instance on a subsequent run, the base instance will be copied to create the
    new instance. This instance is run through a small subset of the setup, which is
    referred to as 'warmup'.

    To keep build environments clean, consistent, and up-to-date, any base instance
    older than 3 months (90 days) is deleted and recreated. This 90 day default can be
    changed with the `expiration` parameter.

    :param name: Name of instance.
    :param base_configuration: Base configuration to apply to the instance.
    :param image_name: LXD image to use, e.g. "20.04".
    :param image_remote: LXD image to use, e.g. "ubuntu".
    :param auto_clean: If true and the existing instance is incompatible, then the
    instance will be deleted and rebuilt. If false and the existing instance is
    incompatible, then a BaseCompatibilityError is raised.
    :param auto_create_project: Automatically create LXD project, if needed.
    :param ephemeral: After the instance is stopped, delete it. Non-ephemeral instances
    cannot be converted to ephemeral instances, so if the instance already exists, it
    will be deleted, then recreated as an ephemeral instance.
    :param map_user_uid: Map host uid/gid to instance's root uid/gid.
    :param uid: The uid to be mapped, if ``map_user_uid`` is enabled.
    :param use_base_instance: Use the base instance mechanisms to reduce setup time.
    :param use_snapshots: Deprecated parameter replaced by `use_base_instance`.
    :param project: LXD project to create instance in.
    :param remote: LXD remote to create instance on.
    :param lxc: LXC client.
    :param expiration: How long a base instance will be valid from its creation date.

    :returns: LXD instance.

    :raises BaseConfigurationError: on unexpected error configuration base.
    :raises BaseCompatibilityError: if instance is incompatible with the base.
    :raises LXDError: on unexpected LXD error.
    :raises ProviderError: if name of instance collides with base instance name.
    """
    # TODO: create a private class to reduce the parameters passed between methods

    if use_snapshots:
        logger.warning(
            "Deprecated: Parameter 'use_snapshots' is deprecated. "
            "Use parameter 'use_base_instance' instead."
        )
        use_base_instance = use_snapshots

    _ensure_project_exists(
        create=auto_create_project, project=project, remote=remote, lxc=lxc
    )
    instance = LXDInstance(
        name=name,
        project=project,
        remote=remote,
        default_command_environment=base_configuration.get_command_environment(),
    )
    logger.warning(
        "Checking for instance %r in project %r in remote %r",
        instance.instance_name,
        project,
        remote,
    )

    if instance.exists():
        # if the existing instance could not be launched, then continue on so a new
        # instance can be created (this can occur when `auto_clean` triggers the
        # instance to be deleted or if the instance is supposed to be ephemeral)
        if _launch_existing_instance(
            instance=instance,
            lxc=lxc,
            project=project,
            remote=remote,
            auto_clean=auto_clean,
            base_configuration=base_configuration,
            ephemeral=ephemeral,
            map_user_uid=map_user_uid,
            uid=uid,
        ):
            return instance

    logger.warning("Instance %r does not exist.", instance.instance_name)

    if not use_base_instance:
        logger.warning("Using base instances is disabled.")
        _create_instance(
            instance=instance,
            base_instance=None,
            base_configuration=base_configuration,
            image_name=image_name,
            image_remote=image_remote,
            ephemeral=ephemeral,
            map_user_uid=map_user_uid,
            uid=uid,
            project=project,
            remote=remote,
            lxc=lxc,
        )
        return instance

    base_instance_name = _formulate_base_instance_name(
        image_name=image_name,
        image_remote=image_remote,
        compatibility_tag=base_configuration.compatibility_tag,
    )
    base_instance = LXDInstance(
        name=base_instance_name,
        project=project,
        remote=remote,
        default_command_environment=base_configuration.get_command_environment(),
    )
    logger.warning(
        "Checking for base instance %r in project %r in remote %r",
        base_instance.instance_name,
        project,
        remote,
    )

    # an application could formulate an instance name that matches the base instance's
    # name, which would break calls to `lxc.copy()`
    if instance.instance_name == base_instance.instance_name:
        raise ProviderError(
            brief="instance name cannot match the base instance name: "
            f"{instance.instance_name!r}",
            resolution="change name of instance",
        )

    # the base instance does not exist, so create a new instance and base instance
    if not base_instance.exists():
        logger.warning("Base instance %r does not exist.", base_instance.instance_name)
        _create_instance(
            instance=instance,
            base_instance=base_instance,
            base_configuration=base_configuration,
            image_name=image_name,
            image_remote=image_remote,
            ephemeral=ephemeral,
            map_user_uid=map_user_uid,
            uid=uid,
            project=project,
            remote=remote,
            lxc=lxc,
        )
        return instance

    # the base instance exists but is not valid, so delete it then create a new
    # instance and base instance
    if not _is_valid(
        instance_name=base_instance.instance_name,
        project=project,
        remote=remote,
        lxc=lxc,
        expiration=expiration,
    ):
        logger.warning(
            "Base instance %r is not valid. Deleting base instance.",
            base_instance.instance_name,
        )
        base_instance.delete()
        _create_instance(
            instance=instance,
            base_instance=base_instance,
            base_configuration=base_configuration,
            image_name=image_name,
            image_remote=image_remote,
            ephemeral=ephemeral,
            map_user_uid=map_user_uid,
            uid=uid,
            project=project,
            remote=remote,
            lxc=lxc,
        )
        return instance

    # at this point, there is a valid base instance to be copied to a new instance
    logger.warning(
        "Creating instance from base instance %r", base_instance.instance_name
    )

    # the base instance is not expected to be running but check for safety
    if base_instance.is_running():
        logger.warning("Stopping base instance.")

    lxc.copy(
        source_remote=remote,
        source_instance_name=base_instance.instance_name,
        destination_remote=remote,
        destination_instance_name=instance.instance_name,
        project=project,
    )

    # the newly copied instance should not be running, but check anyways
    if instance.is_running():
        logger.warning("Instance is already running.")
        instance.stop()

    # set the id map while the instance is not running
    if map_user_uid:
        _set_id_map(instance=instance, lxc=lxc, project=project, remote=remote, uid=uid)

    # instance is now ready to be started and warmed up
    logger.warning("Starting instance.")
    instance.start()
    base_configuration.warmup(executor=instance)
    return instance
