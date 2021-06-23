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
import subprocess
import textwrap

from craft_providers import errors


def test_provider_error():
    error = errors.ProviderError(brief="test brief")

    assert error == errors.ProviderError(brief="test brief")
    assert str(error) == "test brief"


def test_provider_error_with_details():
    error = errors.ProviderError(brief="test brief", details="test details")

    assert error == errors.ProviderError(brief="test brief", details="test details")
    assert str(error) == "test brief\ntest details"


def test_provider_error_with_resolution():
    error = errors.ProviderError(brief="test brief", resolution="test resolution")

    assert error == errors.ProviderError(
        brief="test brief", resolution="test resolution"
    )
    assert str(error) == "test brief\ntest resolution"


def test_provider_error_with_all():
    error = errors.ProviderError(
        brief="test brief", details="test details", resolution="test resolution"
    )

    assert error == errors.ProviderError(
        brief="test brief", details="test details", resolution="test resolution"
    )
    assert str(error) == "test brief\ntest details\ntest resolution"


def test_details_from_called_process_error():
    error = subprocess.CalledProcessError(
        -1, ["test-command", "flags", "quote$me"], "test stdout", "test stderr"
    )

    details = errors.details_from_called_process_error(error)

    assert details == textwrap.dedent(
        """\
            * Command that failed: "test-command flags 'quote$me'"
            * Command exit code: -1
            * Command output: 'test stdout'
            * Command standard error output: 'test stderr'"""
    )


def test_details_from_command_error():
    details = errors.details_from_command_error(
        returncode=-1,
        cmd=["test-command", "flags", "quote$me"],
    )

    assert details == textwrap.dedent(
        """\
            * Command that failed: "test-command flags 'quote$me'"
            * Command exit code: -1"""
    )


def test_details_from_command_error_with_output_strings():
    details = errors.details_from_command_error(
        returncode=-1,
        cmd=["test-command", "flags", "quote$me"],
        stdout="test stdout",
        stderr="test stderr",
    )

    assert details == textwrap.dedent(
        """\
            * Command that failed: "test-command flags 'quote$me'"
            * Command exit code: -1
            * Command output: 'test stdout'
            * Command standard error output: 'test stderr'"""
    )


def test_details_from_command_error_with_output_bytes():
    details = errors.details_from_command_error(
        returncode=-1,
        cmd=["test-command", "flags", "quote$me"],
        stdout=bytes.fromhex("00 FF"),
        stderr=bytes.fromhex("01 FE"),
    )

    assert details == textwrap.dedent(
        """\
            * Command that failed: "test-command flags 'quote$me'"
            * Command exit code: -1
            * Command output: b'\\x00\\xff'
            * Command standard error output: b'\\x01\\xfe'"""
    )
