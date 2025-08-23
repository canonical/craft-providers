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
"""Access to the user's LXC configuration."""

import pathlib
from typing import Annotated, Any, Literal

import pydantic
import yaml
from typing_extensions import Self

SNAP_CONFIG = pathlib.Path("~/snap/lxd/common/config/config.yml").expanduser()
APT_CONFIG = pathlib.Path("~/.config/lxc/config.yml").expanduser()


class SimpleStreamsRemote(pydantic.BaseModel, extra="allow"):
    """An LXD remote for SimpleStreams."""

    addr: pydantic.AnyHttpUrl
    protocol: Literal["simplestreams"]
    public: bool


class TLSRemote(pydantic.BaseModel, extra="allow"):
    """An LXD remote using the LXD protocol."""

    addr: pydantic.AnyHttpUrl
    auth_type: Literal["tls", "oidc"]
    protocol: Literal["lxd"]
    public: bool


class UnixRemote(pydantic.BaseModel, extra="allow"):
    """The default LXD "local" remote."""

    addr: Literal["unix://"]
    public: bool


NetworkRemote = Annotated[
    SimpleStreamsRemote | TLSRemote, pydantic.Field(discriminator="protocol")
]


def _get_remote_tag(remote: dict[str, Any] | NetworkRemote | UnixRemote) -> str:
    if isinstance(remote, dict):
        address = remote.get("addr", "")
    else:
        address = str(remote.addr)
    return "unix" if address.startswith("unix://") else "network"


Remote = Annotated[
    Annotated[UnixRemote, pydantic.Tag("unix")]
    | Annotated[NetworkRemote, pydantic.Tag("network")],
    pydantic.Discriminator(_get_remote_tag),
]


class UserConfig(pydantic.BaseModel):
    """A user's LXC configuration."""

    model_config = pydantic.ConfigDict(
        extra="allow", alias_generator=lambda name: name.replace("_", "-")
    )

    default_remote: str
    remotes: dict[str, Remote]
    aliases: dict[str, str]
    _path: pathlib.Path = pydantic.PrivateAttr()

    @classmethod
    def load(cls, path: pathlib.Path | None = None) -> Self:
        """Load this user configuration."""
        if path is None:
            if SNAP_CONFIG.is_file():
                path = SNAP_CONFIG
            elif APT_CONFIG.is_file():
                path = APT_CONFIG
            else:
                raise FileNotFoundError("Could not find LXC config.")
        with path.open() as f:
            raw = yaml.safe_load(f)
        self = cls.model_validate(raw)
        self._path = path
        return self

    def save(self) -> None:
        """Save this configuration back to the same file."""
        with self._path.open("w+") as f:
            yaml.safe_dump(self.model_dump(mode="json", by_alias=True), f)

    def get_remote_cert_path(self, remote: str) -> pathlib.Path:
        """Get the certificate path for a remote."""
        if remote not in self.remotes:
            raise ValueError(f"Undefined remote {remote}")
        return self._path.parent / f"servercerts/{remote}.crt"


DEFAULT_REMOTES = {
    "images": SimpleStreamsRemote(
        addr=pydantic.AnyHttpUrl("https://images.lxd.canonical.com/"),
        protocol="simplestreams",
        public=True,
    ),
    "ubuntu": SimpleStreamsRemote(
        addr=pydantic.AnyHttpUrl("https://cloud-images.ubuntu.com/releases/"),
        protocol="simplestreams",
        public=True,
    ),
    "ubuntu-daily": SimpleStreamsRemote(
        addr=pydantic.AnyHttpUrl("https://cloud-images.ubuntu.com/daily/"),
        protocol="simplestreams",
        public=True,
    ),
    "ubuntu-minimal": SimpleStreamsRemote(
        addr=pydantic.AnyHttpUrl("https://cloud-images.ubuntu.com/minimal/releases/"),
        protocol="simplestreams",
        public=True,
    ),
    "ubuntu-minimal-daily": SimpleStreamsRemote(
        addr=pydantic.AnyHttpUrl("https://cloud-images.ubuntu.com/minimal/daily/"),
        protocol="simplestreams",
        public=True,
    ),
}
