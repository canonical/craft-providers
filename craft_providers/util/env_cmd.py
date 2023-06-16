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

"""Helper(s) for env command."""
import pathlib
from typing import Dict, List, Optional


def formulate_command(
    env: Optional[Dict[str, Optional[str]]] = None,
    *,
    chdir: Optional[pathlib.PurePath] = None,
    ignore_environment: bool = False,
) -> List[str]:
    """Create an env command with the specified environment.

    For each key-value, the env command will include the key=value argument to
    the env command.

    If a variable is None, then the env -u parameter will be used to unset it.

    An empty environment will simply yield the env command.

    NOTE: not all versions of `env` support --chdir, it is up to the caller to
    ensure compatibility.

    :param env: Environment flags to set/unset.
    :param chdir: Optional directory to run in.
    :param ignore_environment: Start with an empty environment.

    :returns: List of env command strings.
    """
    env_cmd = ["env"]

    if chdir:
        env_cmd.append(f"--chdir={chdir.as_posix()}")

    if ignore_environment:
        env_cmd.append("-i")

    if env is None:
        return env_cmd

    for key, value in env.items():
        if value is None:
            env_cmd += ["-u", key]
        else:
            env_cmd.append(f"{key}={value}")

    return env_cmd
