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
"""Tests for craft_providers helper utilities."""
from unittest import mock

import pytest
from craft_providers.util import retry


@pytest.fixture(params=range(1, 6), ids=[f"timeout_{i}ms" for i in range(1, 6)])
def timeout(request):
    return request.param * 0.001


@pytest.fixture(params=range(5), ids=[f"wait_{i}us" for i in range(5)])
def retry_wait(request):
    """A parametrized fixture of times to wait before retrying, in microseconds"""
    return request.param * 0.000_001


def test_retry_until_timeout_success(failure_count, retry_wait):
    failures = [Exception()] * failure_count
    mock_function = mock.Mock(side_effect=[*failures, None])

    retry.retry_until_timeout(1, retry_wait, mock_function)

    assert len(mock_function.mock_calls) == failure_count + 1


@pytest.mark.parametrize("error_cls", [TimeoutError, Exception, ValueError])
def test_retry_until_timeout_times_out(retry_wait, timeout, mock_time_sleep, error_cls):
    mock_function = mock.Mock(side_effect=Exception())

    with pytest.raises(error_cls):
        retry.retry_until_timeout(timeout, retry_wait, mock_function, error=error_cls())

    mock_function.assert_called()

    mock_time_sleep.assert_called_with(retry_wait)
