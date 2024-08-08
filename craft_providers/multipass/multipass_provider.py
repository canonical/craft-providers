# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2022-2023 Canonical Ltd.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Multipass Provider class."""

import contextlib
import logging
import pathlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator

from craft_providers import Base, Executor, Provider, base
from craft_providers.bases import ubuntu
from craft_providers.errors import BaseConfigurationError

from ._launch import launch
from ._ready import ensure_multipass_is_ready
from .errors import MultipassError
from .installer import install, is_installed
from .multipass import Multipass
from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


class Remote(Enum):
    """Enumeration of Multipass remotes.

    Multipass uses the name 'snapcraft' for the Ubuntu buildd remote at
    https://cloud-images.ubuntu.com/buildd/.
    """

    RELEASE = "release"
    DAILY = "daily"
    SNAPCRAFT = "snapcraft"


@dataclass
class RemoteImage:
    """Contains the name and details of a remote Multipass image.

    :param remote: Remote server that hosts the image.
    :param image_name: Name of the image on the remote.
    """

    remote: Remote
    image_name: str

    @property
    def is_stable(self) -> bool:
        """Check if the image is stable.

        Images are stable if they are from the snapcraft or release remotes.
        Devel images and images from daily remotes or any other remotes are not stable.

        :returns: True if the image is stable.
        """
        return (
            self.remote in (Remote.RELEASE, Remote.SNAPCRAFT)
            and "devel" not in self.image_name
        )

    @property
    def name(self) -> str:
        """Get the full name of a remote image.

        This name is used to launch an instance with `multipass launch <name>`.

        :returns: Full name of the remote image, formatted as `<remote>:<image_name>`.
        """
        return f"{self.remote.value}:{self.image_name}"


# mapping of Provider bases to Multipass remote images
_BUILD_BASE_TO_MULTIPASS_REMOTE_IMAGE: Dict[Enum, RemoteImage] = {
    ubuntu.BuilddBaseAlias.BIONIC: RemoteImage(
        remote=Remote.SNAPCRAFT, image_name="18.04"
    ),
    ubuntu.BuilddBaseAlias.FOCAL: RemoteImage(
        remote=Remote.SNAPCRAFT, image_name="20.04"
    ),
    ubuntu.BuilddBaseAlias.JAMMY: RemoteImage(
        remote=Remote.SNAPCRAFT, image_name="22.04"
    ),
    ubuntu.BuilddBaseAlias.NOBLE: RemoteImage(
        remote=Remote.SNAPCRAFT, image_name="24.04"
    ),
    ubuntu.BuilddBaseAlias.ORACULAR: RemoteImage(
        remote=Remote.DAILY, image_name="oracular"
    ),
    # devel images are not available on macos
    ubuntu.BuilddBaseAlias.DEVEL: RemoteImage(
        remote=Remote.SNAPCRAFT, image_name="devel"
    ),
}


def _get_remote_image(provider_base: Base) -> RemoteImage:
    """Get a RemoteImage for a particular provider base.

    :param provider_base: String containing the provider base.

    :returns: The RemoteImage for the provider base.

    :raises MultipassError: If the remote image does not exist.
    """
    image = _BUILD_BASE_TO_MULTIPASS_REMOTE_IMAGE.get(provider_base.alias)
    if not image:
        raise MultipassError(
            brief=(
                "could not find a multipass remote image for the provider base "
                f"{provider_base!r}"
            )
        )

    return image


class MultipassProvider(Provider):
    """Multipass build environment provider.

    This class is not stable and is likely to change. This class will be stable and
    recommended for use in the release of craft-providers 2.0.

    :param multipass: Optional Multipass client to use.
    """

    def __init__(self, instance: Multipass = Multipass()) -> None:
        self.multipass = instance

    @property
    def name(self) -> str:
        """Name of the provider."""
        return "Multipass"

    @property
    def install_recommendation(self) -> str:
        """Recommended way to install the provider."""
        return (
            "Visit https://multipass.run/install for instructions to install Multipass."
        )

    @classmethod
    def ensure_provider_is_available(cls) -> None:
        """Ensure provider is available, prompting the user to install it if required.

        :raises MultipassError: if provider is not available.
        """
        if not is_installed():
            install()
        ensure_multipass_is_ready()

    def create_environment(self, *, instance_name: str) -> Executor:
        """Create a bare environment for specified base.

        No initializing, launching, or cleaning up of the environment occurs.

        :param name: Name of the instance.
        """
        return MultipassInstance(name=instance_name)

    @classmethod
    def is_provider_installed(cls) -> bool:
        """Check if provider is installed.

        :returns: True if installed.
        """
        return is_installed()

    @contextlib.contextmanager
    def launched_environment(
        self,
        *,
        project_name: str,
        project_path: pathlib.Path,
        base_configuration: base.Base,
        instance_name: str,
        allow_unstable: bool = False,
    ) -> Iterator[Executor]:
        """Configure and launch environment for specified base.

        When this method loses context, all directories are unmounted and the
        environment is stopped. For more control of environment setup and teardown,
        use `create_environment()` instead.

        :param project_name: Name of the project.
        :param project_path: Path to project.
        :param base_configuration: Base configuration to apply to instance.
        :param instance_name: Name of the instance to launch.
        :param allow_unstable: If true, allow unstable images to be launched.

        :raises MultipassError: If the instance cannot be launched or configured.
        """
        image = _get_remote_image(base_configuration)

        # only allow launching unstable images when opted-in with `allow_unstable`
        if not image.is_stable and not allow_unstable:
            raise MultipassError(
                brief=f"Cannot launch unstable image {image.name!r}.",
                details=(
                    "Devel or daily images are not guaranteed and are intended for "
                    "experimental use only."
                ),
                resolution=(
                    "Set parameter `allow_unstable` to True to launch unstable images."
                ),
            )
        try:
            instance = launch(
                name=instance_name,
                base_configuration=base_configuration,
                image_name=image.name,
                cpus=2,
                disk_gb=64,
                mem_gb=2,
                auto_clean=True,
            )
        except BaseConfigurationError as error:
            raise MultipassError(str(error)) from error

        try:
            yield instance
        finally:
            # Ensure to unmount everything and stop instance upon completion.
            instance.unmount_all()
            instance.stop()
