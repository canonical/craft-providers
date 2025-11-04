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
"""A factory for providing bases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    import enum
    import pathlib

    from craft_providers.actions.snap_installer import Snap
    from craft_providers.base import Base

    # These are used in code, but we import them there so we don't have to import
    # them if they don't get used.
    from craft_providers.bases.almalinux import AlmaLinuxBase
    from craft_providers.bases.centos import CentOSBase
    from craft_providers.bases.ubuntu import BuilddBase


@overload
def get_base(
    *,
    distribution: Literal["almalinux"],
    series: str,
    compatibility_tag: str | None = None,
    environment: dict[str, str | None] | None = None,
    hostname: str = "craft-instance",
    snaps: list[Snap] | None = None,
    packages: list[str] | None = None,
    use_default_packages: bool = True,
    cache_path: pathlib.Path | None = None,
) -> AlmaLinuxBase: ...
@overload
def get_base(
    *,
    distribution: Literal["centos"],
    series: str,
    compatibility_tag: str | None = None,
    environment: dict[str, str | None] | None = None,
    hostname: str = "craft-instance",
    snaps: list[Snap] | None = None,
    packages: list[str] | None = None,
    use_default_packages: bool = True,
    cache_path: pathlib.Path | None = None,
) -> CentOSBase: ...
@overload
def get_base(
    *,
    distribution: Literal["ubuntu"],
    series: str,
    compatibility_tag: str | None = None,
    environment: dict[str, str | None] | None = None,
    hostname: str = "craft-instance",
    snaps: list[Snap] | None = None,
    packages: list[str] | None = None,
    use_default_packages: bool = True,
    cache_path: pathlib.Path | None = None,
) -> BuilddBase: ...
@overload
def get_base(
    *,
    distribution: str,
    series: str,
    compatibility_tag: str | None = None,
    environment: dict[str, str | None] | None = None,
    hostname: str = "craft-instance",
    snaps: list[Snap] | None = None,
    packages: list[str] | None = None,
    use_default_packages: bool = True,
    cache_path: pathlib.Path | None = None,
) -> Base[enum.Enum]: ...
def get_base(  # noqa: PLR0913
    *,
    distribution: str,
    series: str,
    compatibility_tag: str | None = None,
    environment: dict[str, str | None] | None = None,
    hostname: str = "craft-instance",
    snaps: list[Snap] | None = None,
    packages: list[str] | None = None,
    use_default_packages: bool = True,
    cache_path: pathlib.Path | None = None,
) -> Base[enum.Enum]:
    """Get a base according to the provided distribution and series.

    :param distribution: The distribution of the base (e.g. ubuntu)
    :param series: The series of the base (e.g. 26.04)
    :param compatibility_tag: Tag/Version for variant of build configuration and
        setup.  Any change to this version would indicate that prior [versioned]
        instances are incompatible and must be cleaned.  As such, any new value
        should be unique to old values (e.g. incrementing).  It is suggested to
        extend this tag, not overwrite it, e.g.: compatibility_tag =
        f"{appname}-{Base.compatibility_tag}.{apprevision}" to ensure base
        compatibility levels are maintained.
    :param environment: Environment to set in /etc/environment.
    :param hostname: Hostname to configure.
    :param snaps: Optional list of snaps to install on the base image.
    :param packages: Optional list of system packages to install on the base image.
    :param use_default_packages: Optional bool to enable/disable default packages.
    :param cache_path: Optional path to the shared cache directory. If this is
        provided, shared cache directories will be mounted as appropriate.
    """
    # We're importing within the function here so we don't have to import bases
    # that we aren't going to use.
    alias: BuilddBaseAlias | AlmaLinuxBaseAlias | CentOSBaseAlias
    cls: type[BuilddBase | AlmaLinuxBase | CentOSBase]
    match distribution:
        case "ubuntu":
            from .ubuntu import BuilddBase, BuilddBaseAlias  # noqa: PLC0415

            try:
                alias = BuilddBaseAlias(series)
            except ValueError:
                raise ValueError(f"Unknown Ubuntu series: {series}") from None
            cls = BuilddBase
        case "almalinux":
            from .almalinux import AlmaLinuxBase, AlmaLinuxBaseAlias  # noqa: PLC0415

            try:
                alias = AlmaLinuxBaseAlias(series)
            except ValueError:
                raise ValueError(f"Unknown Alma Linux series: {series}") from None
            cls = AlmaLinuxBase
        case "centos":
            from .centos import CentOSBase, CentOSBaseAlias  # noqa: PLC0415

            try:
                alias = CentOSBaseAlias(series)
            except ValueError:
                raise ValueError(f"Unknown CentOS series: {series}") from None
            cls = CentOSBase
        case _:
            raise ValueError(f"Unknown distribution {distribution!r}")

    return cls(
        # Ignore argument type here because we set the matching pair above.
        alias=alias,  # type: ignore[arg-type]
        compatibility_tag=compatibility_tag,
        environment=environment,
        hostname=hostname,
        snaps=snaps,
        packages=packages,
        use_default_packages=use_default_packages,
        cache_path=cache_path,
    )
