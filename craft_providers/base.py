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

# pylint: disable=too-many-lines

import enum
import io
import logging
import os
import pathlib
import re
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from textwrap import dedent
from time import sleep
from typing import Dict, List, Optional, Type, final

from pydantic import ValidationError

from craft_providers.actions import snap_installer
from craft_providers.actions.snap_installer import Snap, SnapInstallationError
from craft_providers.const import (
    RETRY_WAIT,
    TIMEOUT_COMPLEX,
    TIMEOUT_SIMPLE,
    TIMEOUT_UNPREDICTABLE,
)
from craft_providers.errors import (
    BaseCompatibilityError,
    BaseConfigurationError,
    NetworkError,
    details_from_called_process_error,
)
from craft_providers.executor import Executor
from craft_providers.instance_config import InstanceConfiguration
from craft_providers.util.os_release import parse_os_release

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

    alias: Enum
    compatibility_tag: str = "base-v1"
    environment: Dict[str, Optional[str]]
    executor: Executor
    hostname: str
    instance_config_path: pathlib.Path = pathlib.Path("/etc/craft-instance.conf")
    instance_config_class: Type[InstanceConfiguration] = InstanceConfiguration
    snaps: Optional[List[Snap]] = None
    packages: Optional[List[str]] = None
    retry_wait: float = RETRY_WAIT
    timeout_simple: Optional[float] = TIMEOUT_SIMPLE
    timeout_complex: Optional[float] = TIMEOUT_COMPLEX
    timeout_unpredictable: Optional[float] = TIMEOUT_UNPREDICTABLE

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

    @staticmethod
    def default_command_environment() -> Dict[str, Optional[str]]:
        """Provide default command environment dictionary.

        The minimum environment for the image to be configured and function
        properly.  This contains the default environment for most Linux systems
        in /etc/environment.

        :returns: Dictionary of environment key/values.
        """
        return {
            "PATH": "/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
        }

    def _set_hostname(self, hostname: str) -> None:
        """Set hostname.

        hostname naming convention:
        - between 1 and 63 characters long
        - be made up exclusively of letters, numbers, and hyphens from the ASCII table
        - not begin or end with a hyphen

        If needed, the provided hostname will be trimmed to meet naming conventions.

        :param hostname: hostname to set
        :raises BaseConfigurationError: if the hostname contains no
          alphanumeric characters
        """
        # truncate to 63 characters
        truncated_name = hostname[:63]

        # remove anything that is not an alphanumeric character or hyphen
        name_with_valid_chars = re.sub(r"[^\w-]", "", truncated_name)

        # trim hyphens from the beginning and end
        valid_name = name_with_valid_chars.strip("-")
        if not valid_name:
            raise BaseConfigurationError(
                brief=f"failed to create base with hostname {hostname!r}.",
                details="hostname must contain at least one alphanumeric character",
            )

        logger.debug("Using hostname %r", valid_name)
        self.hostname = valid_name

    def _ensure_instance_config_compatible(self) -> None:
        """Ensure instance configuration is compatible.

        As long as the config is not incompatible (via a mismatched compatibility tag),
        then assume the instance is compatible. This assumption is done because the
        config file may not exist or contain a tag while the set up is in progress.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        try:
            config = InstanceConfiguration.load(
                executor=self.executor,
                config_path=self.instance_config_path,
            )
        except ValidationError as error:
            raise BaseConfigurationError(
                brief="Failed to parse instance configuration file.",
            ) from error
        # if no config exists, assume base is compatible (likely unfinished setup)
        except FileNotFoundError:
            return

        # make the same assumption as above for empty configs or configs without a tag
        if config is None or config.compatibility_tag is None:
            return

        if config.compatibility_tag != self.compatibility_tag:
            raise BaseCompatibilityError(
                reason=(
                    "Expected image compatibility tag "
                    f"{self.compatibility_tag!r}, found {config.compatibility_tag!r}"
                )
            )
        logger.debug(
            "Instance is compatible with compatibility tag %r", config.compatibility_tag
        )

    def _ensure_setup_completed(self) -> None:
        """Ensure the instance was fully setup.

        The last step of setting up an instance is to set the `setup` key in the
        instance config file to True. This flag is used to verify that setup was
        completed for the instance.

        :raises BaseCompatibilityError: If setup was not completed.
        """
        try:
            config = InstanceConfiguration.load(
                executor=self.executor,
                config_path=self.instance_config_path,
            )
        except ValidationError as error:
            raise BaseCompatibilityError(
                reason="failed to parse instance configuration file",
            ) from error
        except FileNotFoundError as error:
            raise BaseCompatibilityError(
                reason="failed to find instance config file",
            ) from error

        if config is None:
            raise BaseCompatibilityError(reason="instance config is empty")

        if not config.setup:
            raise BaseCompatibilityError(reason="instance is marked as not setup")

        logger.debug("Instance has already been setup.")

    def _get_os_release(self) -> Dict[str, str]:
        """Get the OS release information from an instance's /etc/os-release.

        :returns: Dictionary of key-mappings found in os-release.
        """
        try:
            # Replace encoding errors if it somehow occurs with utf-8. This
            # doesn't need to be perfect for checking compatibility.
            proc = self.executor.execute_run(
                command=["cat", "/etc/os-release"],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to read /etc/os-release.",
                details=details_from_called_process_error(error),
            ) from error

        return parse_os_release(proc.stdout)

    @abstractmethod
    def _ensure_os_compatible(self) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """

    def get_command_environment(
        self,
    ) -> Dict[str, Optional[str]]:
        """Get command environment to use when executing commands.

        :returns: Dictionary of environment, allowing None as a value to
                  indicate that a value should be unset.
        """
        return self.environment.copy()

    def _update_setup_status(self, status: bool) -> None:
        """Update the instance config to indicate the status of the setup.

        :param status: True if the setup is complete, False otherwise.
        """
        InstanceConfiguration.update(
            executor=self.executor,
            data={"setup": status},
            config_path=self.instance_config_path,
        )

    def _update_compatibility_tag(self) -> None:
        """Update the compatibility_tag in the instance config."""
        InstanceConfiguration.update(
            executor=self.executor,
            data={"compatibility_tag": self.compatibility_tag},
            config_path=self.instance_config_path,
        )

    def _setup_environment(self) -> None:
        """Configure /etc/environment.

        If environment is None, reset /etc/environment to the default.
        """
        content = (
            "\n".join(
                [f"{k}={v}" for k, v in self.environment.items() if v is not None]
            )
            + "\n"
        ).encode()

        self.executor.push_file_io(
            destination=pathlib.Path("/etc/environment"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    def _setup_wait_for_system_ready(self) -> None:
        """Wait until system is ready."""
        logger.debug("Waiting for environment to be ready...")
        start_time = time.time()

        while True:
            proc = self._execute_run(
                ["systemctl", "is-system-running"],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_simple,
            )

            running_state = proc.stdout.strip()
            if running_state in ["running", "degraded"]:
                return

            logger.debug("systemctl is-system-running status: %s", running_state)

            if self.timeout_simple and self.timeout_simple > 0:
                if time.time() - start_time > self.timeout_simple:
                    raise BaseConfigurationError(
                        brief="Timed out waiting for environment to be ready.",
                    )

            sleep(self.retry_wait)

    def _setup_hostname(self) -> None:
        """Configure hostname, installing /etc/hostname."""
        self.executor.push_file_io(
            destination=pathlib.Path("/etc/hostname"),
            content=io.BytesIO((self.hostname + "\n").encode()),
            file_mode="0644",
        )

        try:
            self._execute_run(
                ["hostname", "-F", "/etc/hostname"], timeout=self.timeout_simple
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set hostname.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_networkd(self) -> None:
        """Configure networkd and start it.

        Installs eth0 network configuration using ipv4.
        """
        self.executor.push_file_io(
            destination=pathlib.Path("/etc/systemd/network/10-eth0.network"),
            content=io.BytesIO(
                dedent(
                    """\
                [Match]
                Name=eth0

                [Network]
                DHCP=ipv4
                LinkLocalAddressing=ipv6

                [DHCP]
                RouteMetric=100
                UseMTU=true
                """
                ).encode()
            ),
            file_mode="0644",
        )

        try:
            self._execute_run(
                ["systemctl", "enable", "systemd-networkd"], timeout=self.timeout_simple
            )
            self._execute_run(
                ["systemctl", "restart", "systemd-networkd"],
                timeout=self.timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-networkd.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_resolved(self) -> None:
        """Configure system-resolved to manage resolve.conf."""
        try:
            command = [
                "ln",
                "-sf",
                "/run/systemd/resolve/resolv.conf",
                "/etc/resolv.conf",
            ]
            self._execute_run(command, timeout=self.timeout_simple)

            self._execute_run(
                ["systemctl", "enable", "systemd-resolved"], timeout=self.timeout_simple
            )

            self._execute_run(
                ["systemctl", "restart", "systemd-resolved"],
                timeout=self.timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-resolved.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_wait_for_network(self) -> None:
        """Wait until networking is ready."""
        logger.debug("Waiting for networking to be ready...")
        start_time = time.time()

        command = ["getent", "hosts", "snapcraft.io"]
        while True:
            proc = self._execute_run(command, check=False, timeout=10)
            if proc.returncode == 0:
                return

            if self.timeout_simple and self.timeout_simple > 0:
                if time.time() - start_time > self.timeout_simple:
                    raise BaseConfigurationError(
                        brief="Timed out waiting for networking to be ready.",
                    )

            sleep(self.retry_wait)

    def _enable_udevd_service(self) -> None:
        """Enable and start udevd service."""
        try:
            proc = self._execute_run(
                ["systemctl", "is-active", "systemd-udevd"],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_simple,
            )

            state = proc.stdout.strip()
            if state == "active":
                return

            # systemd-udevd is not active, enable and start it
            self._execute_run(
                ["systemctl", "enable", "systemd-udevd"],
                timeout=TIMEOUT_SIMPLE,
            )
            self._execute_run(
                ["systemctl", "start", "systemd-udevd"],
                timeout=TIMEOUT_SIMPLE,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to enable systemd-udevd service.",
                details=details_from_called_process_error(error),
            ) from error

    def _disable_snapd_cdn(self) -> None:
        """Disable snapd CDN access if necessary."""
        try:
            # This file is created by launchpad-buildd to stop snapd from
            # using the snap store's CDN when running in Canonical's
            # production build farm, since internet access restrictions may
            # prevent it from doing so but will allow the non-CDN storage
            # endpoint.  If this is in place, then we need to propagate it
            # to containers we create.
            no_cdn = pathlib.Path("/etc/systemd/system/snapd.service.d/no-cdn.conf")
            if no_cdn.exists():
                self._execute_run(
                    ["mkdir", "-p", no_cdn.parent.as_posix()],
                    timeout=TIMEOUT_SIMPLE,
                )

                self.executor.push_file(source=no_cdn, destination=no_cdn)
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to disable snapd CDN.",
                details=details_from_called_process_error(error),
            ) from error

    def _enable_snapd_service(self) -> None:
        """Create the symlink to /snap and enable the snapd service."""
        try:
            self._execute_run(
                ["ln", "-sf", "/var/lib/snapd/snap", "/snap"],
                timeout=TIMEOUT_SIMPLE,
            )

            self._execute_run(
                ["systemctl", "enable", "--now", "snapd.socket"],
                timeout=TIMEOUT_SIMPLE,
            )

            # Restart, not start, the service in case the environment
            # has changed and the service is already running.
            self._execute_run(
                ["systemctl", "restart", "snapd.service"],
                timeout=TIMEOUT_SIMPLE,
            )
            self._execute_run(
                ["snap", "wait", "system", "seed.loaded"],
                timeout=TIMEOUT_SIMPLE,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to enable snapd service.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_snapd_proxy(self) -> None:
        """Configure the snapd proxy."""
        try:
            http_proxy = self.environment.get("http_proxy")
            if http_proxy:
                command = ["snap", "set", "system", f"proxy.http={http_proxy}"]
            else:
                command = ["snap", "unset", "system", "proxy.http"]
            self._execute_run(command, timeout=self.timeout_simple)

            https_proxy = self.environment.get("https_proxy")
            if https_proxy:
                command = ["snap", "set", "system", f"proxy.https={https_proxy}"]
            else:
                command = ["snap", "unset", "system", "proxy.https"]
            self._execute_run(command, timeout=self.timeout_simple)

        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set the snapd proxy.",
                details=details_from_called_process_error(error),
            ) from error

    def _disable_and_wait_for_snap_refresh(self) -> None:
        """Disable automatic snap refreshes and wait for refreshes to complete.

        Craft-providers manages the installation and versions of snaps inside the
        build environment, so automatic refreshes of snaps by snapd are disabled.
        """
        # disable refresh for 1 day
        hold_time = datetime.now() + timedelta(days=1)
        logger.debug("Holding refreshes for snaps.")

        # TODO: run `snap refresh --hold` once during setup (`--hold` is not yet stable)
        try:
            self.executor.execute_run(
                ["snap", "set", "system", f"refresh.hold={hold_time.isoformat()}Z"],
                capture_output=True,
                check=True,
                timeout=self.timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to hold snap refreshes.",
                details=details_from_called_process_error(error),
            ) from error

        # a refresh may have started before the hold was set
        logger.debug("Waiting for pending snap refreshes to complete.")
        try:
            self.executor.execute_run(
                ["snap", "watch", "--last=auto-refresh?"],
                capture_output=True,
                check=True,
                timeout=self.timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to wait for snap refreshes to complete.",
                details=details_from_called_process_error(error),
            ) from error

    def _install_snaps(self) -> None:
        """Install snaps.

        Snaps will either be installed from the store or injected from the host.
        - If channel is `None` on a linux system, the host snap is injected
          into the provider.
        - If channel is `None` on a non-linux system, an error is raised
          because host injection is not supported on non-linux systems.

        :raises BaseConfigurationError: if the snap cannot be installed
        """
        if not self.snaps:
            logger.debug("No snaps to install.")
            return

        for snap in self.snaps:
            logger.debug(
                "Installing snap %r with channel=%r and classic=%r",
                snap.name,
                snap.channel,
                snap.classic,
            )

            # don't inject snaps on non-linux hosts
            if sys.platform != "linux" and not snap.channel:
                raise BaseConfigurationError(
                    brief=(
                        f"cannot inject snap {snap.name!r} from host on "
                        "a non-linux system"
                    ),
                    resolution=(
                        "install the snap from the store by setting the "
                        "'channel' parameter"
                    ),
                )

            if snap.channel:
                try:
                    snap_installer.install_from_store(
                        executor=self.executor,
                        snap_name=snap.name,
                        channel=snap.channel,
                        classic=snap.classic,
                    )
                except SnapInstallationError as error:
                    raise BaseConfigurationError(
                        brief=(
                            f"failed to install snap {snap.name!r} from store"
                            f" channel {snap.channel!r} in target environment."
                        )
                    ) from error
            else:
                try:
                    snap_installer.inject_from_host(
                        executor=self.executor,
                        snap_name=snap.name,
                        classic=snap.classic,
                    )
                except SnapInstallationError as error:
                    raise BaseConfigurationError(
                        brief=(
                            f"failed to inject host's snap {snap.name!r} "
                            "into target environment."
                        )
                    ) from error

    def wait_until_ready(self) -> None:
        """Wait until base instance is ready.

        Ensure minimum-required boot services are running.  This would be used
        when starting an environment's container/VM after already [recently]
        running setup(), e.g. rebooting the instance.  Allows the environment to
        be used without the cost incurred by re-executing the steps
        unnecessarily.

        If timeout is specified, abort operation if time has been exceeded.

        Guarantees provided by this wait:

            - networking available (IP & DNS resolution)

            - system services are started and ready

        :raises ProviderError: on timeout or unexpected error.
        """
        self._setup_wait_for_system_ready()
        self._setup_wait_for_network()

    def _pre_image_check(self) -> None:
        """Start the setup process and update the status.

        This step usually does not need to be overridden.
        """
        return

    def _image_check(self) -> None:
        """Check that the image compatibility.

        This step usually does not need to be overridden.
        """
        self._ensure_os_compatible()
        self._ensure_instance_config_compatible()

    def _post_image_check(self) -> None:
        """Do anything extra image checking.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_os(self) -> None:
        """Do anything before setting up the OS.

        e.g.
            enable/disable services.
            load kernel modules.

        This step should be overridden when needed.
        """
        return

    def _setup_os(self) -> None:
        """Set up the OS environment.

        This step should be overridden when needed.
        """
        self._setup_environment()

    def _post_setup_os(self) -> None:
        """Do anything after setting up the OS.

        e.g.
            additional OS-related configuration.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_network(self) -> None:
        """Do anything before setting up the basic network.

        e.g.
            enable/disable other network managers.

        This step should be overridden when needed.
        """
        return

    def _setup_network(self) -> None:
        """Set up the basic network.

        Basic configuration for the systemd and networkd by default.

        Any other configuration requires overriding this step.
        If only part of it needs to be modified you should override only the
        corresponding function.

        This step usually does not need to be overridden.
        """
        self._setup_hostname()
        self._setup_resolved()
        self._setup_networkd()

    def _post_setup_network(self) -> None:
        """Do anything after setting up the basic network.

        e.g.
            additional network-related configuration.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_packages(self) -> None:
        """Do anything before setting up the packages.

        e.g.
            update package database.

        This step should be overridden when needed.
        """
        return

    @abstractmethod
    def _setup_packages(self) -> None:
        """Set up the packages.

        This step must be overridden.
        """

    def _post_setup_packages(self) -> None:
        """Configure the new installed packages.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_snapd(self) -> None:
        """Do anything before setting up snapd.

        e.g.
            enable depended services.
            check possible incompatibility issues.

        This step should be overridden when needed.
        """
        self._enable_udevd_service()
        self._disable_snapd_cdn()

    @abstractmethod
    def _setup_snapd(self) -> None:
        """Set up snapd.

        This step must be overridden.
        """

    def _post_setup_snapd(self) -> None:
        """Configure the new installed snapd.

        This step usually does not need to be overridden.
        """
        self._enable_snapd_service()
        self._disable_and_wait_for_snap_refresh()
        self._setup_snapd_proxy()

    def _pre_setup_snaps(self) -> None:
        """Do anything before setting up the snaps.

        e.g.
            remove non-snap old packages.

        This step should be overridden when needed.
        """
        return

    def _setup_snaps(self) -> None:
        """Set up the snaps.

        e.g.
            install snaps.

        This step should be overridden when needed.
        """
        self._install_snaps()

    def _post_setup_snaps(self) -> None:
        """Configure the new installed snaps.

        This step should be overridden when needed.
        """
        return

    def _pre_clean_up(self) -> None:
        """Do anything before cleaning up.

        e.g.
            stop affected services.

        This step should be overridden when needed.
        """
        return

    def _clean_up(self) -> None:
        """Cleanup the OS environment.

        e.g.
            remove unnecessary packages.
            remove cache files.

        This step should be overridden when needed.
        """
        return

    def _post_clean_up(self) -> None:
        """Do anything needed after cleaning up.

        e.g.
            restart affected services.
            rebuild packages database.

        This step should be overridden when needed.
        """
        return

    def _pre_finish(self) -> None:
        """Do anything needed before finishing the setup process.

        e.g.
            get the final package / snap versions.

        This step should be overridden when needed.
        """
        return

    @final
    def _finish(self) -> None:
        """Finish the setup process and update the status.

        This step cannot be overridden.
        """
        self._update_setup_status(status=True)

    @final
    def setup(
        self,
        *,
        executor: Executor,
        timeout: Optional[float] = -1,
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
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        self.executor = executor
        if timeout is None:
            self.timeout_unpredictable = None
        elif timeout > 0:
            self.timeout_unpredictable = timeout
        else:
            self.timeout_unpredictable = TIMEOUT_UNPREDICTABLE

        self._update_setup_status(status=False)

        self._pre_image_check()
        self._image_check()
        self._post_image_check()

        self._update_compatibility_tag()

        self._pre_setup_os()
        self._setup_os()
        self._post_setup_os()

        self._setup_wait_for_system_ready()

        self._pre_setup_network()
        self._setup_network()
        self._post_setup_network()

        self._setup_wait_for_network()

        self._pre_setup_packages()
        self._setup_packages()
        self._post_setup_packages()

        self._pre_setup_snapd()
        self._setup_snapd()
        self._post_setup_snapd()

        self._pre_setup_snaps()
        self._setup_snaps()
        self._post_setup_snaps()

        self._pre_clean_up()
        self._clean_up()
        self._post_clean_up()

        self._pre_finish()
        self._finish()

    @final
    def warmup(
        self,
        *,
        executor: Executor,
        timeout: Optional[float] = -1,
    ) -> None:
        """Prepare a previously created and setup instance for use by the application.

        Ensure the instance is still valid and wait for environment to become ready.

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        self.executor = executor

        if timeout is None:
            self.timeout_unpredictable = None
        elif timeout > 0:
            self.timeout_unpredictable = timeout
        else:
            self.timeout_unpredictable = TIMEOUT_UNPREDICTABLE

        self._ensure_setup_completed()

        self._pre_image_check()
        self._image_check()
        self._post_image_check()

        self._setup_wait_for_system_ready()
        self._setup_wait_for_network()

        self._post_setup_snapd()

        self._pre_setup_snaps()
        self._setup_snaps()
        self._post_setup_snaps()

    def _network_connected(self) -> bool:
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
            proc = self.executor.execute_run(
                command, check=False, timeout=10, capture_output=True
            )
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0

    def _execute_run(
        self,
        command: List[str],
        *,
        executor: Optional[Executor] = None,
        check: bool = True,
        capture_output: bool = True,
        text: bool = False,
        timeout: Optional[float] = None,
        verify_network=False,
    ) -> subprocess.CompletedProcess:
        """Run a command through the executor.

        This is a helper to simplify most common calls and provide extra network
        verification (if indicated) in a central place.

        The default of capture_output is True because it's useful for error reports
        (if the command failed) even if the output is not really wanted as a result
        of the execution.
        """
        if executor is None:
            executor = self.executor

        if not check and verify_network:
            # if check is False, the caller needs the process result no matter
            # what, it's wrong to also request to verify network, which may
            # raise a different exception
            raise RuntimeError("Invalid check and verify_network combination.")

        try:
            proc = executor.execute_run(
                command,
                check=check,
                capture_output=capture_output,
                text=text,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            if verify_network and not self._network_connected():
                raise NetworkError() from exc
            raise
        return proc
