#
# Copyright 2021-2023 Canonical Ltd.
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

"""Helpers for temporary files."""

import contextlib
import pathlib
import tempfile
from typing import Iterator


@contextlib.contextmanager
def home_temporary_directory() -> Iterator[pathlib.Path]:
    """Create temporary directory in home directory where Multipass has access."""
    with tempfile.TemporaryDirectory(
        suffix=".tmp-craft", dir=pathlib.Path.home()
    ) as tmp_dir:
        yield pathlib.Path(tmp_dir)


@contextlib.contextmanager
def home_temporary_file() -> Iterator[pathlib.Path]:
    """Create a temporary file in the home directory where Multipass has access."""
    with home_temporary_directory() as tmp_dir:
        with tempfile.NamedTemporaryFile(dir=tmp_dir) as tmp_file:
            yield pathlib.Path(tmp_file.name)
