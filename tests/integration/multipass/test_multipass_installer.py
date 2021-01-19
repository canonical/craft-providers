# Copyright (C) 2021 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import sys

import pytest

from craft_providers.multipass import multipass_installer


@pytest.fixture(autouse=True)
def multipass_path():
    """Override shared fixture."""
    yield None


@pytest.fixture(autouse=True)
def uninstalled_multipass():
    """Uninstall Multipass prior to test, if environment allows it.

    CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL=1
    """
    if not multipass_installer.is_installed():
        return

    if (
        os.environ.get("CRAFT_PROVIDER_TESTS_ENABLE_MULTIPASS_UNINSTALL") == "1"
        and sys.platform == "linux"
    ):
        subprocess.run(["sudo", "snap", "remove", "multipass", "--purge"], check=True)
    else:
        pytest.skip("not allowed to uninstall multipass, skipped")


def test_install():
    path = multipass_installer.install()

    assert path.exists() is True
    assert multipass_installer.is_installed() is True
