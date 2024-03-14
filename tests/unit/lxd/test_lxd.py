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

import pytest
from craft_providers import errors
from craft_providers.lxd import LXD, LXDError


def test_init(fake_process):
    fake_process.register_subprocess(
        [
            "lxd",
            "init",
        ]
    )

    LXD().init()

    assert len(fake_process.calls) == 1


def test_init_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "sudo",
            "lxd",
            "init",
            "--auto",
        ]
    )

    LXD().init(
        auto=True,
        sudo=True,
    )

    assert len(fake_process.calls) == 1


def test_init_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxd",
            "init",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXD().init()

    assert exc_info.value == LXDError(
        brief="Failed to init LXD.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.parametrize(
    ("version", "compatible"),
    [
        ("3.0", False),
        ("3.1.4", False),
        ("3.10", False),
        ("4.0", True),
        ("4.1.4", True),
        ("4.10", True),
        ("5.21.0 LTS", True),
    ],
)
def test_is_supported_version(fake_process, version, compatible):
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout=version,
    )

    assert LXD().is_supported_version() == compatible
    assert len(fake_process.calls) == 1


@pytest.mark.parametrize("version_data", ["", "invalid"])
def test_is_supported_version_parse_error(fake_process, version_data):
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout=version_data,
    )

    with pytest.raises(LXDError) as exc_info:
        LXD().is_supported_version()

    assert exc_info.value == LXDError(
        brief="Failed to parse LXD version.",
        details=f"Version data returned: {version_data!r}",
    )


def test_version(fake_process):
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        stdout="test-version",
    )

    version = LXD().version()

    assert len(fake_process.calls) == 1
    assert version == "test-version"


def test_version_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxd",
            "version",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXD().version()

    assert exc_info.value == LXDError(
        brief="Failed to query LXD version.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_wait_ready(fake_process):
    fake_process.register_subprocess(
        [
            "lxd",
            "waitready",
        ]
    )

    LXD().wait_ready()

    assert len(fake_process.calls) == 1


def test_wait_ready_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "sudo",
            "lxd",
            "waitready",
            "--timeout=5",
        ]
    )

    LXD().wait_ready(
        sudo=True,
        timeout=5,
    )

    assert len(fake_process.calls) == 1


def test_wait_ready_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxd",
            "waitready",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXD().wait_ready()

    assert exc_info.value == LXDError(
        brief="Failed to wait for LXD to get ready.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )
