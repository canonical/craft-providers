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

"""Multipass Provider."""

import logging

import packaging.version

from craft_providers import Base, bases
from craft_providers.multipass.errors import MultipassError
from craft_providers.multipass.multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


def launch(
    name: str,
    *,
    base_configuration: Base,
    image_name: str,
    cpus: int = 2,
    disk_gb: int = 64,
    mem_gb: int = 2,
    auto_clean: bool = False,
) -> MultipassInstance:
    """Create, start, and configure instance.

    If auto_clean is enabled, automatically delete an existing instance that is
    deemed to be incompatible, rebuilding it with the specified environment.

    :param name: Name of instance.
    :param base_configuration: Base configuration to apply to instance.
    :param image_name: Multipass image to use, e.g. snapcraft:core22.
    :param cpus: Number of CPUs.
    :param disk_gb: Disk allocation in gigabytes.
    :param mem_gb: Memory allocation in gigabytes.
    :param auto_clean: Automatically clean instance, if incompatible.

    :returns: Multipass instance.

    :raises BaseConfigurationError: on unexpected error configuration base.
    :raises MultipassError: on unexpected Multipass error.
    """
    instance = MultipassInstance(name=name)

    # TODO: drop this after 1.14.1 is released to latest/stable (#638)
    if base_configuration.alias == bases.ubuntu.BuilddBaseAlias.NOBLE:
        version, _ = instance._multipass.version()
        if packaging.version.parse(version) < packaging.version.Version("1.14.1"):
            raise MultipassError(
                brief=f"Multipass {version!r} does not support Ubuntu 24.04 (Noble).",
                resolution="Upgrade to Multipass 1.14.1 or newer.",
            )

    if instance.exists():
        # TODO: Warn if existing instance doesn't match cpu/disk/mem specs.
        instance.start()
        try:
            base_configuration.warmup(executor=instance)
        except bases.BaseCompatibilityError as error:
            if auto_clean:
                logger.debug(
                    "Cleaning incompatible instance %r (reason: %s).",
                    instance.name,
                    error.reason,
                )
                instance.delete()
            else:
                raise
        else:
            return instance

    instance.launch(
        cpus=cpus,
        disk_gb=disk_gb,
        mem_gb=mem_gb,
        image=image_name,
    )
    base_configuration.setup(executor=instance)
    return instance
