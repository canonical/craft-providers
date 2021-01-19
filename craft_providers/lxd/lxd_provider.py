# Copyright (C) 2021 Canonical Ltd
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

"""LXD Provider."""
import logging
from typing import Optional

from .. import images
from . import lxd_installer
from .lxc import LXC
from .lxd_instance import LXDInstance

logger = logging.getLogger(__name__)


def _get_snapshot_image_name(*, remote: str, compatibility_tag: str) -> str:
    return "-".join(
        [
            remote,
            f"r{compatibility_tag}",
        ]
    )


class LXDProviderError(Exception):
    """LXD Provider Error.

    :param reason: Reason for error.
    """

    def __init__(self, reason: str) -> None:
        super().__init__()

        self.reason = reason

    def __str__(self) -> str:
        return f"LXD provider encountered an error: {self.reason}"


class LXDProvider:
    """LXD Provider.

    :param lxc: Optional LXC client.
    """

    def __init__(self, *, lxc: Optional[LXC] = None) -> None:
        self._lxc = lxc

    def _configure_instance(
        self,
        *,
        instance: LXDInstance,
        auto_clean: bool,
        image_configuration: images.Image,
    ) -> None:
        if not instance.is_running():
            instance.start()

        try:
            image_configuration.setup(executor=instance)
        except images.CompatibilityError as error:
            if auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    instance.name,
                    error.reason,
                )
                instance.delete(force=True)
                return
            raise error

        image_configuration.wait_until_ready(executor=instance)

    def create_image_remote(self, *, name: str, addr: str, protocol: str) -> None:
        """Add a public remote.

        :param name: Name of remote.
        :param addr: Address of remote.
        :param protocol: Protocol to use, e.g. simplestreams.
        """
        lxc = self._get_lxc()
        lxc.remote_add(
            remote=name,
            addr=addr,
            protocol=protocol,
        )

    def create_instance(
        self,
        *,
        auto_clean: bool,
        image_configuration: images.Image,
        image_name: str,
        image_remote: str,
        name: str,
        project: str,
        remote: str,
        ephemeral: bool = False,
        use_snapshots: bool = True,
    ) -> LXDInstance:
        """Create, start, and configure instance as necessary.

        :param auto_clean: Automatically clean LXD instances if required (e.g.
            incompatible).
        :param image_configuration: Image configuration.
        :param image_name: Name of image to use, e.g. "20.04"
        :param image_remote: Name of image remote, e.g. "ubuntu".
        :param name: Name of instance to use/create.
        :param project: Name of LXD project.
        :param remote: Name of LXD remote for instance to run on.
        :param ephemeral: Create ephemeral instance (cleaned on shutdown).
        :param use_snapshots: Create intermediate instances to speedup setup of
            future instances.

        :returns: LXD instance.

        :raises IncompatibleInstanceError: If incompatible and clean is
            disabled.
        """
        lxc = self._get_lxc()
        instance = LXDInstance(
            name=name,
            lxc=lxc,
            project=project,
            remote=remote,
        )
        snapshot_name = _get_snapshot_image_name(
            remote=remote, compatibility_tag=image_configuration.compatibility_tag
        )

        if instance.exists():
            self._configure_instance(
                instance=instance,
                auto_clean=auto_clean,
                image_configuration=image_configuration,
            )

        # Re-check if instance exists as it may been cleaned.
        # If it doesn't exist, launch a fresh instance.
        if not instance.exists():
            # Create from snapshot, if available.
            if self._has_compatible_snapshot(
                snapshot_name=snapshot_name, project=project, remote=remote
            ):
                logger.info("Using compatible snapshot {snapshot_name!r}.")
                image_name = snapshot_name

            instance.launch(
                image=image_name,
                image_remote=image_remote,
                ephemeral=ephemeral,
            )

            self._configure_instance(
                instance=instance,
                auto_clean=False,
                image_configuration=image_configuration,
            )

            # Publish snapshot if not ephemeral (snapshotting may fail on ephemeral).
            if use_snapshots and not ephemeral:
                self._publish_snapshot(
                    snapshot_name=snapshot_name,
                    instance=instance,
                    image_configuration=image_configuration,
                )

        return instance

    def _delete_snapshot(
        self,
        *,
        snapshot_name: str,
        project: str,
        remote: str,
    ) -> None:
        self._get_lxc().image_delete(
            image=snapshot_name,
            project=project,
            remote=remote,
        )

    def _publish_snapshot(
        self,
        *,
        snapshot_name: str,
        instance: LXDInstance,
        image_configuration: images.Image,
    ) -> None:
        instance.stop()

        self._get_lxc().publish(
            alias=snapshot_name,
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
            force=True,
        )

        # Restart container and ensure it is ready.
        instance.start()
        image_configuration.wait_until_ready(executor=instance)

    def create_project(self, *, name: str, remote: str) -> None:
        """Create lxd project if it does not exist.

        :param name: Name of project.
        :param remote_name: Name of remote to create project on.
        """
        lxc = self._get_lxc()
        projects = lxc.project_list(remote=remote)
        if name in projects:
            return

        lxc.project_create(project=name, remote=remote)

    def _get_lxc(self) -> LXC:
        """Get lxc client API.

        :raises LXDProviderError: if lxc not found.
        """
        if self._lxc is not None:
            return self._lxc

        lxc_path = lxd_installer.find_lxc()
        if lxc_path is None:
            raise LXDProviderError("unable to find 'lxc' in PATH")

        self._lxc = LXC(lxc_path=lxc_path)
        return self._lxc

    def install(self) -> None:
        """Install LXD."""
        lxd_installer.install()

    def is_image_remote_installed(self, *, name: str) -> bool:
        """Check if image remote is installed.

        :param name: Name of remote.
        """
        lxc = self._get_lxc()
        remotes = lxc.remote_list()
        remote = remotes.get(name)

        return remote is not None

    def is_installed(self) -> bool:
        """Check if LXD is installed."""
        return lxd_installer.is_installed()

    def _has_compatible_snapshot(
        self, *, snapshot_name: str, project: str, remote: str
    ) -> bool:
        lxc = self._get_lxc()
        image_list = lxc.image_list(project=project, remote=remote)

        for image in image_list:
            for alias in image["aliases"]:
                if snapshot_name == alias["name"]:
                    return True

        return False
