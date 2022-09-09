#
# Copyright 2021-2022 Canonical Ltd.
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

import subprocess
from textwrap import dedent
from unittest.mock import ANY, call, patch

import pytest
from logassert import Exact  # type: ignore
from pydantic import ValidationError

from craft_providers.actions.snap_installer import SnapInstallationError
from craft_providers.bases import (
    BaseCompatibilityError,
    BaseConfigurationError,
    buildd,
    errors,
    instance_config,
)
from craft_providers.errors import details_from_called_process_error

# pylint: disable=too-many-lines

DEFAULT_FAKE_CMD = ["fake-executor"]


@pytest.fixture()
def mock_load(mocker):
    mocker.patch(
        "craft_providers.bases.instance_config.InstanceConfiguration.load",
        return_value=instance_config.InstanceConfiguration(
            compatibility_tag="buildd-base-v0"
        ),
    )


@pytest.fixture()
def mock_install_from_store(mocker):
    yield mocker.patch("craft_providers.actions.snap_installer.install_from_store")


@pytest.fixture()
def mock_inject_from_host(mocker):
    yield mocker.patch("craft_providers.actions.snap_installer.inject_from_host")


@pytest.mark.parametrize(
    "alias,hostname",
    [
        (buildd.BuilddBaseAlias.XENIAL, "test-xenial-host"),
        (buildd.BuilddBaseAlias.BIONIC, "test-bionic-host"),
        (buildd.BuilddBaseAlias.FOCAL, "test-focal-host"),
        (buildd.BuilddBaseAlias.JAMMY, "test-jammy-host"),
    ],
)
@pytest.mark.parametrize(
    "environment, etc_environment_content",
    [
        (
            None,
            (
                "PATH=/usr/local/sbin:/usr/local/bin:"
                "/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin\n"
            ).encode(),
        ),
        (
            dict(
                https_proxy="http://foo.bar:8081",
                PATH="/snap",
                http_proxy="http://foo.bar:8080",
            ),
            (
                "https_proxy=http://foo.bar:8081\n"
                "PATH=/snap\nhttp_proxy=http://foo.bar:8080\n"
            ).encode(),
        ),
    ],
)
@pytest.mark.parametrize(
    "snaps, expected_snap_call",
    [
        (None, []),
        (
            [buildd.Snap(name="snap1", channel="edge", classic=True)],
            [call(executor=ANY, snap_name="snap1", channel="edge", classic=True)],
        ),
    ],
)
@pytest.mark.parametrize(
    "packages, expected_packages",
    [
        (None, ["apt-utils", "curl"]),
        (["grep", "git"], ["apt-utils", "curl", "grep", "git"]),
    ],
)
@pytest.mark.parametrize(
    "tag, expected_tag", [(None, "buildd-base-v0"), ("test-tag", "test-tag")]
)
def test_setup(  # pylint: disable=too-many-arguments
    fake_process,
    fake_executor,
    alias,
    hostname,
    environment,
    etc_environment_content,
    mock_inject_from_host,
    mock_install_from_store,
    mocker,
    snaps,
    expected_snap_call,
    packages,
    expected_packages,
    tag,
    expected_tag,
):
    mocker.patch(
        "craft_providers.bases.instance_config.InstanceConfiguration.load",
        return_value=instance_config.InstanceConfiguration(
            compatibility_tag=expected_tag
        ),
    )

    if environment is None:
        environment = buildd.default_command_environment()

    base_config = buildd.BuilddBase(
        alias=alias,
        compatibility_tag=tag,
        environment=environment,
        hostname=hostname,
        snaps=snaps,
        packages=packages,
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="Ubuntu"
            ID=ubuntu
            ID_LIKE=debian
            VERSION_ID="{alias.value}"
            """
        ),
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "test", "-f", "/etc/craft-instance.conf"],
        returncode=1,
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"], stdout="degraded"
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "hostname", "-F", "/etc/hostname"]
    )
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "ln",
            "-sf",
            "/run/systemd/resolve/resolv.conf",
            "/etc/resolv.conf",
        ]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-resolved"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "systemd-resolved"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-networkd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "systemd-networkd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"]
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "apt-get", "update"])
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "apt-get", "install", "-y"] + expected_packages
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "apt-get", "install", "-y", "fuse", "udev"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-udevd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "start", "systemd-udevd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "apt-get", "install", "-y", "snapd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "start", "snapd.socket"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "snapd.service"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "wait", "system", "seed.loaded"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "set", "system", "proxy.http=http://foo.bar:8080"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.http"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "set", "system", "proxy.https=http://foo.bar:8081"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.https"]
    )

    base_config.setup(executor=fake_executor)

    assert fake_executor.records_of_push_file_io == [
        dict(
            destination="/etc/apt/apt.conf.d/20auto-upgrades",
            content=dedent(
                """\
                APT::Periodic::Update-Package-Lists "10000";
                APT::Periodic::Unattended-Upgrade "0";
                """
            ).encode(),
            file_mode="0644",
            group="root",
            user="root",
        ),
        dict(
            destination="/etc/environment",
            content=etc_environment_content,
            file_mode="0644",
            group="root",
            user="root",
        ),
        dict(
            destination="/etc/craft-instance.conf",
            content=(f"compatibility_tag: {expected_tag}\n").encode(),
            file_mode="0644",
            group="root",
            user="root",
        ),
        dict(
            destination="/etc/hostname",
            content=f"{hostname}\n".encode(),
            file_mode="0644",
            group="root",
            user="root",
        ),
        dict(
            destination="/etc/systemd/network/10-eth0.network",
            content=dedent(
                """\
                [Match]
                Name=eth0

                [Network]
                DHCP=ipv4
                LinkLocalAddressing=ipv6

                [DHCP]
                RouteMetric=100
                UseMTU=true
                """
            ).encode(),
            file_mode="0644",
            group="root",
            user="root",
        ),
        dict(
            destination="/etc/apt/apt.conf.d/00no-recommends",
            content=b'APT::Install-Recommends "false";\n',
            file_mode="0644",
            group="root",
            user="root",
        ),
        dict(
            destination="/etc/apt/apt.conf.d/00update-errors",
            content=b'APT::Update::Error-Mode "any";\n',
            file_mode="0644",
            group="root",
            user="root",
        ),
    ]
    assert fake_executor.records_of_pull_file == []
    assert fake_executor.records_of_push_file == []
    assert mock_install_from_store.mock_calls == expected_snap_call


def test_snaps_no_channel_raises_errors(fake_executor):
    """Verify the Snap model raises an error when the channel is an empty string."""
    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        buildd.Snap(name="snap1", channel="")

    assert exc_info.value == errors.BaseConfigurationError(
        brief="channel cannot be empty",
        resolution="set channel to a non-empty string or `None`",
    )


def test_install_snaps_install_from_store(fake_executor, mock_install_from_store):
    """Verify installing snaps calls install_from_store()."""
    my_snaps = [
        buildd.Snap(name="snap1"),
        buildd.Snap(name="snap2", channel="edge"),
        buildd.Snap(name="snap3", channel="edge", classic=True),
    ]
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, snaps=my_snaps)

    base._install_snaps(executor=fake_executor, deadline=None)

    assert mock_install_from_store.mock_calls == [
        call(
            executor=fake_executor, snap_name="snap1", channel="stable", classic=False
        ),
        call(executor=fake_executor, snap_name="snap2", channel="edge", classic=False),
        call(executor=fake_executor, snap_name="snap3", channel="edge", classic=True),
    ]


def test_install_snaps_inject_from_host_valid(
    fake_executor, mock_inject_from_host, mocker
):
    """Verify installing snaps calls inject_from_host()."""
    mocker.patch("sys.platform", "linux")
    my_snaps = [
        buildd.Snap(name="snap1", channel=None),
        buildd.Snap(name="snap2", channel=None, classic=True),
    ]
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, snaps=my_snaps)

    base._install_snaps(executor=fake_executor, deadline=None)

    assert mock_inject_from_host.mock_calls == [
        call(executor=fake_executor, snap_name="snap1", classic=False),
        call(executor=fake_executor, snap_name="snap2", classic=True),
    ]


def test_install_snaps_inject_from_host_not_linux_error(fake_executor, mocker):
    """Verify install_snaps raises an error when injecting from host on
    a non-linux system."""
    mocker.patch("sys.platform", return_value="darwin")
    my_snaps = [buildd.Snap(name="snap1", channel=None)]
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, snaps=my_snaps)

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base._install_snaps(executor=fake_executor, deadline=None)

    assert exc_info.value == errors.BaseConfigurationError(
        brief="cannot inject snap 'snap1' from host on a non-linux system",
        resolution="install the snap from the store by setting the 'channel' parameter",
    )


def test_install_snaps_install_from_store_error(fake_executor, mocker):
    """Verify install_snaps raises an error when install_from_store fails."""
    mocker.patch(
        "craft_providers.actions.snap_installer.install_from_store",
        side_effect=SnapInstallationError(brief="test error"),
    )
    my_snaps = [
        buildd.Snap(name="snap1", channel="candidate"),
    ]
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, snaps=my_snaps)

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base._install_snaps(executor=fake_executor, deadline=None)

    assert exc_info.value == errors.BaseConfigurationError(
        brief=(
            "failed to install snap 'snap1' from store"
            " channel 'candidate' in target environment."
        )
    )


def test_install_snaps_inject_from_host_error(fake_executor, mocker):
    """Verify install_snaps raises an error when inject_from_host fails."""
    mocker.patch("sys.platform", "linux")
    mocker.patch(
        "craft_providers.actions.snap_installer.inject_from_host",
        side_effect=SnapInstallationError(brief="test error"),
    )
    my_snaps = [
        buildd.Snap(name="snap1", channel=None),
    ]
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, snaps=my_snaps)

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base._install_snaps(executor=fake_executor, deadline=None)

    assert exc_info.value == errors.BaseConfigurationError(
        brief="failed to inject host's snap 'snap1' into target environment."
    )


def test_setup_apt(fake_executor, fake_process):
    """Verify packages are installed as expected."""
    packages = ["grep", "git"]
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, packages=packages)
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "apt-get", "update"])
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "apt-get",
            "install",
            "-y",
            "apt-utils",
            "curl",
            "grep",
            "git",
        ]
    )

    base._setup_apt(executor=fake_executor, deadline=None)


def test_install_default(fake_executor, fake_process):
    """Verify only default packages are installed."""
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY)
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "apt-get", "update"])
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "apt-get", "install", "-y", "apt-utils", "curl"]
    )

    base._setup_apt(executor=fake_executor, deadline=None)


def test_install_packages_update_error(mocker, fake_executor):
    """Verify error is caught from `apt-get update` call."""
    error = subprocess.CalledProcessError(100, ["error"])
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY)

    mocker.patch.object(fake_executor, "execute_run", side_effect=error)

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base._setup_apt(executor=fake_executor, deadline=None)

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to update apt cache.",
        details="* Command that failed: 'error'\n* Command exit code: 100",
    )


def test_install_packages_install_error(mocker, fake_executor):
    """Verify error is caught from `apt-get install` call."""
    error = subprocess.CalledProcessError(100, ["error"])
    base = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY)

    mocker.patch.object(fake_executor, "execute_run", side_effect=[None, error])

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base._setup_apt(executor=fake_executor, deadline=None)

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to install packages.",
        details="* Command that failed: 'error'\n* Command exit code: 100",
    )


def test_ensure_image_version_compatible_failure(
    fake_executor,
    monkeypatch,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    monkeypatch.setattr(
        instance_config.InstanceConfiguration,
        "load",
        lambda **kwargs: instance_config.InstanceConfiguration(
            compatibility_tag="invalid-tag"
        ),
    )

    with pytest.raises(errors.BaseCompatibilityError) as exc_info:
        base_config._ensure_instance_config_compatible(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseCompatibilityError(
        "Expected image compatibility tag 'buildd-base-v0', found 'invalid-tag'"
    )


@patch("time.time", side_effect=[0.0, 1.0])
def test_setup_timeout(  # pylint: disable=unused-argument
    mock_time, fake_executor, fake_process, monkeypatch
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess([fake_process.any()])

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config.setup(
            executor=fake_executor,
            retry_wait=0.01,
            timeout=0.0,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Timed out configuring environment."
    )


def test_ensure_os_compatible_name_failure(
    fake_executor,
    fake_process,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout="NAME=Fedora\nVERSION_ID=32\n",
    )

    with pytest.raises(errors.BaseCompatibilityError) as exc_info:
        base_config._ensure_os_compatible(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseCompatibilityError(
        "Expected OS 'Ubuntu', found 'Fedora'"
    )


def test_ensure_os_compatible_version_failure(
    fake_executor,
    fake_process,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout="NAME=Ubuntu\nVERSION_ID=12.04\n",
    )

    with pytest.raises(errors.BaseCompatibilityError) as exc_info:
        base_config._ensure_os_compatible(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseCompatibilityError(
        "Expected OS version '20.04', found '12.04'"
    )


def test_read_os_release_failure(
    fake_process,
    fake_executor,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._ensure_os_compatible(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value.__cause__ is not None
    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to read /etc/os-release.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_hostname_failure(
    fake_process,
    fake_executor,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "hostname", "-F", "/etc/hostname"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_hostname(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to set hostname.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_networkd_enable_failure(
    fake_process,
    fake_executor,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-networkd"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_networkd(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to setup systemd-networkd.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_networkd_restart_failure(
    fake_process,
    fake_executor,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-networkd"],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "systemd-networkd"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_networkd(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to setup systemd-networkd.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_resolved_enable_failure(
    fake_process,
    fake_executor,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "ln",
            "-sf",
            "/run/systemd/resolve/resolv.conf",
            "/etc/resolv.conf",
        ],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-resolved"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_resolved(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to setup systemd-resolved.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_resolved_restart_failure(
    fake_process,
    fake_executor,
):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "ln",
            "-sf",
            "/run/systemd/resolve/resolv.conf",
            "/etc/resolv.conf",
        ],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-resolved"],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "systemd-resolved"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_resolved(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to setup systemd-resolved.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_snapd_proxy(fake_executor, fake_process):
    """Verify snapd proxy is set or unset."""
    environment = dict(
        http_proxy="http://foo.bar:8080",
        https_proxy="http://foo.bar:8081",
    )
    base_config = buildd.BuilddBase(
        alias=buildd.BuilddBaseAlias.FOCAL,
        environment=environment,  # type: ignore
    )
    fake_process.keep_last_process(True)
    fake_process.register([fake_process.any()])

    base_config._setup_snapd_proxy(
        executor=fake_executor,
        deadline=None,
    )
    assert [
        *DEFAULT_FAKE_CMD,
        "snap",
        "set",
        "system",
        "proxy.http=http://foo.bar:8080",
    ] in fake_process.calls
    assert [
        *DEFAULT_FAKE_CMD,
        "snap",
        "set",
        "system",
        "proxy.https=http://foo.bar:8081",
    ] in fake_process.calls


@pytest.mark.parametrize("fail_index", list(range(0, 1)))
def test_setup_snapd_proxy_failures(fake_process, fake_executor, fail_index):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)

    return_codes = [0, 0]
    return_codes[fail_index] = 1

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.http"],
        returncode=return_codes[0],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.https"],
        returncode=return_codes[1],
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_snapd_proxy(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to set the snapd proxy.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.parametrize("fail_index", list(range(0, 7)))
def test_setup_snapd_failures(fake_process, fake_executor, fail_index):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)

    return_codes = [0, 0, 0, 0, 0, 0, 0]
    return_codes[fail_index] = 1

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "apt-get", "install", "-y", "fuse", "udev"],
        returncode=return_codes[0],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-udevd"],
        returncode=return_codes[1],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "start", "systemd-udevd"],
        returncode=return_codes[2],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "apt-get", "install", "-y", "snapd"],
        returncode=return_codes[3],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "start", "snapd.socket"],
        returncode=return_codes[4],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "snapd.service"],
        returncode=return_codes[5],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "wait", "system", "seed.loaded"],
        returncode=return_codes[6],
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._setup_snapd(  # pylint: disable=protected-access
            executor=fake_executor,
            deadline=None,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to setup snapd.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.parametrize(
    "alias",
    [
        buildd.BuilddBaseAlias.XENIAL,
        buildd.BuilddBaseAlias.BIONIC,
        buildd.BuilddBaseAlias.FOCAL,
        buildd.BuilddBaseAlias.JAMMY,
    ],
)
@pytest.mark.parametrize("system_running_ready_stdout", ["degraded", "running"])
def test_wait_for_system_ready(
    fake_executor, fake_process, alias, system_running_ready_stdout
):
    base_config = buildd.BuilddBase(alias=alias)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"],
        stdout="not-ready",
        returncode=-1,
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"], stdout="still-not-ready"
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"],
        stdout=system_running_ready_stdout,
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"],
        returncode=-1,
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"],
        returncode=0,
    )

    base_config.wait_until_ready(executor=fake_executor, retry_wait=0.0)

    assert fake_executor.records_of_push_file_io == []
    assert fake_executor.records_of_pull_file == []
    assert fake_executor.records_of_push_file == []
    assert list(fake_process.calls) == [
        [
            *DEFAULT_FAKE_CMD,
            "systemctl",
            "is-system-running",
        ],
        [
            *DEFAULT_FAKE_CMD,
            "systemctl",
            "is-system-running",
        ],
        [
            *DEFAULT_FAKE_CMD,
            "systemctl",
            "is-system-running",
        ],
        [
            *DEFAULT_FAKE_CMD,
            "getent",
            "hosts",
            "snapcraft.io",
        ],
        [
            *DEFAULT_FAKE_CMD,
            "getent",
            "hosts",
            "snapcraft.io",
        ],
    ]


@patch("time.time", side_effect=[0.0, 0.0, 1.0])
@pytest.mark.parametrize(
    "alias",
    [
        buildd.BuilddBaseAlias.XENIAL,
        buildd.BuilddBaseAlias.BIONIC,
        buildd.BuilddBaseAlias.FOCAL,
        buildd.BuilddBaseAlias.JAMMY,
    ],
)
def test_wait_for_system_ready_timeout(  # pylint: disable=unused-argument
    mock_time, fake_executor, fake_process, alias
):
    base_config = buildd.BuilddBase(
        alias=alias,
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"],
        stdout="not-ready",
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config.wait_until_ready(
            executor=fake_executor,
            retry_wait=0.0,
            timeout=0.1,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Timed out waiting for environment to be ready."
    )


@patch("time.time", side_effect=[0.0, 0.0, 1.0])
@pytest.mark.parametrize(
    "alias",
    [
        buildd.BuilddBaseAlias.XENIAL,
        buildd.BuilddBaseAlias.BIONIC,
        buildd.BuilddBaseAlias.FOCAL,
        buildd.BuilddBaseAlias.JAMMY,
    ],
)
def test_wait_for_system_ready_timeout_in_network(  # pylint: disable=unused-argument
    mock_time, fake_executor, fake_process, alias, monkeypatch
):
    base_config = buildd.BuilddBase(alias=alias)
    monkeypatch.setattr(
        base_config, "_setup_wait_for_system_ready", lambda **kwargs: None
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"],
        returncode=-1,
    )

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config.wait_until_ready(
            executor=fake_executor,
            retry_wait=0.00,
            timeout=1.0,
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Timed out waiting for networking to be ready."
    )


@patch(
    "craft_providers.bases.instance_config.InstanceConfiguration.load",
    side_effect=ValidationError("foo", instance_config.InstanceConfiguration),
)
def test_ensure_config_compatible_validation_error(fake_executor):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)

    with pytest.raises(errors.BaseConfigurationError) as exc_info:
        base_config._ensure_instance_config_compatible(
            executor=fake_executor, deadline=None
        )

    assert exc_info.value == errors.BaseConfigurationError(
        brief="Failed to parse instance configuration file."
    )


@patch(
    "craft_providers.bases.instance_config.InstanceConfiguration.load",
    return_value=None,
)
def test_ensure_config_compatible_empty_config_returns_none(fake_executor):
    base_config = buildd.BuilddBase(alias=buildd.BuilddBaseAlias.FOCAL)

    assert (
        base_config._ensure_instance_config_compatible(
            executor=fake_executor, deadline=None
        )
        is None
    )


@pytest.mark.parametrize(
    "environment",
    [
        None,
        dict(
            https_proxy="http://foo.bar:8081",
            http_proxy="http://foo.bar:8080",
        ),
    ],
)
def test_warmup_overall(environment, fake_process, fake_executor, mock_load):
    alias = buildd.BuilddBaseAlias.JAMMY

    if environment is None:
        environment = buildd.default_command_environment()

    base_config = buildd.BuilddBase(alias=alias, environment=environment)

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="Ubuntu"
            ID=ubuntu
            ID_LIKE=debian
            VERSION_ID="{alias.value}"
            """
        ),
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"], stdout="degraded"
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "set", "system", "proxy.http=http://foo.bar:8080"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.http"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "set", "system", "proxy.https=http://foo.bar:8081"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.https"]
    )

    base_config.warmup(executor=fake_executor)

    assert fake_executor.records_of_push_file_io == []
    assert fake_executor.records_of_pull_file == []
    assert fake_executor.records_of_push_file == []


def test_warmup_bad_os(fake_process, fake_executor, mock_load):
    base_config = buildd.BuilddBase(
        alias=buildd.BuilddBaseAlias.JAMMY,
        environment=buildd.default_command_environment(),
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            """\
            NAME="D.O.S."
            ID=dos
            ID_LIKE=dos
            VERSION_ID="DOS 5.1"
            """
        ),
    )

    with pytest.raises(BaseCompatibilityError):
        base_config.warmup(executor=fake_executor)


def test_warmup_bad_instance_config(fake_process, fake_executor, mock_load):
    alias = buildd.BuilddBaseAlias.JAMMY
    base_config = buildd.BuilddBase(
        alias=alias,
        environment=buildd.default_command_environment(),
    )
    base_config.compatibility_tag = "different-tag"

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="Ubuntu"
            ID=ubuntu
            ID_LIKE=debian
            VERSION_ID="{alias.value}"
            """
        ),
    )

    with pytest.raises(BaseCompatibilityError):
        base_config.warmup(executor=fake_executor)


def test_warmup_never_ready(fake_process, fake_executor, mock_load):
    alias = buildd.BuilddBaseAlias.JAMMY
    base_config = buildd.BuilddBase(
        alias=alias,
        environment=buildd.default_command_environment(),
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="Ubuntu"
            ID=ubuntu
            ID_LIKE=debian
            VERSION_ID="{alias.value}"
            """
        ),
    )
    for _ in range(3):  # it will called twice until timeout, one extra for safety
        fake_process.register_subprocess(
            [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"],
            stdout="starting",
        )

    with pytest.raises(BaseConfigurationError):
        base_config.warmup(executor=fake_executor, timeout=0.01, retry_wait=0.1)


def test_warmup_never_network(fake_process, fake_executor, mock_load):
    alias = buildd.BuilddBaseAlias.JAMMY
    base_config = buildd.BuilddBase(
        alias=alias,
        environment=buildd.default_command_environment(),
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="Ubuntu"
            ID=ubuntu
            ID_LIKE=debian
            VERSION_ID="{alias.value}"
            """
        ),
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"], stdout="degraded"
    )
    for _ in range(3):  # it will called twice until timeout, one extra for safety
        fake_process.register_subprocess(
            [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"], returncode=1
        )

    with pytest.raises(BaseConfigurationError):
        base_config.warmup(executor=fake_executor, timeout=0.01, retry_wait=0.1)


@pytest.mark.parametrize(
    "hostname",
    [
        "t",
        "test",
        "test1",
        "test-1",
        "1-test",
        "this-is-40-characters-xxxxxxxxxxxxxxxxxx",
        "this-is-63-characters-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ],
)
def test_set_hostname_unchanged(hostname, logs):
    """Verify hostnames that are already compliant are not changed."""
    base_config = buildd.BuilddBase(
        alias=buildd.BuilddBaseAlias.JAMMY,
        hostname=hostname,
    )

    assert base_config.hostname == hostname
    assert Exact(f"Using hostname '{hostname}'") in logs.debug


@pytest.mark.parametrize(
    "hostname, expected_hostname",
    [
        # trim away invalid beginning characters
        ("-test", "test"),
        # trim away invalid ending characters
        ("test-", "test"),
        ("test--", "test"),
        ("test1-", "test1"),
        # trim away invalid characters
        ("test$", "test"),
        ("test-!@#$%^&*()test", "test-test"),
        ("$1test", "1test"),
        ("test-$", "test"),
        # this name contains invalid characters so it gets converted, even
        # though it is 63 characters
        (
            "this-is-63-characters-with-invalid-characters-$$$xxxxxxxxxxxxxX",
            "this-is-63-characters-with-invalid-characters-xxxxxxxxxxxxxX",
        ),
        # this name is longer than 63 characters, so it gets converted
        (
            "this-is-64-characters-with-valid-characters-xxxxxxxxxxxxxxxxxxXx",
            "this-is-64-characters-with-valid-characters-xxxxxxxxxxxxxxxxxxX",
        ),
        # trim away away invalid characters and truncate to 63 characters
        (
            "-this-is-64-characters-and-has-invalid-characters-$$$xxxxxxxxxx-",
            "this-is-64-characters-and-has-invalid-characters-xxxxxxxxxx",
        ),
        # ensure invalid ending characters are removed after truncating
        (
            "this-is-64-characters-and-has-a-hyphen-at-character-63-xxxxxxx-x",
            "this-is-64-characters-and-has-a-hyphen-at-character-63-xxxxxxx",
        ),
    ],
)
def test_set_hostname(hostname, expected_hostname, logs):
    """Verify hostname is compliant with hostname naming conventions."""
    base_config = buildd.BuilddBase(
        alias=buildd.BuilddBaseAlias.JAMMY,
        hostname=hostname,
    )

    assert base_config.hostname == expected_hostname
    assert Exact(f"Using hostname '{expected_hostname}'") in logs.debug


@pytest.mark.parametrize(
    "hostname",
    [
        "",
        "-",
        "$$$",
        "-$-$-",
    ],
)
def test_set_hostname_invalid(hostname):
    """Verify invalid hostnames raise an error."""
    with pytest.raises(BaseConfigurationError) as error:
        buildd.BuilddBase(alias=buildd.BuilddBaseAlias.JAMMY, hostname=hostname)

    assert error.value == BaseConfigurationError(
        brief=f"failed to create base with hostname {hostname!r}.",
        details="hostname must contain at least one alphanumeric character",
    )
