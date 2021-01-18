# Copyright (C) 2020 Canonical Ltd
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

"""Image module."""
import logging
from abc import ABC, abstractmethod
from typing import Final

from .executor import Executor

logger = logging.getLogger(__name__)


class Image(ABC):  # pylint: disable=too-few-public-methods
    """Image definition for configuration/setup.

    Images encapsulate the logic required to setup a base image upon initial
    launch and restarting.  By extending this class, an application may include
    its own additional setup/update requirements.

    :param name: Name of image.
    :param compatibility_tag: Version of image setup used to ensure
        compatibility for re-used instances.  Any change to this version would
        indicate that prior [versioned] instances are incompatible and must be
        cleaned.  As such, any new value should be unique to old values (e.g.
        incrementing).
    """

    def __init__(self, *, name: str, compatibility_tag: str) -> None:
        self.name: Final[str] = name
        self.compatibility_tag: Final[str] = compatibility_tag

    @abstractmethod
    def setup(self, *, executor: Executor) -> None:
        """Create, start, and configure instance as necessary.

        :raises CompatibilityError: if executor instance is incompatible with image.
        """
        ...
