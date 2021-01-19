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

"""Linux executor actions."""
import logging
import pathlib
import subprocess
from typing import Any, Dict, Optional

import yaml

from craft_providers import Executor

logger = logging.getLogger(__name__)


def load(*, executor: Executor, config_path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """Load craft configuration.

    :param executor: Executor for instance.
    :param config_path: Path to configuration file.
    """
    try:
        proc = executor.execute_run(
            command=["cat", str(config_path)],
            check=True,
            stdout=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        return None

    return yaml.load(proc.stdout, Loader=yaml.SafeLoader)


def save(
    *, executor: Executor, config: Dict[str, Any], config_path: pathlib.Path
) -> None:
    """Save craft image config.

    :param executor: Executor for instance.
    :param config: Configuration data to write.
    :param config_path: Path to configuration file.
    """
    executor.create_file(
        destination=config_path,
        content=yaml.dump(config).encode(),
        file_mode="0644",
    )
