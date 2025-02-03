# Copyright 2024 Canonical Ltd.
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

"""Utilities for use in snap hooks.

A base instance's full name may look like this:
    base-instance-whatevercraft-buildd-base-v7-craft-com.ubuntu.cloud-buildd-daily-core24

From that, the thing we care most about is the compatibility tag:
    whatevercraft-buildd-base-v7
"""

import dataclasses
import json
import re
import subprocess
import sys
from typing import Any

from typing_extensions import Self

from craft_providers import Base, lxd

_BASE_INSTANCE_START_STRING = "base-instance"
_CURRENT_COMPATIBILITY_TAG_REGEX = re.compile(
    f"^{_BASE_INSTANCE_START_STRING}.*-{Base.compatibility_tag}-.*"
)


class HookError(Exception):
    """Hook logic cannot continue.  Hooks themselves should not exit nonzero."""


@dataclasses.dataclass
class LXDInstance:
    """Represents an lxc instance."""

    name: str
    expanded_config: dict[str, str]

    def base_instance_name(self) -> str:
        """Get the full name of the base instance this instance was created from."""
        try:
            return self.expanded_config["image.description"]
        except KeyError as e:
            # Unexpected, cannot continue
            raise HookError("Could not get full base name from {self.name}") from e

    def is_current_base_instance(self) -> bool:
        """Return true if this is a base instance with the current compat tag."""
        return bool(re.match(_CURRENT_COMPATIBILITY_TAG_REGEX, self.name))

    def is_base_instance(self) -> bool:
        """Return true if this is a base instance."""
        return self.name.startswith(_BASE_INSTANCE_START_STRING)

    @classmethod
    def unmarshal(
        cls,
        src: dict[str, str],
    ) -> Self:
        """Use this rather than init - the lxc output has a lot of extra fields."""
        return cls(
            **{  # type: ignore[arg-type]
                k: v
                for k, v in src.items()
                if k in {f.name for f in dataclasses.fields(cls)}
            }
        )


class HookHelper:
    """Hook business logic."""

    def __init__(self, *, project_name: str, simulate: bool, debug: bool) -> None:
        self.simulate = simulate
        self.debug = debug
        self._project_name = project_name

        self._check_has_lxd()
        self._check_project_exists()

    def _check_has_lxd(self) -> None:
        """Check if LXD is installed before doing anything.

        On recent Ubuntu systems, "lxc" might be "/usr/sbin/lxc", which is provided by the
        "lxd-installer" package and will install the LXD snap if it's not installed. This
        installation can then take a long time if the store is having issues. For the
        purposes of the configure and remove hooks we don't want to install LXD just to
        check that it has no stale images.
        """
        if not lxd.is_installed():
            raise HookError("LXD is not installed.")

    def _check_project_exists(self) -> None:
        """Raise HookError if lxc doesn't know about this app."""
        for project in self.lxc("project", "list", proj=False):
            if project["name"] == self._project_name:
                return

        # Didn't find our project name
        raise HookError(f"Project {self._project_name} does not exist in LXD.")

    def dprint(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Print messages to stderr if debug=True.

        Can treat this like normal print(), except can also pass an instance
        dict as the first argument for some automatic formatting.
        """
        if not self.debug:
            return
        if "file" not in kwargs:
            kwargs["file"] = sys.stderr

        print_args = list(args)
        if len(args) >= 1 and isinstance(args[0], LXDInstance):
            # First arg quacks like an instance object
            instance = print_args.pop(0)
            print_args += [":", instance.name]

        print(*print_args, **kwargs)

    def lxc(
        self,
        *args: Any,  # noqa: ANN401
        fail_msg: str | None = None,
        proj: bool = True,
        json_out: bool = True,
    ) -> Any:  # noqa: ANN401
        """Run lxc commands specified in *args.

        :param fail_msg: Print this if the command returns nonzero.
        :param proj: Set to False to not specify lxc project.
        :param json_out: If set to False, don't ask lxc for JSON output.
        """
        lxc_args = ["lxc"]
        if json_out:
            lxc_args += ["--format", "json"]
        if proj:
            lxc_args += ["--project", self._project_name]
        lxc_args += args

        try:
            out = subprocess.run(
                lxc_args,
                check=True,
                text=True,
                capture_output=True,
            ).stdout
        except FileNotFoundError:
            raise HookError("LXD is not installed.")
        except subprocess.CalledProcessError as e:
            if not fail_msg:
                fail_msg = e.stderr
            raise HookError(fail_msg)
        else:
            if not json_out:
                return out
            try:
                return json.loads(out)
            except json.decoder.JSONDecodeError as e:
                raise HookError(f"Didn't get back JSON: {out}") from e

    def delete_instance(self, instance: LXDInstance) -> None:
        """Delete the specified lxc instance."""
        print(
            f" > Removing instance {instance.name} in LXD {self._project_name} project..."
        )
        if self.simulate:
            return
        self.lxc(
            "delete",
            "--force",
            instance.name,
            fail_msg=f"Failed to remove LXD instance {instance.name}.",
            json_out=False,
        )

    def _delete_image(self, image_fingerprint: str) -> None:
        """Remove the image."""
        self.lxc("image", "delete", image_fingerprint, json_out=False)

    def delete_all_images(self) -> None:
        """Delete all images of the lxc project."""
        for image_fingerprint in self._list_images():
            self._delete_image(image_fingerprint)

    def delete_project(self) -> None:
        """Delete this lxc project."""
        print(f"Removing project {self._project_name}")
        if self.simulate:
            return
        self.lxc(
            "project",
            "delete",
            self._project_name,
            proj=False,
            json_out=False,
        )

    def _list_images(self) -> list[str]:
        """Return fingerprints of all images associated with the lxc project."""
        return [image["fingerprint"] for image in self.lxc("image", "list")]

    def list_instances(self) -> list[LXDInstance]:
        """Return a list of all instance objects for the project."""
        return [LXDInstance.unmarshal(instance) for instance in self.lxc("list")]

    def list_base_instances(self) -> list[LXDInstance]:
        """Return a list of all base instance objects for the project."""
        base_instances = []
        for instance in self.list_instances():
            if not instance.is_base_instance():
                self.dprint(instance, "Not a base instance")
                continue

            base_instances.append(instance)
        return base_instances


def configure_hook(lxc: HookHelper) -> None:
    """Cleanup hook run on snap configure."""
    # Keep the newest base instance with the most recent compatibility tag.
    delete_base_full_names = set()
    for instance in lxc.list_base_instances():
        if instance.is_current_base_instance():
            lxc.dprint(instance, "Base instance is current")
            continue

        # This is a base instance but it doesn't match the compat tag, assume it's
        # old (not future) and delete it.
        lxc.dprint(instance, "Base instance uses old compatibility tag, deleting")
        lxc.delete_instance(instance)
        delete_base_full_names.add(instance.base_instance_name())

    if not delete_base_full_names:
        lxc.dprint("No base instances were deleted, so no derived instances to delete")
        return

    # Find the child instances of the bases we deleted and delete them too
    did_delete = False
    for instance in lxc.list_instances():
        if instance.base_instance_name() not in delete_base_full_names:
            continue
        lxc.dprint(instance, "Base instance was deleted, deleting derived instance")
        lxc.delete_instance(instance)
        did_delete = True
    if not did_delete:
        lxc.dprint("Found no instances derived from deleted base instances")


def remove_hook(lxc: HookHelper) -> None:
    """Cleanup hook run on snap removal."""
    for instance in lxc.list_instances():
        lxc.delete_instance(instance)

    # Project deletion will fail if images aren't all deleted first
    lxc.delete_all_images()

    lxc.delete_project()
