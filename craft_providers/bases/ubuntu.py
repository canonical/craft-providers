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

"""Ubuntu image(s)."""
import enum
import io
import logging
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from textwrap import dedent
from time import sleep
from typing import Dict, List, Optional, Type

from pydantic import ValidationError

from craft_providers import Base, Executor, errors
from craft_providers.actions import snap_installer
from craft_providers.actions.snap_installer import Snap, SnapInstallationError
from craft_providers.errors import BaseCompatibilityError, BaseConfigurationError
from craft_providers.util.os_release import parse_os_release

from .instance_config import InstanceConfiguration

logger = logging.getLogger(__name__)

# pylint: disable=too-many-lines


class BuilddBaseAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = "16.04"
    BIONIC = "18.04"
    FOCAL = "20.04"
    JAMMY = "22.04"
    KINETIC = "22.10"
    LUNAR = "23.04"
    DEVEL = "devel"


class BuilddBase(Base):
    """Support for Ubuntu minimal buildd images.

    :cvar compatibility_tag: Tag/Version for variant of build configuration and
        setup.  Any change to this version would indicate that prior [versioned]
        instances are incompatible and must be cleaned.  As such, any new value
        should be unique to old values (e.g. incrementing).  It is suggested to
        extend this tag, not overwrite it, e.g.: compatibility_tag =
        f"{appname}-{BuildBase.compatibility_tag}.{apprevision}" to ensure base
        compatibility levels are maintained.
    :cvar instance_config_path: Path to persistent environment configuration
        used for compatibility checks (or other data).  Set to
        /etc/craft-instance.conf, but may be overridden for application-specific
        reasons.
    :cvar instance_config_class: Class defining instance configuration.  May be
        overridden with an application-specific subclass of InstanceConfiguration
        to enable application-specific extensions.

    :param alias: Base alias / version.
    :param environment: Environment to set in /etc/environment.
    :param hostname: Hostname to configure.
    :param snaps: Optional list of snaps to install on the base image.
    :param packages: Optional list of system packages to install on the base image.
    """

    compatibility_tag: str = f"buildd-{Base.compatibility_tag}"
    instance_config_path: pathlib.Path = pathlib.Path("/etc/craft-instance.conf")
    instance_config_class: Type[InstanceConfiguration] = InstanceConfiguration

    def __init__(
        self,
        *,
        alias: BuilddBaseAlias,
        compatibility_tag: Optional[str] = None,
        environment: Optional[Dict[str, Optional[str]]] = None,
        hostname: str = "craft-buildd-instance",
        snaps: Optional[List[Snap]] = None,
        packages: Optional[List[str]] = None,
    ):
        self.alias: BuilddBaseAlias = alias

        if environment is None:
            self.environment = self.default_command_environment()
        else:
            self.environment = environment

        if compatibility_tag:
            self.compatibility_tag = compatibility_tag

        self._set_hostname(hostname)
        self.snaps = snaps
        self.packages = packages

    @staticmethod
    def default_command_environment() -> Dict[str, Optional[str]]:
        """Provide default command environment dictionary.

        The minimum environment for the buildd image to be configured and function
        properly.  This contains the default environment found in Ubuntu's
        /etc/environment, replaced with the "secure_path" defaults used by sudo for
        instantiating PATH.  In practice it really just means the PATH set by sudo.

        Default /etc/environment found in supported Ubuntu versions:
        PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:
            /usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin

        Default /etc/sudoers secure_path found in supported Ubuntu versions:
        PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

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

    def _ensure_instance_config_compatible(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Ensure instance configuration is compatible.

        As long as the config is not incompatible (via a mismatched compatibility tag),
        then assume the instance is compatible. This assumption is done because the
        config file may not exist or contain a tag while the set up is in progress.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        self._check_deadline(deadline)

        try:
            config = InstanceConfiguration.load(
                executor=executor,
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

    def _ensure_setup_completed(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Ensure the instance was fully setup.

        The last step of setting up an instance is to set the `setup` key in the
        instance config file to True. This flag is used to verify that setup was
        completed for the instance.

        :raises BaseCompatibilityError: If setup was not completed.
        """
        self._check_deadline(deadline)

        try:
            config = InstanceConfiguration.load(
                executor=executor,
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

    def _get_os_release(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> Dict[str, str]:
        """Get the OS release information from an instance's /etc/os-release.

        :param executor: Executor to get OS release from.
        :param deadline: Optional time.time() deadline.

        :returns: Dictionary of key-mappings found in os-release.
        """
        self._check_deadline(deadline)
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
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to read /etc/os-release.",
                details=errors.details_from_called_process_error(error),
            ) from error

        return parse_os_release(proc.stdout)

    def _ensure_os_compatible(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        os_release = self._get_os_release(executor=executor, deadline=deadline)

        os_name = os_release.get("NAME")
        if os_name != "Ubuntu":
            raise BaseCompatibilityError(
                reason=f"Expected OS 'Ubuntu', found {os_name!r}"
            )

        compat_version_id = self.alias.value
        version_id = os_release.get("VERSION_ID")

        if compat_version_id == BuilddBaseAlias.DEVEL.value:
            logger.debug(
                "Ignoring OS version mismatch for %r because base is %r.",
                version_id,
                compat_version_id,
            )
            return

        if version_id != compat_version_id:
            raise BaseCompatibilityError(
                reason=(
                    f"Expected OS version {compat_version_id!r},"
                    f" found {version_id!r}"
                )
            )

    def get_command_environment(
        self,
    ) -> Dict[str, Optional[str]]:
        """Get command environment to use when executing commands.

        :returns: Dictionary of environment, allowing None as a value to
                  indicate that a value should be unset.
        """
        return self.environment.copy()

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

        The state of the setup is tracked in the instance config. If the setup is
        interrupted, the state can be checked so that a partially setup instance
        can be discarded.

        Setup may be called more than once in a given instance to refresh/update
        the environment.

        If timeout is specified, abort operation if time has been exceeded.

        Guarantees provided by this setup:
          - configured /etc/environment
          - configured hostname
          - networking available (IP & DNS resolution)
          - apt cache up-to-date
          - snapd configured and ready
          - system services are started and ready

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if
            required).
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        if timeout is not None:
            deadline: Optional[float] = time.time() + timeout
        else:
            deadline = None

        self._update_setup_status(executor=executor, deadline=deadline, status=False)
        self._ensure_os_compatible(executor=executor, deadline=deadline)
        self._ensure_instance_config_compatible(executor=executor, deadline=deadline)
        self._disable_automatic_apt(executor=executor, deadline=deadline)
        self._setup_environment(executor=executor, deadline=deadline)
        self._setup_wait_for_system_ready(
            executor=executor, deadline=deadline, retry_wait=retry_wait
        )
        self._update_compatibility_tag(executor=executor, deadline=deadline)
        self._setup_hostname(executor=executor, deadline=deadline)
        self._setup_resolved(executor=executor, deadline=deadline)
        self._setup_networkd(executor=executor, deadline=deadline)
        self._setup_wait_for_network(
            executor=executor, deadline=deadline, retry_wait=retry_wait
        )
        self._setup_apt(executor=executor, deadline=deadline)
        self._setup_snapd(executor=executor, deadline=deadline)
        self._disable_and_wait_for_snap_refresh(executor=executor, deadline=deadline)
        self._setup_snapd_proxy(executor=executor, deadline=deadline)
        self._install_snaps(executor=executor, deadline=deadline)
        self._update_setup_status(executor=executor, deadline=deadline, status=True)

    def warmup(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Prepare a previously created and setup instance for use by the application.

        Ensure the instance is still valid and wait for environment to become ready.

        Guarantees provided by this wait:
          - OS and instance config are compatible
          - networking available (IP & DNS resolution)
          - system services are started and ready

        If timeout is specified, abort operation if time has been exceeded.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if required).
        :param timeout: Timeout in seconds.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        if timeout is not None:
            deadline: Optional[float] = time.time() + timeout
        else:
            deadline = None

        self._ensure_setup_completed(executor=executor, deadline=deadline)
        self._ensure_os_compatible(executor=executor, deadline=deadline)

        # XXX: checking the compatibility_tag should be much more strict when called
        # by warmup (warmup will continue if the compatibility tag is missing or none!)
        self._ensure_instance_config_compatible(executor=executor, deadline=deadline)

        self._setup_wait_for_system_ready(
            executor=executor, deadline=deadline, retry_wait=retry_wait
        )
        self._setup_wait_for_network(
            executor=executor, deadline=deadline, retry_wait=retry_wait
        )
        self._disable_and_wait_for_snap_refresh(executor=executor, deadline=deadline)
        self._setup_snapd_proxy(executor=executor, deadline=deadline)
        self._install_snaps(executor=executor, deadline=deadline)

    def _disable_automatic_apt(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Disable automatic apt actions.

        This should happen as soon as possible in the instance overall setup,
        to reduce the chances of an automatic apt work being triggered during
        the setup itself (because it includes apt work which may clash
        the triggered unattended jobs).

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        self._check_deadline(deadline)
        # set the verification frequency in 10000 days and disable the upgrade
        content = dedent(
            """\
            APT::Periodic::Update-Package-Lists "10000";
            APT::Periodic::Unattended-Upgrade "0";
        """
        ).encode()
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/20auto-upgrades"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    def _disable_and_wait_for_snap_refresh(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Disable automatic snap refreshes and wait for refreshes to complete.

        Craft-providers manages the installation and versions of snaps inside the
        build environment, so automatic refreshes of snaps by snapd are disabled.
        """
        # disable refresh for 1 day
        hold_time = datetime.now() + timedelta(days=1)
        logger.debug("Holding refreshes for snaps.")

        self._check_deadline(deadline)
        # TODO: run `snap refresh --hold` once during setup (`--hold` is not yet stable)
        try:
            executor.execute_run(
                ["snap", "set", "system", f"refresh.hold={hold_time.isoformat()}Z"],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to hold snap refreshes.",
                details=errors.details_from_called_process_error(error),
            ) from error

        # a refresh may have started before the hold was set
        logger.debug("Waiting for pending snap refreshes to complete.")
        self._check_deadline(deadline)
        try:
            executor.execute_run(
                ["snap", "watch", "--last=auto-refresh?"],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to wait for snap refreshes to complete.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _install_snaps(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Install snaps.

        Snaps will either be installed from the store or injected from the host.
        - If channel is `None` on a linux system, the host snap is injected
          into the provider.
        - If channel is `None` on a non-linux system, an error is raised
          because host injection is not supported on non-linux systems.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        :raises BaseConfigurationError: if the snap cannot be installed
        """
        if not self.snaps:
            logger.debug("No snaps to install.")
            return

        for snap in self.snaps:
            self._check_deadline(deadline)
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
                        )
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
                        )
                    ) from error

    def _setup_apt(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Configure apt, update cache and install needed packages.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        self._check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00no-recommends"),
            content=io.BytesIO('APT::Install-Recommends "false";\n'.encode()),
            file_mode="0644",
        )

        self._check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00update-errors"),
            content=io.BytesIO('APT::Update::Error-Mode "any";\n'.encode()),
            file_mode="0644",
        )

        # devel images should use the devel repository
        if self.alias == BuilddBaseAlias.DEVEL:
            self._update_apt_sources(
                executor=executor,
                deadline=deadline,
                codename=BuilddBaseAlias.DEVEL.value,
            )

        try:
            self._check_deadline(deadline)
            self._execute_run(executor, ["apt-get", "update"], verify_network=True)
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update apt cache.",
                details=errors.details_from_called_process_error(error),
            ) from error

        # install required packages and user-defined packages
        packages_to_install = ["apt-utils", "curl"]
        if self.packages:
            packages_to_install.extend(self.packages)

        try:
            self._check_deadline(deadline)
            command = ["apt-get", "install", "-y"] + packages_to_install
            self._execute_run(executor, command, verify_network=True)
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to install packages.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_environment(
        self,
        *,
        executor: Executor,
        deadline: Optional[float],
    ) -> None:
        """Configure /etc/environment.

        If environment is None, reset /etc/environment to the default.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        content = (
            "\n".join(
                [f"{k}={v}" for k, v in self.environment.items() if v is not None]
            )
            + "\n"
        ).encode()

        self._check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/environment"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    def _setup_hostname(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Configure hostname, installing /etc/hostname.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        self._check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/hostname"),
            content=io.BytesIO((self.hostname + "\n").encode()),
            file_mode="0644",
        )

        try:
            self._check_deadline(deadline)
            self._execute_run(executor, ["hostname", "-F", "/etc/hostname"])
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set hostname.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_networkd(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Configure networkd and start it.

        Installs eth0 network configuration using ipv4.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        self._check_deadline(deadline)
        executor.push_file_io(
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
            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "enable", "systemd-networkd"])

            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "restart", "systemd-networkd"])
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-networkd.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_resolved(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Configure system-resolved to manage resolve.conf.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        try:
            self._check_deadline(deadline)
            command = [
                "ln",
                "-sf",
                "/run/systemd/resolve/resolv.conf",
                "/etc/resolv.conf",
            ]
            self._execute_run(executor, command)

            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "enable", "systemd-resolved"])

            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "restart", "systemd-resolved"])
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-resolved.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_snapd(
        self, *, executor: Executor, deadline: Optional[float] = None
    ) -> None:
        """Install snapd and dependencies and wait until ready.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        try:
            self._check_deadline(deadline)
            command = ["apt-get", "install", "-y", "fuse", "udev"]
            self._execute_run(executor, command, verify_network=True)

            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "enable", "systemd-udevd"])
            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "start", "systemd-udevd"])

            # This file is created by launchpad-buildd to stop snapd from
            # using the snap store's CDN when running in Canonical's
            # production build farm, since internet access restrictions may
            # prevent it from doing so but will allow the non-CDN storage
            # endpoint.  If this is in place, then we need to propagate it
            # to containers we create.
            no_cdn = pathlib.Path("/etc/systemd/system/snapd.service.d/no-cdn.conf")
            if no_cdn.exists():
                self._check_deadline(deadline)
                self._execute_run(executor, ["mkdir", "-p", no_cdn.parent.as_posix()])

                self._check_deadline(deadline)
                executor.push_file(source=no_cdn, destination=no_cdn)

            self._check_deadline(deadline)
            self._execute_run(
                executor, ["apt-get", "install", "-y", "snapd"], verify_network=True
            )

            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "start", "snapd.socket"])

            # Restart, not start, the service in case the environment
            # has changed and the service is already running.
            self._check_deadline(deadline)
            self._execute_run(executor, ["systemctl", "restart", "snapd.service"])

            self._check_deadline(deadline)
            self._execute_run(executor, ["snap", "wait", "system", "seed.loaded"])

        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup snapd.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_snapd_proxy(
        self, *, executor: Executor, deadline: Optional[float] = None
    ) -> None:
        """Configure the snapd proxy.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        try:
            self._check_deadline(deadline)
            http_proxy = self.environment.get("http_proxy")
            if http_proxy:
                command = ["snap", "set", "system", f"proxy.http={http_proxy}"]
            else:
                command = ["snap", "unset", "system", "proxy.http"]
            self._execute_run(executor, command)

            self._check_deadline(deadline)
            https_proxy = self.environment.get("https_proxy")
            if https_proxy:
                command = ["snap", "set", "system", f"proxy.https={https_proxy}"]
            else:
                command = ["snap", "unset", "system", "proxy.https"]
            self._execute_run(executor, command)

        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set the snapd proxy.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_wait_for_network(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        deadline: Optional[float] = None,
    ) -> None:
        """Wait until networking is ready.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks.
        :param deadline: Optional time.time() deadline.
        """
        logger.debug("Waiting for networking to be ready...")

        self._check_deadline(deadline)
        command = ["getent", "hosts", "snapcraft.io"]
        while True:
            proc = self._execute_run(executor, command, check=False)
            if proc.returncode == 0:
                return

            self._check_deadline(
                deadline, message="Timed out waiting for networking to be ready."
            )
            sleep(retry_wait)

    def _setup_wait_for_system_ready(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        deadline: Optional[float] = None,
    ) -> None:
        """Wait until system is ready.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks.
        :param deadline: Optional time.time() deadline.
        """
        logger.debug("Waiting for environment to be ready...")

        self._check_deadline(deadline)
        while True:
            proc = self._execute_run(
                executor,
                ["systemctl", "is-system-running"],
                capture_output=True,
                check=False,
                text=True,
            )

            running_state = proc.stdout.strip()
            if running_state in ["running", "degraded"]:
                return

            logger.debug("systemctl is-system-running status: %s", running_state)

            self._check_deadline(
                deadline, message="Timed out waiting for environment to be ready."
            )
            sleep(retry_wait)

    def _update_apt_sources(
        self, *, executor: Executor, deadline: Optional[float], codename: str
    ) -> None:
        """Update the codename in the apt source config files.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        :param codename: New codename to use in apt source config files (i.e. 'lunar')
        """
        self._check_deadline(deadline)

        apt_source = "/etc/apt/sources.list"
        apt_source_dir = "/etc/apt/sources.list.d/"
        cloud_config = "/etc/cloud/cloud.cfg"

        # get the current ubuntu codename
        os_release = self._get_os_release(executor=executor, deadline=deadline)
        version_codename = os_release.get("VERSION_CODENAME")
        logger.debug("Updating apt sources from %r to %r.", version_codename, codename)

        # replace all occurrences of the codename in the `sources.list` file
        sed_command = ["sed", "-i", f"s/{version_codename}/{codename}/g"]
        try:
            self._execute_run(executor, sed_command + [apt_source])
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief=f"Failed to update {apt_source!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        # if cloud-init and cloud.cfg isn't present, then raise an error
        try:
            self._execute_run(executor, ["test", "-s", cloud_config])
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief=(
                    f"Could not update {cloud_config!r} because it is empty or "
                    "does not exist."
                ),
                details=errors.details_from_called_process_error(error),
            ) from error

        # update cloud.cfg to prevent the sources.list file from being reset
        logger.debug("Updating %r to preserve apt sources.", cloud_config)
        try:
            self._execute_run(
                executor,
                # 'aapt' is not a typo, the first 'a' is the sed command to append
                # this is a shlex-compatible way to append to a file
                ["sed", "-i", "$ aapt_preserve_sources_list: true", cloud_config],
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief=f"Failed to update {cloud_config!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        # running `find` and `sed` as two separate calls may appear unoptimized,
        # but these shell commands will pass through `shlex.join()` before being
        # executed, which means one-liners like `find -exec sed` or
        # `find | xargs sed` cannot be used

        try:
            additional_source_files = self._execute_run(
                executor,
                ["find", apt_source_dir, "-type", "f", "-name", "*.list"],
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief=f"Failed to find apt source files in {apt_source_dir!r}.",
                details=errors.details_from_called_process_error(error),
            ) from error

        # if there are config files in `sources.list.d/`, then update them
        if additional_source_files:
            try:
                self._execute_run(executor, sed_command + [apt_source_dir + "*.list"])
            except subprocess.CalledProcessError as error:
                raise BaseConfigurationError(
                    brief=f"Failed to update apt source files in {apt_source_dir!r}.",
                    details=errors.details_from_called_process_error(error),
                ) from error

    def _update_compatibility_tag(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Update the compatibility_tag in the instance config."""
        InstanceConfiguration.update(
            executor=executor,
            data={"compatibility_tag": self.compatibility_tag},
            config_path=self.instance_config_path,
        )
        self._check_deadline(deadline)

    def _update_setup_status(
        self, *, executor: Executor, deadline: Optional[float], status: bool
    ) -> None:
        """Update the instance config to indicate the status of the setup.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        :param status: True if the setup is complete, False otherwise.
        """
        InstanceConfiguration.update(
            executor=executor,
            data={"setup": status},
            config_path=self.instance_config_path,
        )
        self._check_deadline(deadline)

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

        Guarantees provided by this wait:

            - networking available (IP & DNS resolution)

            - system services are started and ready

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks (if
            required).
        :param timeout: Timeout in seconds.

        :raises ProviderError: on timeout or unexpected error.
        """
        if timeout is not None:
            deadline: Optional[float] = time.time() + timeout
        else:
            deadline = None

        self._setup_wait_for_system_ready(
            executor=executor,
            retry_wait=retry_wait,
            deadline=deadline,
        )
        self._setup_wait_for_network(
            executor=executor,
            retry_wait=retry_wait,
            deadline=deadline,
        )


# Backward compatible, will be removed in 2.0
default_command_environment = BuilddBase.default_command_environment
