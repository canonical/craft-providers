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

"""Multipass Provider."""

import logging

from craft_providers import Base

from .multipass_instance import MultipassInstance

logger = logging.getLogger(__name__)


def launch(
    name: str,
    *,
    base_configuration: Base,
    cpus: int = 2,
    disk_gb: int = 256,
    image_name: str,
    mem_gb: int = 2,
) -> MultipassInstance:
    """Create, start, and configure instance.

    :param name: Name of instance.
    :param base_configuration: Base configuration to apply to instance.
    :param cpus: Number of CPUs.
    :param disk_gb: Disk allocation in gigabytes.
    :param image_name: Multipass image to use, e.g. snapcraft:core20.
    :param mem_gb: Memory allocation in gigabytes.

    :returns: Multipass instance.

    :raises BaseConfigurationError: on unexpected error configuration base.
    :raises MultipassError: on unexpected Multipass error.
    """
    instance = MultipassInstance(name=name)

    if instance.exists():
        instance.start()
    else:
        instance.launch(
            cpus=cpus,
            disk_gb=disk_gb,
            mem_gb=mem_gb,
            image=image_name,
        )

    base_configuration.setup(executor=instance)
    return instance
