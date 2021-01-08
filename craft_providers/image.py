"""Image module."""
import logging
from abc import ABC, abstractmethod
from typing import Final

from .executor import Executor

logger = logging.getLogger(__name__)


class Image(ABC):  # pylint: disable=too-few-public-methods
    """Image definition for configuration/setup.

    Images encapsulate the logic required to setup a base image upon initial
    launch and restarting.  By extending this class, an application may include
    its own additional setup/update requirements.

    :param name: Name of image.
    :param compatibility_tag: Version of image setup used to ensure
        compatibility for re-used instances.  Any change to this version would
        indicate that prior [versioned] instances are incompatible and must be
        cleaned.  As such, any new value should be unique to old values (e.g.
        incrementing).
    """

    def __init__(self, *, name: str, compatibility_tag: str) -> None:
        self.name: Final[str] = name
        self.compatibility_tag: Final[str] = compatibility_tag

    @abstractmethod
    def setup(self, *, executor: Executor) -> None:
        """Setup instance.

        :raises CompatibilityError: if executor instance is incompatible with image.
        """
        ...
