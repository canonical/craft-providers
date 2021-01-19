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

"""Path-related helpers."""
import hashlib
import pathlib
import shutil
from typing import Optional


def calculate_file_hash(
    *,
    file_path: pathlib.Path,
    algorithm: str = "sha3_384",
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calculate hash, reading the file in specified chunks.

    :param file_path: Path to file.
    :param algorithm: Hashing algorithm to use, supported by hashlib.
    :param chunk_size: Size of chunk to read/hash at a time.

    :returns: File hash.
    """
    ctx = hashlib.new(algorithm)

    with file_path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            ctx.update(chunk)

    return ctx.hexdigest()


def which(command: str) -> Optional[pathlib.Path]:
    """Find command on path.

    :param command: Which command to find (e.g. "my-executable").

    :returns: Path to command if found, else None.
    """
    path = shutil.which(command)
    if path:
        return pathlib.Path(path)

    return None


def which_required(command: str) -> pathlib.Path:
    """Find command on path, raising error if not found.

    :param command: Which command to find (e.g. "my-executable").

    :raises RuntimeError: If command not found.
    """
    path = which(command)
    if path is None:
        raise RuntimeError(f"Missing required command {command!r}.")

    return path
