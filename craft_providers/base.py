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

"""Base configuration module."""
import logging
from abc import ABC, abstractmethod
from typing import Optional

from .executor import Executor

logger = logging.getLogger(__name__)


class Base(ABC):
    """Base definition for bootstrap configuration and setup.

    :param name: Name of base.
    """

    def __init__(self, *, name: str) -> None:
        self.name = name

    @abstractmethod
    def setup(self, *, executor: Executor) -> None:
        """Configure instance as necessary.

        Wait for environment to become ready and configure it.  Environment will
        be ready upon completion of setup().

        :raises ProviderError: on unexpected error.
        """

    @abstractmethod
    def wait_until_ready(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Wait until system is ready.

        Ensure minimum-required boot services are running.  Typically used when
        brining up an environment and not wanting to run setup(), because it is
        known that setup() is already complete (e.g. rebooting instance).

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks.
        :param timeout: Optional time.time() stamp to timeout after.
        """
