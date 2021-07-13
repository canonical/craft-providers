#
# Copyright 2021 Canonical Ltd.
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

"""Buildd image(s)."""
import enum
import io
import logging
import pathlib
import subprocess
import time
from textwrap import dedent
from time import sleep
from typing import Dict, Optional, Type

from craft_providers import Base, Executor, errors
from craft_providers.util.os_release import parse_os_release

from . import instance_config
from .errors import BaseCompatibilityError, BaseConfigurationError

logger = logging.getLogger(__name__)


def default_command_environment() -> Dict[str, Optional[str]]:
    """Provide default command environment dictionary.

    The minimum environment for the buildd image to be configured and function
    properly.  This contains the default environment found in Ubuntu's
    /etc/environment, replaced with the "secure_path" defaults used by sudo for
    instantiating PATH.  In practice it really just means the PATH set by sudo.

    Default /etc/environment found in supported Ubuntu versions:
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin

    Default /etc/sudoers secure_path found in supported Ubuntu versions:
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

    :returns: Dictionary of environment key/values.
    """
    return dict(
        PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
    )


def _check_deadline(
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


class BuilddBaseAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = "16.04"
    BIONIC = "18.04"
    FOCAL = "20.04"


# pylint: disable=no-self-use
class BuilddBase(Base):
    """Support for Ubuntu minimal buildd images.

    :cvar compatibility_tag: Tag/Version for variant of build configuration and
        setup.  Any change to this version would indicate that prior [versioned]
        instances are incompatible and must be cleaned.  As such, any new value
        should be unique to old values (e.g. incrementing).  It is suggested to
        extend this tag, not overwrite it, e.g.: compatibilty_tag =
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
    """

    compatibility_tag: str = f"buildd-{Base.compatibility_tag}"
    instance_config_path: pathlib.Path = pathlib.Path("/etc/craft-instance.conf")
    instance_config_class: Type[
        instance_config.InstanceConfiguration
    ] = instance_config.InstanceConfiguration

    def __init__(
        self,
        *,
        alias: BuilddBaseAlias,
        environment: Optional[Dict[str, Optional[str]]] = None,
        hostname: str = "craft-buildd-instance",
    ):
        self.alias: BuilddBaseAlias = alias

        if environment is None:
            self.environment = default_command_environment()
        else:
            self.environment = environment

        self.hostname = hostname

    def _ensure_instance_config_compatible(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Ensure instance configuration is compatible.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        _check_deadline(deadline)
        config = self.instance_config_class.load(
            executor=executor,
            config_path=self.instance_config_path,
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

    def _ensure_os_compatible(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        """Ensure OS is compatible with Base.

        :raises BaseCompatibilityError: if instance is incompatible.
        :raises BaseConfigurationError: on other unexpected error.
        """
        try:
            # Replace encoding errors if it somehow occurs with utf-8. This
            # doesn't need to be perfect for checking compatibility.
            _check_deadline(deadline)
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

        os_release = parse_os_release(proc.stdout)

        os_name = os_release.get("NAME")
        if os_name != "Ubuntu":
            raise BaseCompatibilityError(
                reason=f"Exepcted OS 'Ubuntu', found {os_name!r}"
            )

        compat_version_id = self.alias.value
        version_id = os_release.get("VERSION_ID")
        if version_id != compat_version_id:
            raise BaseCompatibilityError(
                reason=f"Expected OS version {compat_version_id!r}, found {version_id!r}"
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

        self._ensure_os_compatible(
            executor=executor,
            deadline=deadline,
        )
        self._ensure_instance_config_compatible(executor=executor, deadline=deadline)
        self._setup_environment(
            executor=executor,
            deadline=deadline,
        )
        self._setup_wait_for_system_ready(
            executor=executor, deadline=deadline, retry_wait=retry_wait
        )
        self._setup_instance_config(executor=executor, deadline=deadline)
        self._setup_hostname(executor=executor, deadline=deadline)
        self._setup_resolved(executor=executor, deadline=deadline)
        self._setup_networkd(executor=executor, deadline=deadline)
        self._setup_wait_for_network(
            executor=executor, deadline=deadline, retry_wait=retry_wait
        )
        self._setup_apt(executor=executor, deadline=deadline)
        self._setup_snapd(executor=executor, deadline=deadline)

    def _setup_apt(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Configure apt & update cache.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        _check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00no-recommends"),
            content=io.BytesIO('APT::Install-Recommends "false";\n'.encode()),
            file_mode="0644",
        )

        _check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00update-errors"),
            content=io.BytesIO('APT::Update::Error-Mode "any";\n'.encode()),
            file_mode="0644",
        )

        try:
            _check_deadline(deadline)
            executor.execute_run(
                ["apt-get", "update"],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update apt cache.",
                details=errors.details_from_called_process_error(error),
            ) from error

        try:
            _check_deadline(deadline)
            executor.execute_run(
                ["apt-get", "install", "-y", "apt-utils"],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to install apt-utils.",
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

        _check_deadline(deadline)
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
        _check_deadline(deadline)
        executor.push_file_io(
            destination=pathlib.Path("/etc/hostname"),
            content=io.BytesIO((self.hostname + "\n").encode()),
            file_mode="0644",
        )

        try:
            _check_deadline(deadline)
            executor.execute_run(
                ["hostname", "-F", "/etc/hostname"],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to set hostname.",
                details=errors.details_from_called_process_error(error),
            ) from error

    def _setup_instance_config(
        self, *, executor: Executor, deadline: Optional[float]
    ) -> None:
        config = instance_config.InstanceConfiguration(
            compatibility_tag=self.compatibility_tag
        )

        config.save(
            executor=executor,
            config_path=self.instance_config_path,
        )
        _check_deadline(deadline)

    def _setup_networkd(self, *, executor: Executor, deadline: Optional[float]) -> None:
        """Configure networkd and start it.

        Installs eth0 network configuration using ipv4.

        :param executor: Executor for target container.
        :param deadline: Optional time.time() deadline.
        """
        _check_deadline(deadline)
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
            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "enable", "systemd-networkd"],
                capture_output=True,
                check=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "restart", "systemd-networkd"],
                check=True,
                capture_output=True,
            )
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
            _check_deadline(deadline)
            executor.execute_run(
                [
                    "ln",
                    "-sf",
                    "/run/systemd/resolve/resolv.conf",
                    "/etc/resolv.conf",
                ],
                check=True,
                capture_output=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "enable", "systemd-resolved"],
                check=True,
                capture_output=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "restart", "systemd-resolved"],
                check=True,
                capture_output=True,
            )
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
            _check_deadline(deadline)
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
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "enable", "systemd-udevd"],
                capture_output=True,
                check=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "start", "systemd-udevd"],
                capture_output=True,
                check=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["apt-get", "install", "-y", "snapd"],
                capture_output=True,
                check=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "start", "snapd.socket"],
                capture_output=True,
                check=True,
            )

            # Restart, not start, the service in case the environment
            # has changed and the service is already running.
            _check_deadline(deadline)
            executor.execute_run(
                ["systemctl", "restart", "snapd.service"],
                capture_output=True,
                check=True,
            )

            _check_deadline(deadline)
            executor.execute_run(
                ["snap", "wait", "system", "seed.loaded"],
                capture_output=True,
                check=True,
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
        deadline: Optional[float] = None,
    ) -> None:
        """Wait until networking is ready.

        :param executor: Executor for target container.
        :param retry_wait: Duration to sleep() between status checks.
        :param deadline: Optional time.time() deadline.
        """
        logger.debug("Waiting for networking to be ready...")

        _check_deadline(deadline)
        while True:
            proc = executor.execute_run(
                ["getent", "hosts", "snapcraft.io"],
                capture_output=True,
                check=False,
            )
            if proc.returncode == 0:
                return

            _check_deadline(
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

        _check_deadline(deadline)
        while True:
            proc = executor.execute_run(
                ["systemctl", "is-system-running"],
                capture_output=True,
                check=False,
                text=True,
            )

            running_state = proc.stdout.strip()
            if running_state in ["running", "degraded"]:
                return

            logger.debug("systemctl is-system-running status: %s", running_state)

            _check_deadline(
                deadline, message="Timed out waiting for environment to be ready."
            )
            sleep(retry_wait)

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
