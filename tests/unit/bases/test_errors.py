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


from craft_providers import errors


def test_base_configuration_error():
    error = errors.BaseConfigurationError(brief="foo")

    assert str(error) == "foo"


def test_base_configuration_error_with_details():
    error = errors.BaseConfigurationError(brief="foo", details="bar")

    assert str(error) == "foo\nbar"


def test_base_configuration_error_with_details_resolution():
    error = errors.BaseConfigurationError(
        brief="foo", details="bar", resolution="do this"
    )

    assert str(error) == "foo\nbar\ndo this"


def test_base_compatibility_error():
    error = errors.BaseCompatibilityError(reason="error during foo")

    assert str(error) == (
        "Incompatible base detected: error during foo.\n"
        "Clean incompatible instance and retry the requested operation."
    )


def test_base_compatibility_error_with_details():
    error = errors.BaseCompatibilityError(
        reason="error during foo", details="Some details..."
    )

    assert str(error) == (
        "Incompatible base detected: error during foo.\n"
        "Some details...\n"
        "Clean incompatible instance and retry the requested operation."
    )
