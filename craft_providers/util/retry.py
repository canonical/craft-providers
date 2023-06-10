#
# Copyright 2023 Canonical Ltd.
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
"""Helper utilities for craft_providers."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


def retry_until_timeout(
    timeout: float,
    retry_wait: float,
    func: Callable[[float], T],
    *,
    error: Exception = TimeoutError(),
) -> T:
    """Re-run a function until it either succeeds or it times out.

    :param timeout: The length of time (in seconds) before timeout.
    :param retry_wait: The length of time (in seconds) before retrying.
    :param func: The callable. May only take a timeout parameter
    :param error: Exception to raise on timeout
    :returns: The result of the function
    :raises: TimeoutError from the last exception
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            return func(deadline - time.monotonic())
        except Exception:
            if time.monotonic() < deadline - retry_wait:
                time.sleep(retry_wait)
    try:
        return func(retry_wait)
    except Exception as exc:
        raise error from exc
