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

from craft_providers.util import temp_paths


def test_home_temporary_directory(monkeypatch):
    # Remove the fake home temporary directory fixture set in conftest
    monkeypatch.undo()

    with temp_paths.home_temporary_directory() as tmp_path:
        assert tmp_path.relative_to(pathlib.Path.home())
        assert tmp_path.is_dir() is True

    assert tmp_path.exists() is False


def test_home_temporary_file(monkeypatch):
    # Remove the fake home temporary file fixture set in conftest
    monkeypatch.undo()

    with temp_paths.home_temporary_file() as tmp_file:
        assert tmp_file.relative_to(pathlib.Path.home())
        assert tmp_file.is_file() is True

    assert tmp_file.exists() is False
