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

"""Persistent instance config / datastore resident in provided environment."""

import io
import pathlib
from typing import Any, Dict, Optional

import pydantic
import yaml

from craft_providers.errors import BaseConfigurationError, ProviderError
from craft_providers.executor import Executor
from craft_providers.util import temp_paths


def update_nested_dictionaries(
    config_data: Dict[str, Any], new_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Recursively update a dictionary containing nested dictionaries.

    New values are added and existing values are updated. No data are removed.

    :param config_data: dictionary of config data to update.
    :param new_data: data to update `config_data` with.
    """
    for key, value in new_data.items():
        if isinstance(value, dict):
            config_data[key] = update_nested_dictionaries(
                config_data.get(key, {}), value
            )
        else:
            config_data[key] = value
    return config_data


class InstanceConfiguration(pydantic.BaseModel, extra="forbid"):
    """Instance configuration datastore.

    :param compatibility_tag: Compatibility tag for instance.
    :param setup: True if instance was fully setup.
    :param snaps: dictionary of snaps and their revisions, e.g.
      snaps:
        snapcraft:
          revision: "x100"
        charmcraft:
          revision: 834
    """

    compatibility_tag: Optional[str] = None
    setup: Optional[bool] = None
    snaps: Optional[Dict[str, Dict[str, Any]]] = None

    @classmethod
    def unmarshal(cls, data: Dict[str, Any]) -> "InstanceConfiguration":
        """Create and populate a new `InstanceConfig` object from dictionary data.

        The unmarshal method validates the data in the dictionary and populates
        the corresponding fields in the `InstanceConfig` object.

        :param data: The dictionary data to unmarshal.

        :return: The newly created `InstanceConfiguration` object.

        :raise BaseConfigurationError: If validation fails.
        """
        return InstanceConfiguration(**data)

    def marshal(self) -> Dict[str, Any]:
        """Create a dictionary containing the InstanceConfiguration data.

        :return: The newly created dictionary.
        """
        return self.model_dump(by_alias=True, exclude_unset=True)

    @classmethod
    def load(
        cls,
        executor: Executor,
        config_path: pathlib.PurePath = pathlib.PurePath("/etc/craft-instance.conf"),
    ) -> Optional["InstanceConfiguration"]:
        """Load an instance config file from an environment.

        :param executor: Executor for instance.
        :param config_path: Path to configuration file.
                            Default is `/etc/craft-instance.conf`.

        :return: The InstanceConfiguration object or None,
                 if the config does not exist or is empty.

        :raise BaseConfigurationError: If the file cannot be loaded from
                                       the environment.
        """
        with temp_paths.home_temporary_file() as temp_config_file:
            try:
                executor.pull_file(source=config_path, destination=temp_config_file)
            except ProviderError as error:
                raise BaseConfigurationError(
                    brief=(
                        "Failed to read instance config"
                        f" in environment at {config_path}"
                    ),
                ) from error
            except FileNotFoundError:
                return None
            with open(temp_config_file, encoding="utf8") as file:
                data = yaml.safe_load(file)
                if data is None:
                    return None

                return cls.unmarshal(data)

    def save(
        self,
        executor: Executor,
        config_path: pathlib.PurePath = pathlib.PurePath("/etc/craft-instance.conf"),
    ) -> None:
        """Save an instance config file to an environment.

        :param executor: Executor for instance.
        :param config_path: Path to configuration file.
                            Default is `/etc/craft-instance.conf`.

        """
        data = self.marshal()

        executor.push_file_io(
            destination=config_path,
            content=io.BytesIO(yaml.dump(data).encode()),
            file_mode="0644",
        )

    @classmethod
    def update(
        cls,
        executor: Executor,
        data: Dict[str, Any],
        config_path: pathlib.PurePath = pathlib.PurePath("/etc/craft-instance.conf"),
    ) -> "InstanceConfiguration":
        """Update an instance config file in an environment.

        New values are added and existing values are updated. No data are removed.
        If there is no existing config to update, then a new config is created.

        :param executor: Executor for instance.
        :param data: The dictionary to update instance with.
        :param config_path: Path to configuration file.
                            Default is `/etc/craft-instance.conf`.

        :return: The updated `InstanceConfiguration` object.
        """
        config_instance = cls.load(executor=executor, config_path=config_path)
        if config_instance is None:
            updated_config_instance = cls.unmarshal(data)
        else:
            updated_config_data = update_nested_dictionaries(
                config_data=config_instance.marshal(), new_data=data
            )
            updated_config_instance = InstanceConfiguration(**updated_config_data)

        updated_config_instance.save(executor=executor, config_path=config_path)

        return updated_config_instance
