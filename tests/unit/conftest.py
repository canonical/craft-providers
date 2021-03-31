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

import io
import pathlib
import subprocess
from typing import Any, Dict, List, Optional

import pytest

from craft_providers import Executor
from craft_providers.util import env_cmd


class FakeExecutor(Executor):
    """Fake Executor.

    Provides a fake execution environment meant to be paired with the
    fake_subprocess fixture for complete control over execution behaviors.

    This records create_file(), pull_file(), and push_file() in
    records_of_<name> for introspection, similar to mock_calls.
    """

    def __init__(self) -> None:
        self.records_of_create_file: List[Dict[str, Any]] = list()
        self.records_of_pull_file: List[Dict[str, Any]] = list()
        self.records_of_push_file: List[Dict[str, Any]] = list()

    def create_file(
        self,
        *,
        destination: pathlib.Path,
        content: io.BytesIO,
        file_mode: str,
        group: str = "root",
        user: str = "root",
    ) -> None:
        self.records_of_create_file.append(
            dict(
                destination=destination.as_posix(),
                content=content.read(),
                file_mode=file_mode,
                group=group,
                user=user,
            )
        )

    def execute_popen(
        self,
        command: List[str],
        env: Optional[Dict[str, Optional[str]]] = None,
        **kwargs,
    ) -> subprocess.Popen:
        final_cmd = ["fake-executor"] + env_cmd.formulate_command(env) + command
        return subprocess.Popen(final_cmd, **kwargs)

    def execute_run(
        self,
        command: List[str],
        env: Optional[Dict[str, Optional[str]]] = None,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        final_cmd = ["fake-executor"] + env_cmd.formulate_command(env) + command
        return subprocess.run(  # pylint: disable=subprocess-run-check
            final_cmd, **kwargs
        )

    def pull_file(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        self.records_of_pull_file.append(
            dict(
                source=source,
                destination=destination,
            )
        )

    def push_file(self, *, source: pathlib.Path, destination: pathlib.Path) -> None:
        self.records_of_push_file.append(
            dict(
                source=source,
                destination=destination,
            )
        )


@pytest.fixture
def fake_executor():
    yield FakeExecutor()
