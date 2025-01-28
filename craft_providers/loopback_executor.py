#
# Copyright 2025 Canonical Ltd.
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

"""Loopback executor module."""

import contextlib
import hashlib
import io
import logging
import pathlib
import re
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional

from craft_providers.executor import Executor
import craft_providers.util.temp_paths
from craft_providers.errors import ProviderError

logger = logging.getLogger(__name__)


class LoopbackExecutor(Executor):
    """Allows executing commands on the host, but using Executior facilities."""

    def execute_popen(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.PurePath] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> subprocess.Popen:

        # Popen() doesn't take a timeout, popen_obj.communicate() does - so what is this
        # actually supposed to do??  Run communicate() and then return the used Popen
        # obj?

        # XXX: delete this function from parent class and all children entirely?

        return subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            **kwargs,
        )

    def execute_run(
        self,
        command: List[str],
        *,
        cwd: Optional[pathlib.PurePath] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        timeout: Optional[float] = None,
        check: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            check=check,
            **kwargs,
        )

    def pull_file(self, *, source: pathlib.PurePath, destination: pathlib.Path) -> None:
        raise NotImplementedError()

    def push_file(self, *, source: pathlib.Path, destination: pathlib.PurePath) -> None:
        raise NotImplementedError()

    def push_file_io(
        self,
        *,
        destination: pathlib.PurePath,
        content: io.BytesIO,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        raise NotImplementedError()

    def delete(self) -> None:
        raise NotImplementedError()

    def exists(self) -> bool:
        raise NotImplementedError()

    def mount(self, *, host_source: pathlib.Path, target: pathlib.PurePath) -> None:
        raise NotImplementedError()

    def is_running(self) -> bool:
        raise NotImplementedError()
