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

"""Buildd image(s)."""
import enum
import io
import logging
import pathlib
import subprocess
import time
from textwrap import dedent
from time import sleep
from typing import Any, Dict, Optional

from craft_providers import Base, Executor, errors
from craft_providers.util.os_release import parse_os_release

from . import craft_config
from .errors import BaseCompatibilityError, BaseConfigurationError

logger = logging.getLogger(__name__)


def default_command_environment() -> Dict[str, Optional[str]]:
    """Provide default command environment dictionary.

    The minimum environment for the buildd image to be configured and
    function properly.

    :returns: Dictionary of environment key/values.
    """
    return dict(
        PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
    )


class BuilddBaseAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = "16.04"
    BIONIC = "18.04"
    FOCAL = "20.04"


class BuilddBase(Base):
    """Support for Ubuntu minimal buildd images.

    :param alias: Base alias / version.
    :param hostname: Hostname to configure.
    :param craft_config_path: Path to persistent environment configuration used
        for compatibility checks.
    :param command_environment: Additional environment to configure for command.
        If specifying an environment, default_command_environment() is provided
        for the minimum required environment configuration.
    :param compatibility_tag: Tag/Version for variant of build configuration and
        setup.  Any change to this version would indicate that prior [versioned]
        instances are incompatible and must be cleaned.  As such, any new value
        should be unique to old values (e.g. incrementing).
    """

    def __init__(
        self,
        *,
        alias: BuilddBaseAlias,
        craft_config_path: pathlib.Path = pathlib.Path("/etc/craft.conf"),
        compatibility_tag: str = "craft-buildd-image-v0",
        hostname: str = "craft-buildd-instance",
        command_environment: Optional[Dict[str, Optional[str]]] = None,
    ):
        super().__init__(name=alias.value)

        self.alias: BuilddBaseAlias = alias
        self.compatibility_tag = compatibility_tag
        self.craft_config_path = craft_config_path
        self.hostname: str = hostname

        if command_environment is not None:
            self.command_environment = command_environment
        else:
            self.command_environment = default_command_environment()

    def ensure_compatible(self, *, executor: Executor) -> None:
        """Ensure exector target is compatible with image.

        :param executor: Executor for target container.
        """
        self._ensure_image_version_compatible(executor=executor)
        self._ensure_os_compatible(executor=executor)

    def _ensure_image_version_compatible(self, *, executor: Executor) -> None:
        config = craft_config.load(
            executor=executor,
            config_path=self.craft_config_path,
            env=self.command_environment,
        )

        # If no config has been written, assume it is compatible (likely an
        # unfinished setup).
        if config is None:
            return

        if config.compatibility_tag != self.compatibility_tag:
            raise BaseCompatibilityError(
                reason=(
                    "Expected image compatibility tag "
                    f"{self.compatibility_tag!r}, found {config.compatibility_tag!r}"
                )
            )

    def _ensure_os_compatible(self, *, executor: Executor) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        """
        os_release = self._read_os_release(executor=executor)

        os_id = os_release.get("NAME")
        if os_id != "Ubuntu":
            raise BaseCompatibilityError(
                reason=f"Exepcted OS 'Ubuntu', found {os_id!r}"
            )

        compat_version_id = self.alias.value
        version_id = os_release.get("VERSION_ID")
        if version_id != compat_version_id:
            raise BaseCompatibilityError(
                reason=f"Expected OS version {compat_version_id!r}, found {version_id!r}"
            )

    def _read_os_release(self, *, executor: Executor) -> Dict[str, Any]:
        """Read & parse /etc/os-release.

        :param executor: Executor for target.

        :returns: Dictionary of parsed /etc/os-release.

        :raises BaseConfigurationError: on error.
        """
        try:
            proc = executor.execute_run(
                command=["cat", "/etc/os-release"],
                capture_output=True,
                check=True,
                text=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to read /etc/os-release.",
                details=errors.details_from_called_process_error(error),
            ) from error

        return parse_os_release(proc.stdout)

    def setup(self, *, executor: Executor) -> None:
        """Configure buildd image to minimum baseline.

        Install & wait for ready:

            - hostname

            - networking (ip & dns)

            - apt cache

            - snapd

        :param executor: Executor for target container.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        self.ensure_compatible(executor=executor)
        self._setup_environment(executor=executor)
        self._setup_wait_for_system_ready(executor=executor)
        self._setup_craft_image_config(executor=executor)
        self._setup_hostname(executor=executor)
        self._setup_resolved(executor=executor)
        self._setup_networkd(executor=executor)
        self._setup_wait_for_network(executor=executor)
        self._setup_apt(executor=executor)
        self._setup_snapd(executor=executor)

    def _setup_apt(self, *, executor: Executor) -> None:
        """Configure apt & update cache.

        :param executor: Executor for target container.
        """
        executor.create_file(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00no-recommends"),
            content=io.BytesIO('Apt::Install-Recommends "false";\n'.encode()),
            file_mode="0644",
        )

        try:
            executor.execute_run(
                ["apt-get", "update"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update apt cache.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            executor.execute_run(
                ["apt-get", "install", "-y", "apt-utils"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to install apt-utils.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_craft_image_config(self, *, executor: Executor) -> None:
        config = craft_config.CraftBaseConfig(compatibility_tag=self.compatibility_tag)

        craft_config.save(
            executor=executor,
            config=config,
            config_path=self.craft_config_path,
        )

    def _setup_environment(self, *, executor: Executor) -> None:
        """Configure hostname, installing /etc/hostname.

        :param executor: Executor for target container.
        """
        content = (
            "\n".join(
                [
                    f"{k}={v}"
                    for k, v in self.command_environment.items()
                    if v is not None
                ]
            )
            + "\n"
        ).encode()

        executor.create_file(
            destination=pathlib.Path("/etc/environment"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    def _setup_hostname(self, *, executor: Executor) -> None:
        """Configure hostname, installing /etc/hostname.

        :param executor: Executor for target container.
        """
        executor.create_file(
            destination=pathlib.Path("/etc/hostname"),
            content=io.BytesIO((self.hostname + "\n").encode()),
            file_mode="0644",
        )

        try:
            executor.execute_run(
                ["hostname", "-F", "/etc/hostname"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set hostname.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_networkd(self, *, executor: Executor) -> None:
        """Configure networkd and start it.

        Installs eth0 network configuration using ipv4.

        :param executor: Executor for target container.
        """
        executor.create_file(
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
            executor.execute_run(
                ["systemctl", "enable", "systemd-networkd"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )

            executor.execute_run(
                ["systemctl", "restart", "systemd-networkd"],
                check=True,
                capture_output=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-networkd.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_resolved(self, *, executor: Executor) -> None:
        """Configure system-resolved to manage resolve.conf.

        :param executor: Executor for target container.
        :param timeout_secs: Timeout in seconds.
        """
        try:
            executor.execute_run(
                [
                    "ln",
                    "-sf",
                    "/run/systemd/resolve/resolv.conf",
                    "/etc/resolv.conf",
                ],
                check=True,
                capture_output=True,
                env=self.command_environment,
            )

            executor.execute_run(
                ["systemctl", "enable", "systemd-resolved"],
                check=True,
                capture_output=True,
                env=self.command_environment,
            )

            executor.execute_run(
                ["systemctl", "restart", "systemd-resolved"],
                check=True,
                capture_output=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup systemd-resolved.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_snapd(self, *, executor: Executor) -> None:
        """Install snapd and dependencies and wait until ready.

        :param executor: Executor for target container.
        :param timeout_secs: Timeout in seconds.
        """
        try:
            executor.execute_run(
                [
                    "apt-get",
                    "install",
                    "-y",
                    "fuse",
                    "udev",
                ],
                check=True,
                capture_output=True,
                env=self.command_environment,
            )

            executor.execute_run(
                ["systemctl", "enable", "systemd-udevd"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
            executor.execute_run(
                ["systemctl", "start", "systemd-udevd"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
            executor.execute_run(
                ["apt-get", "install", "-y", "snapd"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
            executor.execute_run(
                ["systemctl", "start", "snapd.socket"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )

            # Restart, not start, the service in case the environment
            # has changed and the service is already running.
            executor.execute_run(
                ["systemctl", "restart", "snapd.service"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
            executor.execute_run(
                ["snap", "wait", "system", "seed.loaded"],
                capture_output=True,
                check=True,
                env=self.command_environment,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup snapd.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_wait_for_network(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Wait until networking is ready.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks.
        :param timeout: Optional time.time() stamp to timeout after.
        """
        logger.debug("Waiting for networking to be ready...")

        while timeout is None or time.time() < timeout:
            proc = executor.execute_run(
                ["getent", "hosts", "snapcraft.io"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self.command_environment,
            )
            if proc.returncode == 0:
                break

            sleep(retry_wait)
        else:
            raise BaseConfigurationError(
                brief="Timed out waiting for networking to be ready.",
            )

    def _setup_wait_for_system_ready(
        self,
        *,
        executor: Executor,
        retry_wait: float = 0.25,
        timeout: Optional[float] = None,
    ) -> None:
        """Wait until system is ready.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks.
        :param timeout: Optional time.time() stamp to timeout after.
        """
        logger.debug("Waiting for environment to be ready...")
        while timeout is None or time.time() < timeout:
            proc = executor.execute_run(
                ["systemctl", "is-system-running"],
                capture_output=True,
                check=False,
                env=self.command_environment,
                text=True,
            )

            running_state = proc.stdout.strip()
            if running_state in ["running", "degraded"]:
                break

            logger.debug("systemctl is-system-running status: %s", running_state)
            sleep(retry_wait)
        else:
            raise BaseConfigurationError(
                brief="Timed out waiting for environment to be ready.",
            )

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
        self._setup_wait_for_system_ready(
            executor=executor, retry_wait=retry_wait, timeout=timeout
        )
        self._setup_wait_for_network(
            executor=executor, retry_wait=retry_wait, timeout=timeout
        )
