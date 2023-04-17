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

"""Base configuration module."""

import enum
import logging
import os
import subprocess
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional

from craft_providers.errors import BaseConfigurationError, NetworkError

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

    :cvar compatibility_tag: Tag/Version for variant of build configuration and
        setup.  Any change to this version would indicate that prior [versioned]
        instances are incompatible and must be cleaned.  As such, any new value
        should be unique to old values (e.g. incrementing).  It is suggested to
        extend this tag, not overwrite it, e.g.: compatibility_tag =
        f"{appname}-{Base.compatibility_tag}.{apprevision}" to ensure base
        compatibility levels are maintained.
    """

    compatibility_tag: str = "base-v1"
    alias: Enum

    @abstractmethod
    def __init__(
        self,
        *,
        alias: enum.Enum,
        compatibility_tag: Optional[str] = None,
        environment: Optional[Dict[str, Optional[str]]] = None,
        hostname: str = "craft-instance",
        snaps: Optional[List] = None,
        packages: Optional[List[str]] = None,
    ):
        pass

    @abstractmethod
    def get_command_environment(
        self,
    ) -> Dict[str, Optional[str]]:
        """Get command environment to use when executing commands.

        :returns: Dictionary of environment, allowing None as a value to
                  indicate that a value should be unset.
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

        Setup should not be called more than once in a given instance to
        refresh/update the environment, use `warmup` for that.

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if
            required).
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """

    @abstractmethod
    def warmup(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Prepare a previously created and setup instance for use by the application.

        Ensure the instance is still valid and wait for environment to become ready.

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if required).
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
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

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """

    @classmethod
    def _check_deadline(
        cls,
        deadline: Optional[float],
        *,
        message: str = "Timed out configuring environment.",
    ) -> None:
        """Check deadline and raise error if passed.

        :param deadline: Optional time.time() deadline.

        :raises BaseConfigurationError: if deadline is passed.
        """
        if deadline is not None and time.time() >= deadline:
            raise BaseConfigurationError(brief=message)

    @classmethod
    def _network_connected(cls, executor):
        """Check if the network is connected."""
        # bypass the network verification if there is a proxy set for HTTPS
        # (because we're hitting port 443), as bash's TCP functionality will not
        # use it (supporting both lowercase and uppercase names, which is what
        # most applications do)
        if os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"):
            return True

        # check if the port is open using bash's built-in tcp-client, communicating with
        # the HTTPS port on our site
        command = ["bash", "-c", "exec 3<> /dev/tcp/snapcraft.io/443"]
        try:
            # timeout quickly, so it's representative of current state (we don't
            # want for it to hang a lot and then succeed 45 seconds later if network
            # came back); capture the output just for it to not pollute the terminal
            proc = executor.execute_run(
                command, check=False, timeout=1, capture_output=True
            )
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0

    @classmethod
    def _execute_run(
        cls,
        executor: Executor,
        command: List[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        text: bool = False,
        verify_network=False,
    ) -> subprocess.CompletedProcess:
        """Run a command through the executor.

        This is a helper to simplify most common calls and provide extra network
        verification (if indicated) in a central place.

        The default of capture_output is True because it's useful for error reports
        (if the command failed) even if the output is not really wanted as a result
        of the execution.
        """
        if not check and verify_network:
            # if check is False, the caller needs the process result no matter
            # what, it's wrong to also request to verify network, which may
            # raise a different exception
            raise RuntimeError("Invalid check and verify_network combination.")

        try:
            proc = executor.execute_run(
                command, check=check, capture_output=capture_output, text=text
            )
        except subprocess.CalledProcessError as exc:
            if verify_network and not cls._network_connected(executor):
                raise NetworkError() from exc
            raise
        return proc
