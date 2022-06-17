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

"""Multipass Provider Readiness Checks."""

import logging

from . import errors
from .installer import is_installed
from .multipass import Multipass

logger = logging.getLogger(__name__)


def ensure_multipass_is_ready(*, multipass: Multipass = Multipass()) -> None:
    """Ensure Multipass is ready for use.

    :raises MultipassError: on error.
    """
    if not is_installed():
        raise errors.MultipassError(
            brief="Multipass is required, but not installed.",
            resolution="Visit https://multipass.run for instructions on "
            "installing Multipass for your operating system.",
        )

    if not multipass.is_supported_version():
        version = multipass.version()
        min_version = multipass.minimum_required_version
        raise errors.MultipassError(
            brief=(
                f"Multipass {version!r} does not meet the"
                f" minimum required version {min_version!r}."
            ),
            resolution="Visit https://multipass.run for instructions on "
            "installing Multipass for your operating system.",
        )
