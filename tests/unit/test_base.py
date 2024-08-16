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
import pathlib
import subprocess
import sys
from unittest import mock

import pytest
import pytest_subprocess.fake_popen
from craft_providers import Executor, base
from craft_providers.errors import BaseConfigurationError

from tests.unit.conftest import DEFAULT_FAKE_CMD

pytestmark = [pytest.mark.usefixtures("instant_sleep")]

WAIT_FOR_SYSTEM_READY_CMD = ["systemctl", "is-system-running"]
WAIT_FOR_NETWORK_CMD = ["getent", "hosts", "snapcraft.io"]


class FakeBase(base.Base):
    FakeBaseAlias = enum.Enum("FakeBaseAlias", ["TREBLE"])
    _environment = {}

    _hostname = "my-hostname"
    _retry_wait = 0.01

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


@pytest.fixture
def fake_base() -> base.Base:
    return FakeBase()


@pytest.fixture
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
    cmd = [*DEFAULT_FAKE_CMD, *WAIT_FOR_SYSTEM_READY_CMD]
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
        [*DEFAULT_FAKE_CMD, *WAIT_FOR_SYSTEM_READY_CMD], callback=callback
    )
    fake_process.keep_last_process(True)

    with pytest.raises(BaseConfigurationError):
        fake_base._setup_wait_for_system_ready(fake_executor)


def test_wait_for_network_success(
    fake_base, fake_executor, fake_process, failure_count, timeout_value
):
    fake_base._timeout_simple = timeout_value
    cmd = [*DEFAULT_FAKE_CMD, *WAIT_FOR_NETWORK_CMD]
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
    fake_process.register([*DEFAULT_FAKE_CMD, *WAIT_FOR_NETWORK_CMD], callback=callback)
    fake_process.keep_last_process(True)

    with pytest.raises(BaseConfigurationError):
        fake_base._setup_wait_for_system_ready(fake_executor)


@pytest.mark.parametrize("cache_dir", [pathlib.Path("/tmp/fake-cache-dir")])
def test_mount_shared_cache_dirs(fake_process, fake_base, fake_executor, cache_dir):
    """Test mounting of cache directories with a cache directory set."""
    fake_base._cache_path = cache_dir
    user_cache_dir = pathlib.Path("/root/.cache")

    fake_process.register(
        [*DEFAULT_FAKE_CMD, "bash", "-c", "echo -n ${XDG_CACHE_HOME:-${HOME}/.cache}"],
        stdout=str(user_cache_dir),
    )

    fake_process.register(
        [*DEFAULT_FAKE_CMD, "mkdir", "-p", "/root/.cache/pip"],
    )

    fake_base._mount_shared_cache_dirs(fake_executor)

    if sys.platform == "win32":
        expected = {
            "host_source": pathlib.WindowsPath("d:")
            / cache_dir
            / "base-v7"
            / "FakeBaseAlias.TREBLE"
            / "pip",
            "target": user_cache_dir / "pip",
        }
    else:
        expected = {
            "host_source": cache_dir / "base-v7" / "FakeBaseAlias.TREBLE" / "pip",
            "target": user_cache_dir / "pip",
        }
    assert fake_executor.records_of_mount == [expected]


@pytest.mark.parametrize("cache_dir", [pathlib.Path("/tmp/fake-cache-dir")])
def test_mount_shared_cache_dirs_mkdir_failed(
    fake_process, fake_base, fake_executor, cache_dir, mocker
):
    """Test mounting of cache directories with a cache directory set, but mkdir failed."""
    fake_base._cache_path = cache_dir
    user_cache_dir = pathlib.Path("/root/.cache")

    fake_process.register(
        [*DEFAULT_FAKE_CMD, "bash", "-c", "echo -n ${XDG_CACHE_HOME:-${HOME}/.cache}"],
        stdout=str(user_cache_dir),
    )

    fake_process.register(
        [*DEFAULT_FAKE_CMD, "mkdir", "-p", "/root/.cache/pip"],
    )

    mocker.patch("pathlib.Path.mkdir", side_effect=OSError)

    with pytest.raises(BaseConfigurationError):
        fake_base._mount_shared_cache_dirs(fake_executor)


@pytest.mark.parametrize(
    ("process_outputs", "expected"),
    [
        (
            [
                'NAME="AlmaLinux"\nVERSION="9.1 (Lime Lynx)"\nID="almalinux"\nID_LIKE="rhel centos fedora"\nVERSION_ID="9.1"\n'
            ],
            {
                "NAME": "AlmaLinux",
                "ID": "almalinux",
                "VERSION": "9.1 (Lime Lynx)",
                "VERSION_ID": "9.1",
                "ID_LIKE": "rhel centos fedora",
            },
        ),
        (
            [
                "",
                'NAME="AlmaLinux"\nVERSION="9.1 (Lime Lynx)"\nID="almalinux"\nID_LIKE="rhel centos fedora"\nVERSION_ID="9.1"\n',
            ],
            {
                "NAME": "AlmaLinux",
                "ID": "almalinux",
                "VERSION": "9.1 (Lime Lynx)",
                "VERSION_ID": "9.1",
                "ID_LIKE": "rhel centos fedora",
            },
        ),
        (
            [
                'NAME="CentOS Linux"\nVERSION="7 (Core)"\nID="centos"\nID_LIKE="rhel fedora"\nVERSION_ID="7"\n'
            ],
            {
                "NAME": "CentOS Linux",
                "ID": "centos",
                "VERSION": "7 (Core)",
                "VERSION_ID": "7",
                "ID_LIKE": "rhel fedora",
            },
        ),
        (
            [
                "",
                'NAME="CentOS Linux"\nVERSION="7 (Core)"\nID="centos"\nID_LIKE="rhel fedora"\nVERSION_ID="7"\n',
            ],
            {
                "NAME": "CentOS Linux",
                "ID": "centos",
                "VERSION": "7 (Core)",
                "VERSION_ID": "7",
                "ID_LIKE": "rhel fedora",
            },
        ),
        (
            ["NAME=Ubuntu\nVERSION_ID=22.04\n"],
            {"NAME": "Ubuntu", "VERSION_ID": "22.04"},
        ),
    ],
)
def test_get_os_release_success(
    fake_process, fake_executor, fake_base, process_outputs, expected
):
    """`_get_os_release` should parse data from `/etc/os-release` to a dict."""
    for output in process_outputs:
        fake_process.register_subprocess(
            [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
            stdout=output,
        )

    result = fake_base._get_os_release(executor=fake_executor)

    assert result == expected


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        ("", 0),
        ("NAME=Linux", 1),
    ],
)
def test_get_os_release_error_output(
    fake_process, fake_executor, fake_base, stdout, returncode
):
    """Test when output values /etc/os-release are invalid."""
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=stdout,
        returncode=returncode,
    )
    fake_process.keep_last_process(True)

    with pytest.raises(BaseConfigurationError):
        fake_base._get_os_release(executor=fake_executor)


def test_get_os_release_exception(fake_base, mock_executor):
    mock_executor.execute_run.side_effect = subprocess.CalledProcessError(
        cmd=[], returncode=1
    )

    with pytest.raises(BaseConfigurationError):
        fake_base._get_os_release(executor=mock_executor)
