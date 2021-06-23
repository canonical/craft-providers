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

"""Project helper utilities."""
import logging

from .lxc import LXC

logger = logging.getLogger(__name__)


def create_with_default_profile(
    *,
    lxc: LXC,
    project: str,
    profile: str = "default",
    profile_project: str = "default",
    remote: str = "local",
) -> None:
    """Create a project with a valid default profile.

    LXD does not set a valid profile on newly created projects.  This will
    create a project and set the profile to match the specified profile,
    typically the default.

    :param project: Name of project to create.
    :param remote: Name of remote.
    :param profile_name: Name of profile to copy.

    :raises LXDError: on unexpected error.
    """
    lxc.project_create(project=project, remote=remote)

    # Retrieve config from specified (default) project profile.
    config = lxc.profile_show(profile=profile, project=profile_project, remote=remote)

    # Set config.
    lxc.profile_edit(profile="default", project=project, config=config, remote=remote)


def purge(*, lxc: LXC, project: str, remote: str = "local") -> None:
    """Purge a project including its instances and images.

    The lxc command does not provide a straight-forward option to purge a
    project.  This helper will purge anything related to a specified one.

    :param project: Name of project to delete.
    :param remote: Name of remote.

    :raises LXDError: on unexpected error.
    """
    logger.debug("Purging project %r on remote %r.", project, remote)
    projects = lxc.project_list(remote=remote)
    if project not in projects:
        logger.debug(
            "Attempted to purge non-existent project %r on remote %r.", project, remote
        )
        return

    # Cleanup any outstanding instance_names.
    for instance_name in lxc.list_names(project=project, remote=remote):
        logger.debug(
            "Deleting instance %r from project %r on remote %r.",
            instance_name,
            project,
            remote,
        )
        lxc.delete(
            instance_name=instance_name,
            project=project,
            remote=remote,
            force=True,
        )

    # Cleanup any outstanding images.
    for image in lxc.image_list(project=project):
        logger.debug(
            "Deleting image %r from project %r on remote %r.", image, project, remote
        )
        lxc.image_delete(image=image["fingerprint"], project=project, remote=remote)

    # Cleanup project.
    logger.debug("Deleting project %r on remote %r.", project, remote)
    lxc.project_delete(project=project, remote=remote)

    logger.debug("Project %r on remote %r was purged successfully.", project, remote)
