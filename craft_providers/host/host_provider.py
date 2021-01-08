"""Host provider."""
import logging
from typing import Optional

from .. import Executor, Provider
from .host_executor import HostExecutor

logger = logging.getLogger(__name__)


class HostProvider(Provider):
    """Run commands directly on host."""

    def __init__(
        self,
        *,
        sudo_user: Optional[str] = "root",
    ) -> None:
        super().__init__()
        self.sudo_user = sudo_user

    def setup(self) -> Executor:
        return HostExecutor(
            sudo_user=self.sudo_user,
        )

    def teardown(self, *, clean: bool = False) -> None:
        pass
