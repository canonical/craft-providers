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
"""Tests for abstract Base's implementations."""
import enum
import subprocess
from unittest import mock

import pytest
import pytest_subprocess.fake_popen
from craft_providers import Executor, base
from craft_providers.errors import BaseConfigurationError

FAKE_EXECUTOR_CMD = ["fake-executor"]
WAIT_FOR_SYSTEM_READY_CMD = ["systemctl", "is-system-running"]
WAIT_FOR_NETWORK_CMD = ["getent", "hosts", "snapcraft.io"]


class FakeBase(base.Base):
    FakeBaseAlias = enum.Enum("FakeBaseAlias", ["TREBLE"])
    _environment = {}

    _hostname = "my-hostname"
    _retry_wait = 0.0  # Don't actually sleep before retrying

    # Very small retry and timeout values so tests don't take long.
    _timeout_simple = 1
    _timeout_complex = _timeout_simple * 2
    _timeout_unpredictable = _timeout_complex * 2
    alias = FakeBaseAlias.TREBLE

    # Minimal implementations of abstract methods
    def __init__(self, **kwargs):
        pass

    def _ensure_os_compatible(self, executor: Executor) -> None:
        pass

    def _setup_packages(self, executor: Executor) -> None:
        pass

    def _setup_snapd(self, executor: Executor) -> None:
        pass


@pytest.fixture()
def fake_base() -> base.Base:
    return FakeBase()


@pytest.fixture()
def mock_executor():
    return mock.Mock(spec=Executor)


@pytest.fixture(params=[None, 0.1, 1])
def timeout_value(request):
    return request.param


def raise_timeout(process: pytest_subprocess.fake_popen.FakePopen):
    """Raise a TimeoutExpired exception, for use as a callback for subprocess."""
    raise subprocess.TimeoutExpired(process.args, 0)


@pytest.mark.parametrize("running_state", ["running", "degraded"])
def test_wait_for_system_ready_success(
    fake_base, fake_executor, fake_process, running_state, failure_count, timeout_value
):
    fake_base._timeout_simple = timeout_value
    cmd = [*FAKE_EXECUTOR_CMD, *WAIT_FOR_SYSTEM_READY_CMD]
    for _ in range(failure_count):
        fake_process.register(cmd, stdout="no")
    fake_process.register(cmd, stdout=running_state)

    fake_base._setup_wait_for_system_ready(fake_executor)


@pytest.mark.parametrize(
    "callback",
    [
        pytest.param(raise_timeout, id="subprocess-timeout"),
        pytest.param(lambda _: None, id="loop-timeout"),
    ],
)
def test_wait_for_system_ready_timeout(
    fake_base, fake_executor, fake_process, callback
):
    fake_process.register(
        [*FAKE_EXECUTOR_CMD, *WAIT_FOR_SYSTEM_READY_CMD], callback=callback
    )
    fake_process.keep_last_process(True)

    with pytest.raises(BaseConfigurationError):
        fake_base._setup_wait_for_system_ready(fake_executor)


def test_wait_for_network_success(
    fake_base, fake_executor, fake_process, failure_count, timeout_value
):
    fake_base._timeout_simple = timeout_value
    cmd = [*FAKE_EXECUTOR_CMD, *WAIT_FOR_NETWORK_CMD]
    for _ in range(failure_count):
        fake_process.register(cmd, returncode=1)
    fake_process.register(cmd, returncode=0)

    fake_base._setup_wait_for_network(fake_executor)


@pytest.mark.parametrize(
    "callback",
    [
        pytest.param(raise_timeout, id="subprocess-timeout"),
        pytest.param(lambda _: None, id="loop-timeout"),
    ],
)
def test_wait_for_network_timeout(fake_base, fake_executor, fake_process, callback):
    fake_process.register(
        [*FAKE_EXECUTOR_CMD, *WAIT_FOR_NETWORK_CMD], callback=callback
    )
    fake_process.keep_last_process(True)

    with pytest.raises(BaseConfigurationError):
        fake_base._setup_wait_for_system_ready(fake_executor)
