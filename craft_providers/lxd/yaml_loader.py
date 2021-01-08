"""Yaml loader."""
import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class _YamlLoader(yaml.SafeLoader):  # pylint: disable=too-many-ancestors
    """Safe yaml loader to be modified for loading yaml output from lxc."""


def _load_yaml(data: bytes) -> Any:
    # Unfortunately some timestamps used by LXD are incompatible with the
    # python's timestamp.  Drop the implicit resolver to avoid this.
    _YamlLoader.yaml_implicit_resolvers = {
        k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    return yaml.load(data, Loader=_YamlLoader)
