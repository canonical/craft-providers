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

import pathlib

import pytest
from craft_providers.util import env_cmd


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, ["env"]),
        ({"foo": "bar"}, ["env", "foo=bar"]),
        ({"foo": "bar", "foo2": "bar2"}, ["env", "foo=bar", "foo2=bar2"]),
        (
            {"foo": "bar", "foo2": None, "foo3": "baz"},
            ["env", "foo=bar", "-u", "foo2", "foo3=baz"],
        ),
        ({"foo": None}, ["env", "-u", "foo"]),
    ],
)
def test_formulate_command(env, expected):
    assert env_cmd.formulate_command(env) == expected


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, ["env", "-i"]),
        ({"foo": "bar"}, ["env", "-i", "foo=bar"]),
        ({"foo": "bar", "foo2": "bar2"}, ["env", "-i", "foo=bar", "foo2=bar2"]),
        (
            {"foo": "bar", "foo2": None, "foo3": "baz"},
            ["env", "-i", "foo=bar", "-u", "foo2", "foo3=baz"],
        ),
        ({"foo": None}, ["env", "-i", "-u", "foo"]),
    ],
)
def test_formulate_command_ignore(env, expected):
    assert env_cmd.formulate_command(env, ignore_environment=True) == expected


def test_formulate_command_chdir():
    assert env_cmd.formulate_command(chdir=pathlib.PurePosixPath("/tmp/foo")) == [
        "env",
        "--chdir=/tmp/foo",
    ]


def test_formulate_command_all_opts():
    assert env_cmd.formulate_command(
        env={"VAR_A": "1", "VAR_B": "2"},
        ignore_environment=True,
        chdir=pathlib.PurePosixPath("/tmp/foo"),
    ) == ["env", "--chdir=/tmp/foo", "-i", "VAR_A=1", "VAR_B=2"]
