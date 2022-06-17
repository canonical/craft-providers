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


from craft_providers.multipass import errors


def test_multipass_error():
    error = errors.MultipassError(brief="foo")

    assert str(error) == "foo"


def test_multipass_error_with_details():
    error = errors.MultipassError(brief="foo", details="bar")

    assert str(error) == "foo\nbar"


def test_multipass_error_with_details_resolution():
    error = errors.MultipassError(brief="foo", details="bar", resolution="do this")

    assert str(error) == "foo\nbar\ndo this"


def test_multipass_installation_error():
    error = errors.MultipassInstallationError(reason="error during foo")

    assert str(error) == (
        "Failed to install Multipass: error during foo.\n"
        "Please visit https://multipass.run/ for instructions"
        " on installing Multipass for your operating system."
    )


def test_multipass_installation_error_with_details():
    error = errors.MultipassInstallationError(
        reason="error during foo", details="Some details..."
    )

    assert str(error) == (
        "Failed to install Multipass: error during foo.\n"
        "Some details...\n"
        "Please visit https://multipass.run/ for instructions"
        " on installing Multipass for your operating system."
    )
