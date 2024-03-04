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
import io
import logging
import math
import os
import pathlib
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from enum import Enum
from textwrap import dedent
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
from craft_providers.util import retry
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

    :param cache_path: (Optional) Path to the shared cache directory. If this is
        provided, shared cache directories will be mounted as appropriate. Some
        directories depend on the base implementation.
    """

    _environment: Dict[str, Optional[str]]
    _hostname: str
    _instance_config_path = pathlib.PurePosixPath("/etc/craft-instance.conf")
    _instance_config_class: Type[InstanceConfiguration] = InstanceConfiguration
    _snaps: Optional[List[Snap]] = None
    _packages: Optional[List[str]] = None
    _retry_wait: float = RETRY_WAIT
    _timeout_simple: Optional[float] = TIMEOUT_SIMPLE
    _timeout_complex: Optional[float] = TIMEOUT_COMPLEX
    _timeout_unpredictable: Optional[float] = TIMEOUT_UNPREDICTABLE
    _cache_path: Optional[pathlib.Path] = None
    alias: Enum
    compatibility_tag: str = "base-v7"

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
        use_default_packages: bool = True,
        cache_path: Optional[pathlib.Path] = None,
    ) -> None:
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
        self._hostname = valid_name

    def _ensure_instance_config_compatible(self, executor: Executor) -> None:
        """Ensure instance configuration is compatible.

        As long as the config is not incompatible (via a mismatched compatibility tag),
        then assume the instance is compatible. This assumption is done because the
        config file may not exist or contain a tag while the set up is in progress.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        try:
            config = InstanceConfiguration.load(
                executor=executor,
                config_path=self._instance_config_path,
            )
        except ValidationError as error:
            raise BaseConfigurationError(
                brief="Failed to parse instance configuration file.",
            ) from error
        # if no config exists, assume base is compatible (likely unfinished setup)
        # XXX: checking the compatibility_tag should be much more strict when called
        # by warmup (warmup will continue if the compatibility tag is missing or none!)
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

    def _ensure_setup_completed(self, executor: Executor) -> None:
        """Ensure the instance was fully setup.

        The last step of setting up an instance is to set the `setup` key in the
        instance config file to True. This flag is used to verify that setup was
        completed for the instance.

        :raises BaseCompatibilityError: If setup was not completed.
        """
        try:
            config = InstanceConfiguration.load(
                executor=executor,
                config_path=self._instance_config_path,
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

    def _get_os_release(self, executor: Executor) -> Dict[str, str]:
        """Get the OS release information from an instance's /etc/os-release.

        :returns: Dictionary of key-mappings found in os-release.
        """

        # `lxc exec` will occasionally print an empty string when the CPU is
        # busy. The retry logic here decreases the chance of that.
        def getter(timeout: float) -> str:
            try:
                # Replace encoding errors if it somehow occurs with utf-8. This
                # doesn't need to be perfect for checking compatibility.
                proc = executor.execute_run(
                    command=["cat", "/etc/os-release"],
                    capture_output=True,
                    check=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
            except subprocess.CalledProcessError as error:
                raise BaseConfigurationError(
                    brief="Failed to read /etc/os-release.",
                    details=details_from_called_process_error(error),
                ) from error
            if not proc.stdout:
                raise BaseConfigurationError(
                    brief="Failed to read /etc/os-release.",
                    details="File appears to be empty.",
                )
            return proc.stdout

        return parse_os_release(
            retry.retry_until_timeout(
                self._timeout_simple or TIMEOUT_SIMPLE,
                self._retry_wait,
                getter,
                error=None,
            )
        )

    @abstractmethod
    def _ensure_os_compatible(self, executor: Executor) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """

    def get_command_environment(self) -> Dict[str, Optional[str]]:
        """Get command environment to use when executing commands.

        :returns: Dictionary of environment, allowing None as a value to
                  indicate that a value should be unset.
        """
        return self._environment.copy()

    def _update_setup_status(self, executor: Executor, status: bool) -> None:
        """Update the instance config to indicate the status of the setup.

        :param status: True if the setup is complete, False otherwise.
        """
        InstanceConfiguration.update(
            executor=executor,
            data={"setup": status},
            config_path=self._instance_config_path,
        )

    def _update_compatibility_tag(self, executor: Executor) -> None:
        """Update the compatibility_tag in the instance config."""
        InstanceConfiguration.update(
            executor=executor,
            data={"compatibility_tag": self.compatibility_tag},
            config_path=self._instance_config_path,
        )

    def _setup_environment(self, executor: Executor) -> None:
        """Configure /etc/environment.

        If environment is None, reset /etc/environment to the default.
        """
        content = (
            "\n".join(
                [f"{k}={v}" for k, v in self._environment.items() if v is not None]
            )
            + "\n"
        ).encode()

        executor.push_file_io(
            destination=pathlib.PurePosixPath("/etc/environment"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    def _setup_wait_for_system_ready(self, executor: Executor) -> None:
        """Wait until system is ready."""
        logger.debug("Waiting for environment to be ready...")

        def assert_running(timeout: float) -> None:
            proc = self._execute_run(
                ["systemctl", "is-system-running"],
                executor=executor,
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout,
            )
            system_state = proc.stdout.strip()
            if system_state not in ("running", "degraded"):
                logger.debug("systemctl is-system-running status: %s", system_state)
                raise ValueError

        error = BaseConfigurationError(
            brief="Timed out waiting for environment to be ready."
        )
        retry.retry_until_timeout(
            self._timeout_simple or TIMEOUT_SIMPLE,
            self._retry_wait,
            assert_running,
            error=error,
        )

    def _setup_hostname(self, executor: Executor) -> None:
        """Configure hostname, installing /etc/hostname."""
        executor.push_file_io(
            destination=pathlib.PurePosixPath("/etc/hostname"),
            content=io.BytesIO((self._hostname + "\n").encode()),
            file_mode="0644",
        )

        try:
            self._execute_run(
                ["hostname", "-F", "/etc/hostname"],
                executor=executor,
                timeout=self._timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set hostname.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_networkd(self, executor: Executor) -> None:
        """Configure networkd and start it.

        Installs eth0 network configuration using ipv4.
        """
        executor.push_file_io(
            destination=pathlib.PurePosixPath("/etc/systemd/network/10-eth0.network"),
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
                ["systemctl", "enable", "systemd-networkd"],
                executor=executor,
                timeout=self._timeout_simple,
            )
            self._execute_run(
                ["systemctl", "restart", "systemd-networkd"],
                executor=executor,
                timeout=self._timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-networkd.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_resolved(self, executor: Executor) -> None:
        """Configure system-resolved to manage resolve.conf."""
        try:
            command = [
                "ln",
                "-sf",
                "/run/systemd/resolve/resolv.conf",
                "/etc/resolv.conf",
            ]
            self._execute_run(command, executor=executor, timeout=self._timeout_simple)

            self._execute_run(
                ["systemctl", "enable", "systemd-resolved"],
                executor=executor,
                timeout=self._timeout_simple,
            )

            self._execute_run(
                ["systemctl", "restart", "systemd-resolved"],
                executor=executor,
                timeout=self._timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-resolved.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_wait_for_network(self, executor: Executor) -> None:
        """Wait until networking is ready."""
        logger.debug("Waiting for networking to be ready...")
        command = ["getent", "hosts", "snapcraft.io"]

        def check_network(timeout: float) -> None:
            self._execute_run(
                command, executor=executor, check=True, timeout=0.1 * timeout
            )

        error = BaseConfigurationError(
            brief="Timed out waiting for networking to be ready."
        )
        retry.retry_until_timeout(
            self._timeout_simple or math.inf,
            self._retry_wait,
            check_network,
            error=error,
        )

    def _enable_udevd_service(self, executor: Executor) -> None:
        """Enable and start udevd service."""
        try:
            proc = self._execute_run(
                ["systemctl", "is-active", "systemd-udevd"],
                executor=executor,
                capture_output=True,
                check=False,
                text=True,
                timeout=self._timeout_simple,
            )

            state = proc.stdout.strip()
            if state == "active":
                return

            # systemd-udevd is not active, enable and start it
            self._execute_run(
                ["systemctl", "enable", "systemd-udevd"],
                executor=executor,
                timeout=TIMEOUT_SIMPLE,
            )
            self._execute_run(
                ["systemctl", "start", "systemd-udevd"],
                executor=executor,
                timeout=TIMEOUT_SIMPLE,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to enable systemd-udevd service.",
                details=details_from_called_process_error(error),
            ) from error

    def _disable_snapd_cdn(self, executor: Executor) -> None:
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
                    executor=executor,
                    timeout=TIMEOUT_SIMPLE,
                )

                executor.push_file(source=no_cdn, destination=no_cdn)
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to disable snapd CDN.",
                details=details_from_called_process_error(error),
            ) from error

    def _enable_snapd_service(self, executor: Executor) -> None:
        """Create the symlink to /snap and enable the snapd service."""
        try:
            self._execute_run(
                ["ln", "-sf", "/var/lib/snapd/snap", "/snap"],
                executor=executor,
                timeout=TIMEOUT_SIMPLE,
            )

            self._execute_run(
                ["systemctl", "enable", "--now", "snapd.socket"],
                executor=executor,
                timeout=TIMEOUT_SIMPLE,
            )

            # Restart, not start, the service in case the environment
            # has changed and the service is already running.
            self._execute_run(
                ["systemctl", "restart", "snapd.service"],
                executor=executor,
                timeout=TIMEOUT_SIMPLE,
            )
            self._execute_run(
                ["snap", "wait", "system", "seed.loaded"],
                executor=executor,
                timeout=TIMEOUT_SIMPLE,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to enable snapd service.",
                details=details_from_called_process_error(error),
            ) from error

    def _setup_snapd_proxy(self, executor: Executor) -> None:
        """Configure the snapd proxy."""
        try:
            http_proxy = self._environment.get("http_proxy")
            if http_proxy:
                command = ["snap", "set", "system", f"proxy.http={http_proxy}"]
            else:
                command = ["snap", "unset", "system", "proxy.http"]
            self._execute_run(command, executor=executor, timeout=self._timeout_simple)

            https_proxy = self._environment.get("https_proxy")
            if https_proxy:
                command = ["snap", "set", "system", f"proxy.https={https_proxy}"]
            else:
                command = ["snap", "unset", "system", "proxy.https"]
            self._execute_run(command, executor=executor, timeout=self._timeout_simple)

        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set the snapd proxy.",
                details=details_from_called_process_error(error),
            ) from error

    def _disable_and_wait_for_snap_refresh(self, executor: Executor) -> None:
        """Disable automatic snap refreshes and wait for refreshes to complete.

        Automatic snap refreshes are disabled because craft-providers manages the
        installation and versions of snaps inside the build environment.

        :param executor: Executor for target container.

        :raises BaseConfigurationError: if snap refreshes cannot be disabled or an
        error occurs while waiting for pending refreshes to complete.
        """
        logger.debug("Holding refreshes for snaps.")

        try:
            executor.execute_run(
                ["snap", "refresh", "--hold"],
                capture_output=True,
                check=True,
                timeout=self._timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to hold snap refreshes.",
                details=details_from_called_process_error(error),
            ) from error

        # a refresh may have started before the hold was set
        logger.debug("Waiting for pending snap refreshes to complete.")
        try:
            executor.execute_run(
                ["snap", "watch", "--last=auto-refresh?"],
                capture_output=True,
                check=True,
                timeout=self._timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to wait for snap refreshes to complete.",
                details=details_from_called_process_error(error),
            ) from error

    def _install_snaps(self, executor: Executor) -> None:
        """Install snaps.

        Snaps will either be installed from the store or injected from the host.
        - If channel is `None` on a linux system, the host snap is injected
          into the provider.
        - If channel is `None` on a non-linux system, an error is raised
          because host injection is not supported on non-linux systems.

        :raises BaseConfigurationError: if the snap cannot be installed
        """
        if not self._snaps:
            logger.debug("No snaps to install.")
            return

        for snap in self._snaps:
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
                        executor=executor,
                        snap_name=snap.name,
                        channel=snap.channel,
                        classic=snap.classic,
                    )
                except SnapInstallationError as error:
                    raise BaseConfigurationError(
                        brief=(
                            f"failed to install snap {snap.name!r} from store"
                            f" channel {snap.channel!r} in target environment."
                        ),
                        details=error.details,
                    ) from error
            else:
                try:
                    snap_installer.inject_from_host(
                        executor=executor,
                        snap_name=snap.name,
                        classic=snap.classic,
                    )
                except SnapInstallationError as error:
                    raise BaseConfigurationError(
                        brief=(
                            f"failed to inject host's snap {snap.name!r} "
                            "into target environment."
                        ),
                        details=error.details,
                    ) from error

    def wait_until_ready(self, executor: Executor) -> None:
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
        self._setup_wait_for_system_ready(executor=executor)
        self._setup_wait_for_network(executor=executor)

    def _pre_image_check(self, executor: Executor) -> None:
        """Start the setup process and update the status.

        This step usually does not need to be overridden.
        """
        return

    def _image_check(self, executor: Executor) -> None:
        """Check that the image compatibility.

        This step usually does not need to be overridden.
        """
        self._ensure_os_compatible(executor=executor)
        self._ensure_instance_config_compatible(executor=executor)

    def _post_image_check(self, executor: Executor) -> None:
        """Do anything extra image checking.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_os(self, executor: Executor) -> None:
        """Do anything before setting up the OS.

        e.g.
            enable/disable services.
            load kernel modules.

        This step should be overridden when needed.
        """
        return

    def _setup_os(self, executor: Executor) -> None:
        """Set up the OS environment.

        This step should be overridden when needed.
        """
        self._setup_environment(executor=executor)

    def _post_setup_os(self, executor: Executor) -> None:
        """Do anything after setting up the OS.

        e.g.
            additional OS-related configuration.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_network(self, executor: Executor) -> None:
        """Do anything before setting up the basic network.

        e.g.
            enable/disable other network managers.

        This step should be overridden when needed.
        """
        return

    def _setup_network(self, executor: Executor) -> None:
        """Set up the basic network.

        Basic configuration for the systemd and networkd by default.

        Any other configuration requires overriding this step.
        If only part of it needs to be modified you should override only the
        corresponding function.

        This step usually does not need to be overridden.
        """
        self._setup_hostname(executor=executor)

    def _post_setup_network(self, executor: Executor) -> None:
        """Do anything after setting up the basic network.

        e.g.
            additional network-related configuration.

        This step should be overridden when needed.
        """
        return

    def _mount_shared_cache_dirs(self, executor: Executor) -> None:
        """Mount shared cache directories for this base.

        e.g.
            pip cache (normally $HOME/.cache/pip)

        This will only be run if caching is enabled for this instance.

        This step should usually be extended, but may be overridden if common
        cache directories are in unusual locations.
        """
        if self._cache_path is None:
            logger.debug("No cache path set, not mounting cache directories.")
            return

        # Get the real path with additional tags.
        host_base_cache_path = self._cache_path.resolve().joinpath(
            self.compatibility_tag, str(self.alias)
        )

        try:
            host_base_cache_path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise BaseConfigurationError(
                brief=f"Failed to create host cache directory: {host_base_cache_path}"
            ) from error

        guest_cache_proc = executor.execute_run(
            ["bash", "-c", "echo -n ${XDG_CACHE_HOME:-${HOME}/.cache}"],
            capture_output=True,
            text=True,
        )
        guest_base_cache_path = pathlib.Path(guest_cache_proc.stdout)

        # PIP cache
        host_pip_cache_path = host_base_cache_path / "pip"
        host_pip_cache_path.mkdir(parents=True, exist_ok=True)

        guest_pip_cache_path = guest_base_cache_path / "pip"
        executor.execute_run(
            ["mkdir", "-p", guest_pip_cache_path.as_posix()],
        )

        executor.mount(host_source=host_pip_cache_path, target=guest_pip_cache_path)

    def _pre_setup_packages(self, executor: Executor) -> None:
        """Do anything before setting up the packages.

        e.g.
            update package database.

        This step should be overridden when needed.
        """
        return

    @abstractmethod
    def _setup_packages(self, executor: Executor) -> None:
        """Set up the packages.

        This step must be overridden.
        """

    def _post_setup_packages(self, executor: Executor) -> None:
        """Configure the new installed packages.

        This step should be overridden when needed.
        """
        return

    def _pre_setup_snapd(self, executor: Executor) -> None:
        """Do anything before setting up snapd.

        e.g.
            enable depended services.
            check possible incompatibility issues.

        This step should be overridden when needed.
        """
        self._enable_udevd_service(executor=executor)
        self._disable_snapd_cdn(executor=executor)

    @abstractmethod
    def _setup_snapd(self, executor: Executor) -> None:
        """Set up snapd.

        This step must be overridden.
        """

    def _post_setup_snapd(self, executor: Executor) -> None:
        """Configure the new installed snapd.

        This step usually does not need to be overridden.
        """
        self._enable_snapd_service(executor=executor)
        self._disable_and_wait_for_snap_refresh(executor=executor)
        self._setup_snapd_proxy(executor=executor)

    def _warmup_snapd(self, executor: Executor) -> None:
        """Warmup snapd.

        This step usually does not need to be overridden.
        """
        self._setup_snapd_proxy(executor=executor)

    def _pre_setup_snaps(self, executor: Executor) -> None:
        """Do anything before setting up the snaps.

        e.g.
            remove non-snap old packages.

        This step should be overridden when needed.
        """
        return

    def _setup_snaps(self, executor: Executor) -> None:
        """Set up the snaps.

        e.g.
            install snaps.

        This step should be overridden when needed.
        """
        self._install_snaps(executor=executor)

    def _post_setup_snaps(self, executor: Executor) -> None:
        """Configure the new installed snaps.

        This step should be overridden when needed.
        """
        return

    def _pre_clean_up(self, executor: Executor) -> None:
        """Do anything before cleaning up.

        e.g.
            stop affected services.

        This step should be overridden when needed.
        """
        return

    def _clean_up(self, executor: Executor) -> None:
        """Cleanup the OS environment.

        e.g.
            remove unnecessary packages.
            remove cache files.

        This step should be overridden when needed.
        """
        return

    def _post_clean_up(self, executor: Executor) -> None:
        """Do anything needed after cleaning up.

        e.g.
            restart affected services.
            rebuild packages database.

        This step should be overridden when needed.
        """
        return

    def _pre_finish(self, executor: Executor) -> None:
        """Do anything needed before finishing the setup process.

        e.g.
            get the final package / snap versions.

        This step should be overridden when needed.
        """
        return

    @final
    def _finish(self, executor: Executor) -> None:
        """Finish the setup process and update the status.

        This step cannot be overridden.
        """
        self._update_setup_status(executor=executor, status=True)

    @final
    def setup(
        self,
        *,
        executor: Executor,
        timeout: Optional[float] = TIMEOUT_UNPREDICTABLE,
        mount_cache: bool = True,
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
        :param mount_cache: If true, mount the cache directories.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        if timeout is None:
            self._timeout_simple = None
            self._timeout_complex = None
            self._timeout_unpredictable = None
        elif timeout > 0:
            self._timeout_unpredictable = timeout
        else:
            raise BaseConfigurationError(f"Invalid timeout value: {timeout}")

        self._update_setup_status(executor=executor, status=False)

        self._pre_image_check(executor=executor)
        self._image_check(executor=executor)
        self._post_image_check(executor=executor)

        self._update_compatibility_tag(executor=executor)

        if mount_cache:
            self._mount_shared_cache_dirs(executor=executor)

        self._pre_setup_os(executor=executor)
        self._setup_os(executor=executor)
        self._post_setup_os(executor=executor)

        self._setup_wait_for_system_ready(executor=executor)

        self._pre_setup_network(executor=executor)
        self._setup_network(executor=executor)
        self._post_setup_network(executor=executor)

        self._setup_wait_for_network(executor=executor)

        self._pre_setup_packages(executor=executor)
        self._setup_packages(executor=executor)
        self._post_setup_packages(executor=executor)

        self._pre_setup_snapd(executor=executor)
        self._setup_snapd(executor=executor)
        self._post_setup_snapd(executor=executor)

        self._pre_setup_snaps(executor=executor)
        self._setup_snaps(executor=executor)
        self._post_setup_snaps(executor=executor)

        self._pre_clean_up(executor=executor)
        self._clean_up(executor=executor)
        self._post_clean_up(executor=executor)

        self._pre_finish(executor=executor)
        self._finish(executor=executor)

    @final
    def warmup(
        self,
        *,
        executor: Executor,
        timeout: Optional[float] = TIMEOUT_UNPREDICTABLE,
    ) -> None:
        """Prepare a previously created and setup instance for use by the application.

        Ensure the instance is still valid and wait for environment to become ready.

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        if timeout is None:
            self._timeout_simple = None
            self._timeout_complex = None
            self._timeout_unpredictable = None
        elif timeout > 0:
            self._timeout_unpredictable = timeout
        else:
            raise BaseConfigurationError(f"Invalid timeout value: {timeout}")

        self._ensure_setup_completed(executor=executor)

        self._pre_image_check(executor=executor)
        self._image_check(executor=executor)
        self._post_image_check(executor=executor)

        self._mount_shared_cache_dirs(executor=executor)

        self._setup_wait_for_system_ready(executor=executor)
        self._setup_wait_for_network(executor=executor)

        self._warmup_snapd(executor=executor)

        self._pre_setup_snaps(executor=executor)
        self._setup_snaps(executor=executor)
        self._post_setup_snaps(executor=executor)

    @staticmethod
    def _network_connected(executor: Executor) -> bool:
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
                command, check=False, timeout=10, capture_output=True
            )
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0

    @classmethod
    def _execute_run(
        cls,
        command: List[str],
        *,
        executor: Executor,
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
            if verify_network and not cls._network_connected(executor=executor):
                raise NetworkError from exc
            raise
        return proc
