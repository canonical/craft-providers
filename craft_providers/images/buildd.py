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

"""Buildd image(s)."""
import enum
import logging
import pathlib
import subprocess
from textwrap import dedent
from time import sleep
from typing import Any, Dict, Final, Optional

import yaml

from craft_providers import Executor, Image
from craft_providers.images import errors
from craft_providers.util.os_release import parse_os_release

logger = logging.getLogger(__name__)


class BuilddImageAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = 16.04
    BIONIC = 18.04
    FOCAL = 20.04


class BuilddImage(Image):
    """Support for Ubuntu minimal buildd images.

    :param alias: Image alias / version.
    :param hostname: Hostname to configure.
    :param compatibility_tag: Version of image setup used to ensure compatibility
        for re-used instances.  Any change to this version would indicate that
        prior [versioned] instances are incompatible and must be cleaned.  As
        such, any new value should be unique to old values (e.g. incrementing).
    """

    def __init__(
        self,
        *,
        alias: BuilddImageAlias,
        compatibility_tag: str = "craft-buildd-image-v0",
        hostname: str = "craft-buildd-instance",
    ):
        super().__init__(compatibility_tag=compatibility_tag, name=str(alias.value))

        self.alias: Final[BuilddImageAlias] = alias
        self.hostname: Final[str] = hostname

    def _read_craft_image_config(
        self, *, executor: Executor
    ) -> Optional[Dict[str, Any]]:
        try:
            proc = executor.execute_run(
                command=["cat", "/etc/craft-image.conf"],
                check=True,
                stdout=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            return None

        return yaml.load(proc.stdout, Loader=yaml.SafeLoader)

    def _write_craft_image_config(self, *, executor: Executor) -> None:
        conf = {"compatibility_tag": self.compatibility_tag}
        executor.create_file(
            destination=pathlib.Path("/etc/craft-image.conf"),
            content=yaml.dump(conf).encode(),
            file_mode="0644",
        )

    def _read_os_release(self, *, executor: Executor) -> Optional[Dict[str, Any]]:
        try:
            proc = executor.execute_run(
                command=["cat", "/etc/os-release"],
                check=False,
                stdout=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            return None

        return parse_os_release(proc.stdout.decode())

    def ensure_compatible(self, *, executor: Executor) -> None:
        """Ensure exector target is compatible with image.

        :param executor: Executor for target container.
        """
        self._ensure_image_version_compatible(executor=executor)
        self._ensure_os_compatible(executor=executor)

    def _ensure_image_version_compatible(self, *, executor: Executor) -> None:
        craft_config = self._read_craft_image_config(executor=executor)

        # If no config has been written, assume it is compatible (likely an unfinished setup).
        if craft_config is None:
            return

        tag = craft_config.get("compatibility_tag")
        if tag != self.compatibility_tag:
            raise errors.CompatibilityError(
                reason=(
                    "Expected image compatibility tag "
                    f"{self.compatibility_tag!r}, found '{tag!s}'"
                )
            )

    def _ensure_os_compatible(self, *, executor: Executor) -> None:
        os_release = self._read_os_release(executor=executor)
        if os_release is None:
            raise errors.CompatibilityError(reason="/etc/os-release not found")

        logger.warning(os_release)
        os_id = os_release.get("NAME")
        if os_id != "Ubuntu":
            raise errors.CompatibilityError(
                reason=f"Exepcted OS 'Ubuntu', found {os_id!r}"
            )

        compat_version_id = str(self.alias.value)
        version_id = os_release.get("VERSION_ID")
        if version_id != compat_version_id:
            raise errors.CompatibilityError(
                reason=f"Expected OS version {compat_version_id!r}, found {version_id!r}"
            )

    def setup(self, *, executor: Executor) -> None:
        """Configure buildd image to minimum baseline.

        Install & wait for ready:
        - hostname
        - networking (ip & dns)
        - apt cache
        - snapd

        :param executor: Executor for target container.
        """
        self.ensure_compatible(executor=executor)
        self._setup_wait_for_system_ready(executor=executor)
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
        executor.execute_run(command=["apt-get", "update"], check=True)

    def _setup_hostname(self, *, executor: Executor) -> None:
        """Configure hostname, installing /etc/hostname.

        :param executor: Executor for target container.
        """
        executor.create_file(
            destination=pathlib.Path("/etc/hostname"),
            content=self.hostname.encode(),
            file_mode="0644",
        )

    def _setup_networkd(self, *, executor: Executor) -> None:
        """Configure networkd and start it.

        Installs eth0 network configuration using ipv4.

        :param executor: Executor for target container.
        """
        executor.create_file(
            destination=pathlib.Path("/etc/systemd/network/10-eth0.network"),
            content=dedent(
                """
                [Match]
                Name=eth0

                [Network]
                DHCP=ipv4
                LinkLocalAddressing=ipv6

                [DHCP]
                RouteMetric=100
                UseMTU=true
                """
            ).encode(),
            file_mode="0644",
        )

        executor.execute_run(
            command=["systemctl", "enable", "systemd-networkd"], check=True
        )

        executor.execute_run(
            command=["systemctl", "restart", "systemd-networkd"], check=True
        )

    def _setup_resolved(self, *, executor: Executor) -> None:
        """Configure system-resolved to manage resolve.conf.

        :param executor: Executor for target container.
        :param timeout_secs: Timeout in seconds.
        """
        executor.execute_run(
            command=[
                "ln",
                "-sf",
                "/run/systemd/resolve/resolv.conf",
                "/etc/resolv.conf",
            ],
            check=True,
        )

        executor.execute_run(
            command=["systemctl", "enable", "systemd-resolved"], check=True
        )

        executor.execute_run(
            command=["systemctl", "restart", "systemd-resolved"], check=True
        )

    def _setup_snapd(self, *, executor: Executor) -> None:
        """Install snapd and dependencies and wait until ready.

        :param executor: Executor for target container.
        :param timeout_secs: Timeout in seconds.
        """
        executor.execute_run(
            command=[
                "apt-get",
                "install",
                "fuse",
                "udev",
                "--yes",
            ],
            check=True,
        )

        executor.execute_run(
            command=["systemctl", "enable", "systemd-udevd"], check=True
        )
        executor.execute_run(
            command=["systemctl", "start", "systemd-udevd"], check=True
        )
        executor.execute_run(
            command=["apt-get", "install", "snapd", "--yes"], check=True
        )
        executor.execute_run(command=["systemctl", "start", "snapd.socket"], check=True)
        executor.execute_run(
            command=["systemctl", "start", "snapd.service"], check=True
        )
        executor.execute_run(
            command=["snap", "wait", "system", "seed.loaded"], check=True
        )

    def _setup_wait_for_network(
        self, *, executor: Executor, timeout_secs: int = 60
    ) -> None:
        """Wait until networking is ready.

        :param executor: Executor for target container.
        :param timeout_secs: Timeout in seconds.
        """
        logger.info("Waiting for networking to be ready...")
        for _ in range(timeout_secs * 2):
            proc = executor.execute_run(
                command=["getent", "hosts", "snapcraft.io"], stdout=subprocess.DEVNULL
            )
            if proc.returncode == 0:
                break

            sleep(0.5)
        else:
            logger.warning("Failed to setup networking.")

    def _setup_wait_for_system_ready(
        self, *, executor: Executor, timeout_secs: int = 60
    ) -> None:
        """Wait until system is ready.

        :param executor: Executor for target container.
        :param timeout_secs: Timeout in seconds.
        """
        logger.info("Waiting for container to be ready...")
        for _ in range(timeout_secs * 2):
            proc = executor.execute_run(
                command=["systemctl", "is-system-running"], stdout=subprocess.PIPE
            )

            running_state = proc.stdout.decode().strip()
            if running_state in ["running", "degraded"]:
                break

            logger.debug("systemctl is-system-running: %s", running_state)
            sleep(0.5)
        else:
            logger.warning("Systemd failed to reach target before timeout.")
