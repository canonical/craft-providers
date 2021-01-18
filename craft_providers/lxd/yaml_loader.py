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
