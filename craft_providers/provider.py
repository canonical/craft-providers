# Copyright (C) 2020 Canonical Ltd
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

"""Provider module."""
import logging
from abc import ABC, abstractmethod

from .executor import Executor

logger = logging.getLogger(__name__)


class Provider(ABC):
    """Provide an execution environment for a project.

    Provides the ability to create/launch the environment, execute commands, and
    move data in/out of the environment.

    :param interactive: Ask the user before making any privileged actions on the
        host, such as installing an application. Allows user to be asked (via
        input()) for configuration, if required.

    """

    def __init__(
        self,
        *,
        interactive: bool = True,
    ) -> None:
        self.interactive = interactive

    def __enter__(self) -> "Provider":
        """Launch environment, performing any required setup.

        If interactive was set to True, prompt the user for privileged
        configuration changes using input(), e.g. installing dependencies.

        The executor will launch the instance (if applicable), the Provider
        extens that to include any additional setup that may be required, e.g.
        updating apt, installing required packages. Upon completion of this, it
        is expected that the environment is ready for the user-provided build
        step(s).
        """
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Non-destructive tear-down of environment.

        Unmount, close, and shutdown any resources.
        """
        self.teardown()

    @abstractmethod
    def setup(self) -> Executor:
        """Launch environment."""
        ...

    @abstractmethod
    def teardown(self, *, clean: bool = False) -> None:
        """Tear down environment.

        :param clean: Purge environment if True.
        """
        ...
