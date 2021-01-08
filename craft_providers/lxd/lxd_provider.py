"""LXD Provider."""
import logging
from typing import Optional

from .. import images
from ..provider import Provider
from .lxc import LXC
from .lxd import LXD
from .lxd_instance import LXDInstance

logger = logging.getLogger(__name__)


class LXDProvider(Provider):
    """LXD Provider.

    :param image: Image configuration.
    :param instance_name: Name of instance to use/create.
    :param auto_clean: Automatically clean LXD instances if required (e.g.
        incompatible).
    :param image_remote_addr: Remote address for LXD image to use.
    :param image_remote_name: Remote name for LXD image to use.
    :param image_remote_protocol: Remote protoocl for LXD image to use.
    :param instance: Specific LXDInstance to use, rather than create.
    :param lxc: LXC client API.
    :param lxd: LXD server API.
    :param project: Name of LXD project.
    :param remote: Name of LXD remote for instance to run on.
    :param use_ephemeral_instances: Set instances to be ephemeral (clean on
        shutdown).
    :param use_intermediate_instances: Create intermediate instances to speedup
        setup of future instances.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        *,
        image: images.Image,
        instance_name: str,
        auto_clean: bool = True,
        image_remote_addr: str = "https://cloud-images.ubuntu.com/buildd/releases",
        image_remote_name: str = "ubuntu-buildd",
        image_remote_protocol: str = "simplestreams",
        instance: Optional[LXDInstance] = None,
        lxc: Optional[LXC] = None,
        lxd: Optional[LXD] = None,
        project: str = "default",
        remote: str = "local",
        use_ephemeral_instances: bool = True,
        use_intermediate_image: bool = True,
    ):
        super().__init__()

        self.image = image
        self.instance_name = instance_name

        self.image_remote_addr = image_remote_addr
        self.image_remote_name = image_remote_name
        self.image_remote_protocol = image_remote_protocol
        self.instance = instance
        self.auto_clean = auto_clean

        if lxc is None:
            self.lxc = LXC()
        else:
            self.lxc = lxc

        if lxd is None:
            self.lxd = LXD()
        else:
            self.lxd = lxd

        self.project = project
        self.remote = remote
        self.use_ephemeral_instances = use_ephemeral_instances
        self.use_intermediate_image = use_intermediate_image

    def setup(self) -> LXDInstance:
        """Sets up instance, creating intermediate image as configured.

        :returns: LXD instance.

        :raises IncompatibleInstanceError: If incompatible and clean is disabled.
        """
        self.lxd.setup()
        self.lxc.setup()

        self._setup_image_remote()

        if self.use_intermediate_image:
            intermediate_image = self._setup_intermediate_image()
            self.instance = self._setup_instance(
                instance=self.instance_name,
                image=intermediate_image,
                image_remote=self.remote,
                ephemeral=self.use_ephemeral_instances,
            )
        else:
            self.instance = self._setup_instance(
                instance=self.instance_name,
                image=self.image.name,
                image_remote=self.image_remote_name,
                ephemeral=self.use_ephemeral_instances,
            )

        return self.instance

    def _setup_image_remote(self) -> None:
        """Add a public remote."""
        remotes = self.lxc.remote_list()
        remote = remotes.get(self.image_remote_name)

        # Ensure remote configuration matches.
        if remote is not None:
            if (
                remote.get("addr") != self.image_remote_addr
                and remote.get("protocol") != self.image_remote_protocol
            ):
                raise RuntimeError(
                    f"Remote configuration does not match for {self.remote!r}."
                )
            return

        self.lxc.remote_add(
            remote=self.image_remote_name,
            addr=self.image_remote_addr,
            protocol=self.image_remote_protocol,
        )

    def _setup_existing_instance(self, *, lxd_instance: LXDInstance) -> None:
        try:
            self.image.setup(executor=lxd_instance)
        except images.CompatibilityError as error:
            if self.auto_clean:
                logger.warning(
                    "Cleaning incompatible instance '%s' (%s).",
                    lxd_instance.name,
                    error.reason,
                )
                lxd_instance.delete(force=True)
            else:
                raise error

    def _setup_instance(
        self,
        *,
        instance: str,
        image: str,
        image_remote: str,
        ephemeral: bool,
    ) -> LXDInstance:
        lxd_instance = LXDInstance(
            name=instance,
            project=self.project,
            remote=self.remote,
            lxc=self.lxc,
        )

        # If instance already exists, special case it
        # to ensure the instance is cleaned if incompatible.
        if lxd_instance.exists():
            self._setup_existing_instance(lxd_instance=lxd_instance)

        if not lxd_instance.exists():
            lxd_instance.launch(
                image=image,
                image_remote=image_remote,
                ephemeral=ephemeral,
            )

        return lxd_instance

    def _setup_intermediate_image(self) -> str:
        intermediate_name = "-".join(
            [
                self.image_remote_name,
                f"r{self.image.compatibility_tag}",
            ]
        )

        image_list = self.lxc.image_list(project=self.project, remote=self.remote)
        for image in image_list:
            for alias in image["aliases"]:
                if intermediate_name == alias["name"]:
                    logger.info("Using intermediate image.")
                    return intermediate_name

        # Intermediate instances cannot be ephemeral. Publishing may fail.
        intermediate_instance = self._setup_instance(
            instance=intermediate_name,
            image=self.image.name,
            image_remote=self.image_remote_name,
            ephemeral=False,
        )

        # Publish intermediate image.
        self.lxc.publish(
            alias=intermediate_name,
            instance=intermediate_name,
            project=self.project,
            remote=self.remote,
            force=True,
        )

        # Nuke it.
        intermediate_instance.delete(force=True)
        return intermediate_name

    def _setup_project(self) -> None:
        projects = self.lxc.project_list(remote=self.remote)
        if self.project in projects:
            return

    def teardown(self, *, clean: bool = False) -> None:
        if self.instance is None:
            return

        if not self.instance.exists():
            return

        if self.instance.is_running():
            self.instance.stop()

        if clean:
            self.instance.delete(force=True)
