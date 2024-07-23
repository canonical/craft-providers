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

"""Craft provider errors."""
import dataclasses
import shlex
import subprocess
from typing import List, Optional, Union


def details_from_command_error(
    *,
    cmd: List[str],
    returncode: int,
    stdout: Optional[Union[bytes, str]] = None,
    stderr: Optional[Union[bytes, str]] = None,
) -> str:
    """Create a consistent ProviderError from command errors.

    stdout and stderr, if provided, will be stringified using its object
    representation.  This method does not decode byte strings.

    :param cmd: Command executed.
    :param returncode: Command exit code.
    :param stdout: Optional stdout to include.
    :param stderr: Optional stderr to include.

    :returns: Details string.
    """
    cmd_string = shlex.join(cmd)

    details = [
        f"* Command that failed: {cmd_string!r}",
        f"* Command exit code: {returncode}",
    ]

    if stdout:
        details.append(f"* Command output: {stdout!r}")

    if stderr:
        details.append(f"* Command standard error output: {stderr!r}")

    return "\n".join(details)


def details_from_called_process_error(
    error: subprocess.CalledProcessError,
) -> str:
    """Create a consistent ProviderError from command errors.

    :param error: CalledProcessError.

    :returns: Details string.
    """
    return details_from_command_error(
        cmd=error.cmd,
        stdout=error.stdout,
        stderr=error.stderr,
        returncode=error.returncode,
    )


@dataclasses.dataclass
class ProviderError(Exception):
    """Unexpected error.

    :param brief: Brief description of error.
    :param details: Detailed information.
    :param resolution: Recommendation, if any.
    """

    brief: str
    details: Optional[str] = None
    resolution: Optional[str] = None

    def __str__(self) -> str:
        parts = [self.brief]

        if self.details:
            parts.append(self.details)

        if self.resolution:
            parts.append(self.resolution)

        return "\n".join(parts)


class BaseConfigurationError(ProviderError):
    """Error configuring the base."""


class BaseCompatibilityError(ProviderError):
    """Base configuration compatibility error.

    :param reason: Reason for incompatibility.
    """

    def __init__(self, reason: str, *, details: Optional[str] = None) -> None:
        self.reason = reason

        brief = f"Incompatible base detected: {reason}."
        resolution = "Clean incompatible instance and retry the requested operation."

        super().__init__(brief=brief, details=details, resolution=resolution)


class NetworkError(ProviderError):
    """Network error when configuring the base."""

    def __init__(self) -> None:
        brief = "A network related operation failed in a context of no network access."
        # XXX Facundo 2022-12-13: need to improve the URL here once
        # we have the online docs updated
        url = "https://canonical-craft-providers.readthedocs-hosted.com/en/latest/explanation/"
        resolution = (
            "Verify that the environment has internet connectivity; "
            f"see {url} for further reference."
        )
        super().__init__(brief=brief, resolution=resolution)
