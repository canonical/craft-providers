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

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

T = TypeVar("T")


def retry_until_timeout(
    timeout: float,
    retry_wait: float,
    func: Callable[[float], T],
    *,
    error: Exception | None = TimeoutError(),
) -> T:
    """Re-run a function until it either succeeds or it times out.

    :param timeout: The length of time (in seconds) before timeout.
    :param retry_wait: The length of time (in seconds) before retrying.
    :param func: The callable. May only take a timeout parameter.
        Must raise an exception on failure, may return anything on success.
    :param error: Exception to raise on timeout or None to pass the error unchanged.
    :returns: The result of the function
    :raises: the passed error from the last exception
    """
    deadline = time.monotonic() + timeout
    soft_deadline = deadline - retry_wait

    while (now := time.monotonic()) < soft_deadline:
        try:
            return func(deadline - now)
        except Exception:
            if time.monotonic() < soft_deadline:
                time.sleep(retry_wait)
    try:
        return func(retry_wait)
    except Exception as exc:
        if error is None:
            raise
        raise error from exc
