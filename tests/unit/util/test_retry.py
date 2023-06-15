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
import time
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


def test_retry_until_timeout_success(
    failure_count, retry_wait, timeout, mock_time_sleep
):
    failures = [Exception()] * failure_count
    mock_function = mock.Mock(side_effect=[*failures, None])

    retry.retry_until_timeout(timeout, retry_wait, mock_function)

    assert len(mock_function.mock_calls) == failure_count + 1
    assert len(mock_time_sleep.mock_calls) >= failure_count


# @pytest.mark.no_mock_sleep
@pytest.mark.parametrize("retry_multiplier", [0.5, 0.8])
def test_retry_until_timeout_success_longish_retry(timeout, retry_multiplier):
    """retry_wait is more than half the timeout we always run twice."""
    retry_wait = timeout * retry_multiplier
    mock_function = mock.Mock(side_effect=[Exception(), None])

    retry.retry_until_timeout(timeout, retry_wait, mock_function)

    assert len(mock_function.mock_calls) == 2


@pytest.mark.parametrize("retry_multiplier", [1.0, 1000.0])
def test_retry_until_timeout_success_long_retry(monkeypatch, timeout, retry_multiplier):
    """retry_wait > timeout, we never loop."""
    retry_wait = retry_multiplier * timeout
    mock_function = mock.Mock(return_value=None)
    mock_monotonic = mock.Mock(wraps=time.monotonic)
    monkeypatch.setattr("time.monotonic", mock_monotonic)

    retry.retry_until_timeout(timeout, retry_wait, mock_function)

    mock_function.assert_called_once_with(retry_wait)
    assert mock_monotonic.mock_calls == [mock.call(), mock.call()]


@pytest.mark.parametrize("error_cls", [TimeoutError, Exception, ValueError])
def test_retry_until_timeout_times_out(retry_wait, timeout, mock_time_sleep, error_cls):
    mock_function = mock.Mock(side_effect=Exception())

    with pytest.raises(error_cls):
        retry.retry_until_timeout(timeout, retry_wait, mock_function, error=error_cls())

    mock_function.assert_called()

    mock_time_sleep.assert_called_with(retry_wait)


@pytest.mark.parametrize("error_cls", [TimeoutError, Exception, ValueError])
@pytest.mark.parametrize("retry_multiplier", [1.0, 1.1, 2.0])
def test_retry_until_timeout_times_out_long_retry(
    timeout, mock_time_sleep, error_cls, retry_multiplier
):
    """Here the retry time is always at least as long as the timeout."""
    mock_function = mock.Mock(side_effect=Exception())

    with pytest.raises(error_cls):
        retry.retry_until_timeout(
            timeout, timeout * retry_multiplier, mock_function, error=error_cls()
        )

    mock_function.assert_called_once()

    mock_time_sleep.assert_not_called()
