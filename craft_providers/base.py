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
    """Interface for providers to configure instantiated environments.

    Defines how to setup/configure an environment that has been instantiated by
    a provider and prepare it for some operation, e.g. execute build.  It must
    account for:

    (1) the OS type and version.

    (2) the provided image that was launched, e.g. bootstrapping a minimal image
    versus a more fully featured one.

    (3) any dependencies that are required for the operation to complete, e.g.
    installed applications, networking configuration, etc.  This includes any
    environment configuration that the application will assume is available.
    """

    @abstractmethod
    def setup(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Prepare base instance for use by the application.

        Wait for environment to become ready and configure it.  At completion of
        setup, the executor environment should have networking up and have all
        of the installed dependencies required for subsequent use by the
        application.

        Setup may be called more than once in a given instance to refresh/update
        the environment.

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if
            required).
        :param timeout: Timeout in seconds.

        :raises ProviderError: on timeout or unexpected error.
        """

    @abstractmethod
    def wait_until_ready(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Wait until base instance is ready.

        Ensure minimum-required boot services are running.  This would be used
        when starting an environment's container/VM after already [recently]
        running setup(), e.g. rebooting the instance.  Allows the environment to
        be used without the cost incurred by re-executing the steps
        unnecessarily.

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if
            required).
        :param timeout: Timeout in seconds.

        :raises ProviderError: on timeout or unexpected error.
        """
