# Copyright 2021 Canonical Ltd.
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


import pytest

from craft_providers.util import env_cmd


@pytest.mark.parametrize(
    "env,expected",
    [
        (dict(), ["env"]),
        (dict(foo="bar"), ["env", "foo=bar"]),
        (dict(foo="bar", foo2="bar2"), ["env", "foo=bar", "foo2=bar2"]),
        (
            dict(foo="bar", foo2=None, foo3="baz"),
            ["env", "foo=bar", "-u", "foo2", "foo3=baz"],
        ),
        (dict(foo=None), ["env", "-u", "foo"]),
    ],
)
def test_formulate_command(env, expected):
    assert env_cmd.formulate_command(env) == expected


@pytest.mark.parametrize(
    "env,expected",
    [
        (dict(), ["env", "-i"]),
        (dict(foo="bar"), ["env", "-i", "foo=bar"]),
        (dict(foo="bar", foo2="bar2"), ["env", "-i", "foo=bar", "foo2=bar2"]),
        (
            dict(foo="bar", foo2=None, foo3="baz"),
            ["env", "-i", "foo=bar", "-u", "foo2", "foo3=baz"],
        ),
        (dict(foo=None), ["env", "-i", "-u", "foo"]),
    ],
)
def test_formulate_command_ignore(env, expected):
    assert env_cmd.formulate_command(env, ignore_environment=True) == expected
