#
# Copyright 2025 Canonical Ltd.
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
import contextlib
from unittest.mock import MagicMock, patch

import craft_providers
import pytest
from craft_providers.bases import centos, ubuntu
from craft_providers.errors import ProviderError

from tests.unit.conftest import DEFAULT_FAKE_CMD


def test_ensure_guest_compatible_not_ubuntu(fake_executor, fake_process):
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    base._get_os_release = MagicMock(spec=base._get_os_release)
    ubuntu.ensure_guest_compatible(base, fake_executor, "")

    # The first thing that ensure_guest_compatible does is the base check.  The next
    # thing is to call _get_os_release on the base.  So if that isn't called then we
    # haven't progressed.
    base._get_os_release.assert_not_called()


@pytest.mark.parametrize(
    "base_alias",
    [
        ubuntu.BuilddBaseAlias.JAMMY,  # host greater than FOCAL
        ubuntu.BuilddBaseAlias.FOCAL,  # guest less than ORACULAR
    ],
)
def test_ensure_guest_compatible_valid_ubuntu(
    fake_executor,
    fake_process,
    base_alias,
):
    """Check for combinations of host and guest OS unaffected by the lxd issue."""
    guest_base = ubuntu.BuilddBase(alias=base_alias)
    guest_base._retry_wait = 0.01
    guest_base._timeout_simple = 1

    # Set this up so we can be sure the guest _get_os_release was called once
    real_get_os_release = guest_base._get_os_release

    def fake_get_os_release(*args, **kwargs):
        fake_get_os_release.counter += 1  # type: ignore[reportFunctionMemberAccess]
        return real_get_os_release(*args, **kwargs)

    fake_get_os_release.counter = 0  # type: ignore[reportFunctionMemberAccess]
    guest_base._get_os_release = fake_get_os_release

    # Specifying an invalid version string will ensure that the code never gets to the
    # point of parsing the lxd version string in the ensure_guest_compatible call -
    # this would cause an IndexError after the split(".").
    lxd_version = ""

    # Mock the host os-release file
    fake_os_release = f"""
VERSION_ID="{base_alias.value}"
WOOP="dedoo"
"""

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=fake_os_release,
    )

    ubuntu.ensure_guest_compatible(guest_base, fake_executor, lxd_version)

    assert fake_get_os_release.counter == 1  # type: ignore[reportFunctionMemberAccess]


@pytest.mark.parametrize(
    ("host_base_alias", "guest_base_alias", "lxd_version"),
    [
        # host FOCAL or older AND guest ORACULAR or newer
        (
            ubuntu.BuilddBaseAlias.BIONIC,
            ubuntu.BuilddBaseAlias.ORACULAR,
            "4.67.8901",
        ),
        (
            ubuntu.BuilddBaseAlias.FOCAL,
            ubuntu.BuilddBaseAlias.ORACULAR,
            "5.0.3",
        ),
        (
            ubuntu.BuilddBaseAlias.XENIAL,
            ubuntu.BuilddBaseAlias.DEVEL,
            "5.21",
        ),
    ],
)
def test_ensure_guest_compatible_bad_lxd_versions(
    mocker,
    fake_executor,
    fake_process,
    host_base_alias,
    guest_base_alias,
    lxd_version,
):
    """Various LXD versions must raise an exception when the host and guest OS match."""
    guest_base = ubuntu.BuilddBase(alias=guest_base_alias)
    guest_base._retry_wait = 0.01
    guest_base._timeout_simple = 1

    # Mock the guest os-release file contents
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=f'VERSION_ID="{guest_base_alias.value}"',
    )

    # Mock the host os-release file contents
    @contextlib.contextmanager
    def fake_open(*args, **kwargs):
        class Fake:
            def read(self):
                return f'VERSION_ID="{host_base_alias.value}"'

        yield Fake()

    with (
        patch.object(craft_providers.util.os_release.Path, "open", fake_open),  # type: ignore[reportAttributeAccessIssue]
        pytest.raises(ProviderError) as e,
    ):
        ubuntu.ensure_guest_compatible(guest_base, fake_executor, lxd_version)
    assert (
        "This combination of guest and host OS versions requires a newer lxd version."
        in str(e)
    )


@pytest.mark.parametrize(
    ("host_base_alias", "guest_base_alias", "lxd_version", "kernel_version"),
    [
        # host FOCAL or older AND guest ORACULAR or newer
        (
            ubuntu.BuilddBaseAlias.BIONIC,
            ubuntu.BuilddBaseAlias.ORACULAR,
            "6.0",
            "5.14",
        ),
        (
            ubuntu.BuilddBaseAlias.FOCAL,
            ubuntu.BuilddBaseAlias.ORACULAR,
            "5.0.4",
            "2.6.32-51555-generic",
        ),
    ],
)
def test_ensure_guest_compatible_bad_kernel_versions(
    mocker,
    fake_executor,
    fake_process,
    host_base_alias,
    guest_base_alias,
    lxd_version,
    kernel_version,
):
    """Various kernels must raise when the host and guest OS and LXD versions all match."""
    guest_base = ubuntu.BuilddBase(alias=guest_base_alias)
    guest_base._retry_wait = 0.01
    guest_base._timeout_simple = 1

    # Mock the guest os-release file contents
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=f'VERSION_ID="{guest_base_alias.value}"',
    )

    # Mock the host os-release file contents
    @contextlib.contextmanager
    def fake_open(*args, **kwargs):
        class Fake:
            def read(self):
                return f'VERSION_ID="{host_base_alias.value}"'

        yield Fake()

    # Mock the kernel version
    fake_process.register_subprocess(
        ["uname", "-r"],
        stdout=kernel_version,
    )

    with (
        patch.object(craft_providers.util.os_release.Path, "open", fake_open),  # type: ignore[reportAttributeAccessIssue]
        pytest.raises(ProviderError) as e,
    ):
        ubuntu.ensure_guest_compatible(guest_base, fake_executor, lxd_version)
    assert (
        "This combination of guest and host OS versions requires a newer kernel version."
        in str(e)
    )
