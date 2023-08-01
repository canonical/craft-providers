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


from craft_providers.lxd import errors


def test_lxd_error():
    error = errors.LXDError(brief="foo")

    assert str(error) == "foo"


def test_lxd_error_with_details():
    error = errors.LXDError(brief="foo", details="bar")

    assert str(error) == "foo\nbar"


def test_lxd_error_with_details_resolution():
    error = errors.LXDError(brief="foo", details="bar", resolution="do this")

    assert str(error) == "foo\nbar\ndo this"


def test_lxd_installation_error():
    error = errors.LXDInstallationError(reason="error during foo")

    assert str(error) == (
        "Failed to install LXD: error during foo.\n"
        "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/"
        " for instructions on installing and configuring LXD for your operating system."
    )


def test_lxd_installation_error_with_details():
    error = errors.LXDInstallationError(
        reason="error during foo", details="Some details..."
    )

    assert str(error) == (
        "Failed to install LXD: error during foo.\n"
        "Some details...\n"
        "Visit https://documentation.ubuntu.com/lxd/en/latest/getting_started/"
        " for instructions on installing and configuring LXD for your operating system."
    )


def test_lxd_unstable_image_error():
    error = errors.LXDUnstableImageError(brief="test error")

    assert str(error) == (
        "test error\n"
        "Devel or daily images are not guaranteed and are intended for "
        "experimental use only."
    )
