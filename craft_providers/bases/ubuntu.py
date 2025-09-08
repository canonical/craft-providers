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

import csv
import datetime
import enum
import importlib.resources
import io
import logging
import pathlib
import subprocess
from functools import total_ordering
from textwrap import dedent

import requests
from typing_extensions import override

from craft_providers import const
from craft_providers.actions.snap_installer import Snap
from craft_providers.base import Base
from craft_providers.errors import (
    BaseCompatibilityError,
    BaseConfigurationError,
    details_from_called_process_error,
)
from craft_providers.executor import Executor
from craft_providers.util import retry

logger = logging.getLogger(__name__)


@total_ordering
class BuilddBaseAlias(enum.Enum):
    """Mappings for supported buildd images."""

    XENIAL = "16.04"
    BIONIC = "18.04"
    FOCAL = "20.04"
    JAMMY = "22.04"
    NOBLE = "24.04"
    ORACULAR = "24.10"
    PLUCKY = "25.04"
    QUESTING = "25.10"
    DEVEL = "devel"

    def __lt__(self, other) -> bool:  # noqa: ANN001
        # Devels are the greatest, luckily 'd' > [0-9]
        return self.value < other.value


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
    :param use_default_packages: Optional bool to enable/disable default packages.
    :param cache_path: Optional path to the shared cache directory. If this is
        provided, shared cache directories will be mounted as appropriate.
    """

    compatibility_tag: str = f"buildd-{Base.compatibility_tag}"

    @override
    def __init__(
        self,
        *,
        alias: BuilddBaseAlias,
        compatibility_tag: str | None = None,
        environment: dict[str, str | None] | None = None,
        hostname: str = "craft-buildd-instance",
        snaps: list[Snap] | None = None,
        packages: list[str] | None = None,
        use_default_packages: bool = True,
        cache_path: pathlib.Path | None = None,
    ) -> None:
        # ignore enum subclass (see https://github.com/microsoft/pyright/issues/6750)
        self.alias: BuilddBaseAlias = alias  # pyright: ignore  # noqa: PGH003

        self._cache_path = cache_path

        if environment is None:
            self._environment = self.default_command_environment()
        else:
            self._environment = environment

        # ensure apt installs are always non-interactive
        self._environment.update(
            {
                "DEBIAN_FRONTEND": "noninteractive",
                "DEBCONF_NONINTERACTIVE_SEEN": "true",
                "DEBIAN_PRIORITY": "critical",
            }
        )

        if compatibility_tag:
            self.compatibility_tag = compatibility_tag

        self._set_hostname(hostname)

        self._packages: list[str] | None = []
        if use_default_packages:
            self._packages.extend(
                [
                    "apt-utils",
                    "build-essential",
                    "curl",
                    "fuse",
                    "udev",
                    "python3",
                    "python3-dev",
                    "python3-pip",
                    "python3-wheel",
                    "python3-setuptools",
                ]
            )

        if packages:
            self._packages.extend(packages)

        self._snaps = snaps

    def _disable_automatic_apt(self, executor: Executor) -> None:
        """Disable automatic apt actions.

        This should happen as soon as possible in the instance overall setup,
        to reduce the chances of an automatic apt work being triggered during
        the setup itself (because it includes apt work which may clash
        the triggered unattended jobs).
        """
        # set the verification frequency in 10000 days and disable the upgrade
        content = dedent(
            """\
            APT::Periodic::Update-Package-Lists "10000";
            APT::Periodic::Unattended-Upgrade "0";
        """
        ).encode()
        executor.push_file_io(
            destination=pathlib.PurePosixPath("/etc/apt/apt.conf.d/20auto-upgrades"),
            content=io.BytesIO(content),
            file_mode="0644",
        )

    @override
    def _ensure_os_compatible(self, executor: Executor) -> None:
        """Ensure OS is compatible with Base."""
        os_release = self._get_os_release(executor=executor)

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
                    f"Expected OS version {compat_version_id!r}, found {version_id!r}"
                )
            )

    @override
    def _post_setup_os(self, executor: Executor) -> None:
        """Ubuntu specific post-setup OS tasks."""
        self._disable_automatic_apt(executor=executor)

    @override
    def _setup_network(self, executor: Executor) -> None:
        """Set up the basic network with systemd-networkd and systemd-resolved."""
        self._setup_hostname(executor=executor)
        self._setup_resolved(executor=executor)
        self._setup_networkd(executor=executor)

    @override
    def _pre_setup_packages(self, executor: Executor) -> None:
        """Configure apt, update database."""
        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00no-recommends"),
            content=io.BytesIO(b'APT::Install-Recommends "false";\n'),
            file_mode="0644",
        )

        executor.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/00update-errors"),
            content=io.BytesIO(b'APT::Update::Error-Mode "any";\n'),
            file_mode="0644",
        )

        self._update_eol_sources(executor)

        try:
            self._execute_run(
                ["apt-get", "update"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update apt cache.",
                details=details_from_called_process_error(error),
            ) from error

    def _update_eol_sources(self, executor: Executor) -> None:
        """Update sources for EOL (end of life) bases.

        Only updates sources if the base is past its EOL date and is available on https://old-releases.ubuntu.com.

        :param executor: Executor for the instance.

        :raises BaseConfigurationError: If base's EOL status can't be determined.
        :raises BaseConfigurationError: If the sources can't be updated in the instance.
        """
        codename = self._get_codename(executor)

        if not self._is_eol(codename):
            logger.debug(
                f"Not updating EOL sources because {self.alias.value} isn't EOL."
            )
            return

        if not self._is_old_release(codename):
            logger.debug(
                f"Not updating EOL sources because {self.alias.value} isn't on https://old-releases.ubuntu.com."
            )
            return

        logger.debug("Updating EOL sources.")

        with importlib.resources.path(
            "craft_providers.util", "sources.sh"
        ) as sources_script:
            executor.push_file(
                source=sources_script,
                destination=pathlib.Path("/tmp/craft-sources.sh"),  # noqa: S108
            )

        # use a bash script because there isn't an easy way to modify files in an instance (#132)
        try:
            self._execute_run(
                ["bash", "/tmp/craft-sources.sh"],  # noqa: S108
                executor=executor,
                timeout=self._timeout_simple,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update EOL sources.",
                details=details_from_called_process_error(error),
            ) from error

    def _get_codename(self, executor: Executor) -> str:
        """Get the codename for an instance.

        :param executor: Executor for the instance.

        :returns: The instance's Ubuntu codename.

        :raises BaseConfigurationError: If the codename can't be determined.
        """
        os_release = self._get_os_release(executor=executor)
        codename = os_release.get("UBUNTU_CODENAME")
        if not codename:
            raise BaseConfigurationError(
                brief="Couldn't find Ubuntu codename in OS release data.",
                details=f"OS release data: {os_release}.",
            )
        return codename

    def _is_old_release(self, codename: str) -> bool:
        """Check if a base is on the old-releases archive.

        :param codename: The instance's Ubuntu codename.

        :returns: True if the base is on the old-releases archive.
        """
        url = "https://old-releases.ubuntu.com"
        slug = f"/ubuntu/dists/{codename}/"

        def _request(timeout: float) -> requests.Response:  # noqa: ARG001
            return requests.head(url + slug, allow_redirects=True, timeout=5)

        logger.debug(f"Checking for {self.alias.value} ({codename}) on {url}.")
        response = retry.retry_until_timeout(
            timeout=self._timeout_simple or const.TIMEOUT_SIMPLE,
            retry_wait=self._retry_wait,
            func=_request,
            error=BaseConfigurationError(brief=f"Failed to get {url + slug}."),
        )

        if response.status_code == 200:  # noqa: PLR2004
            logger.debug(f"{self.alias.value} is available on {url}.")
            return True

        logger.debug(f"{self.alias.value} isn't available on {url}.")
        return False

    def _is_eol(self, codename: str) -> bool:
        """Check if a base is EOL.

        :param codename: The instance's Ubuntu codename.

        :returns: True if the base is EOL.

        :raises BaseConfigurationError: If the EOL data can't be determined.
        """
        logger.debug(f"Getting EOL data for {self.alias.value} ({codename}).")
        with importlib.resources.path(
            "craft_providers.data", "ubuntu.csv"
        ) as distro_info_file:
            reader = csv.DictReader(io.StringIO(distro_info_file.read_text("utf-8")))

        for row in reader:
            if row.get("series") == codename:
                eol_date = row["eol"]
                break
        else:
            raise BaseConfigurationError(
                brief=f"Couldn't get EOL data for {self.alias.value}."
            )

        current_date = datetime.date.today().isoformat()

        if current_date > eol_date:
            logger.debug(f"{self.alias.value} is EOL.")
            return True

        logger.debug(f"{self.alias.value} isn't EOL.")
        return False

    @override
    def _setup_packages(self, executor: Executor) -> None:
        """Use apt install required packages and user-defined packages."""
        try:
            self._execute_run(
                ["apt-get", "-y", "dist-upgrade"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to update packages.",
                details=details_from_called_process_error(error),
            ) from error
        if not self._packages:
            return
        try:
            command = ["apt-get", "install", "-y", *self._packages]
            self._execute_run(
                command,
                executor=executor,
                verify_network=True,
                timeout=self._timeout_unpredictable,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to install packages.",
                details=details_from_called_process_error(error),
            ) from error

    @override
    def _setup_snapd(self, executor: Executor) -> None:
        """Install snapd and dependencies and wait until ready."""
        try:
            self._execute_run(
                ["apt-get", "install", "-y", "snapd"],
                executor=executor,
                verify_network=True,
                timeout=self._timeout_complex,
            )
        except subprocess.CalledProcessError as error:
            raise BaseConfigurationError(
                brief="Failed to setup snapd.",
                details=details_from_called_process_error(error),
            ) from error

    @override
    def _clean_up(self, executor: Executor) -> None:
        self._execute_run(
            ["apt-get", "autoremove", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )
        self._execute_run(
            ["apt-get", "clean", "-y"],
            executor=executor,
            timeout=self._timeout_complex,
        )


# Backward compatible, will be removed in 2.0
default_command_environment = BuilddBase.default_command_environment
