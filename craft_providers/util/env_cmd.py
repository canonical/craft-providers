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

"""Helper(s) for env command."""
from typing import Dict, List, Optional


def formulate_command(
    env: Optional[Dict[str, Optional[str]]] = None, *, ignore_environment: bool = False
) -> List[str]:
    """Create an env command with the specified environment.

    For each key-value, the env command will include the key=value argument to
    the env command.

    If a variable is None, then the env -u parameter will be used to unset it.

    An empty environment will simply yield the env command.

    :param env: Environment flags to set/unset.
    :param ignore_environment: Start with an empty environment.

    :returns: List of env command strings.
    """
    env_cmd = ["env"]

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
