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
import pathlib
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import ANY, call, patch

import pytest
from craft_providers.actions.snap_installer import Snap, SnapInstallationError
from craft_providers.bases import centos
from craft_providers.errors import (
    BaseCompatibilityError,
    BaseConfigurationError,
    NetworkError,
    details_from_called_process_error,
)
from craft_providers.instance_config import InstanceConfiguration
from logassert import Exact  # type: ignore

from tests.unit.conftest import DEFAULT_FAKE_CMD


@pytest.fixture
def mock_load(mocker):
    return mocker.patch(
        "craft_providers.instance_config.InstanceConfiguration.load",
        return_value=InstanceConfiguration(compatibility_tag="centos-base-v7"),
    )


@pytest.fixture
def fake_filesystem(fs):
    return fs


@pytest.fixture
def mock_install_from_store(mocker):
    return mocker.patch("craft_providers.actions.snap_installer.install_from_store")


@pytest.fixture
def mock_inject_from_host(mocker):
    return mocker.patch("craft_providers.actions.snap_installer.inject_from_host")


@pytest.fixture
def mock_get_os_release(mocker):
    return mocker.patch.object(
        centos.CentOSBase,
        "_get_os_release",
        return_value={
            "NAME": "CentOS Linux",
            "ID": "centos",
            "VERSION_ID": "7",
        },
    )


@pytest.mark.parametrize("alias", list(centos.CentOSBaseAlias))
@pytest.mark.parametrize(
    ("environment", "etc_environment_content"),
    [
        (
            None,
            (
                b"PATH=/usr/local/sbin:/usr/local/bin:"
                b"/opt/rh/rh-python38/root/usr/bin:"
                b"/sbin:/bin:/usr/sbin:/usr/bin:/snap/bin\n"
            ),
        ),
        (
            {
                "https_proxy": "http://foo.bar:8081",
                "PATH": "/snap",
                "http_proxy": "http://foo.bar:8080",
            },
            (
                b"https_proxy=http://foo.bar:8081\n"
                b"PATH=/snap\nhttp_proxy=http://foo.bar:8080\n"
            ),
        ),
    ],
)
@pytest.mark.parametrize("no_cdn", [False, True])
@pytest.mark.parametrize(
    ("snaps", "expected_snap_call"),
    [
        (None, []),
        (
            [Snap(name="snap1", channel="edge", classic=True)],
            [call(executor=ANY, snap_name="snap1", channel="edge", classic=True)],
        ),
    ],
)
@pytest.mark.parametrize(
    ("packages", "expected_packages"),
    [
        (
            None,
            [
                "autoconf",
                "automake",
                "gcc",
                "gcc-c++",
                "git",
                "make",
                "patch",
                "rh-python38-python",
                "rh-python38-python-devel",
                "rh-python38-python-pip",
                "rh-python38-python-pip-wheel",
                "rh-python38-python-setuptools",
            ],
        ),
        (
            ["go", "clang"],
            [
                "autoconf",
                "automake",
                "gcc",
                "gcc-c++",
                "git",
                "make",
                "patch",
                "rh-python38-python",
                "rh-python38-python-devel",
                "rh-python38-python-pip",
                "rh-python38-python-pip-wheel",
                "rh-python38-python-setuptools",
                "go",
                "clang",
            ],
        ),
    ],
)
@pytest.mark.parametrize(
    ("tag", "expected_tag"), [(None, "centos-base-v7"), ("test-tag", "test-tag")]
)
def test_setup(
    fake_process,
    fake_executor,
    fake_filesystem,
    alias,
    environment,
    etc_environment_content,
    no_cdn,
    mock_load,
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
    mock_load.return_value = InstanceConfiguration(compatibility_tag=expected_tag)

    if environment is None:
        environment = centos.CentOSBase.default_command_environment()

    if no_cdn:
        fake_filesystem.create_file(
            "/etc/systemd/system/snapd.service.d/no-cdn.conf",
            contents=dedent(
                """\
                [Service]
                Environment=SNAPPY_STORE_NO_CDN=1
                """
            ),
        )

    base_config = centos.CentOSBase(
        alias=alias,
        compatibility_tag=tag,
        environment=environment,
        hostname="test-hostname",
        snaps=snaps,
        packages=packages,
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
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
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
            VERSION_ID="{alias.value}"
            VERSION_CODENAME="test-name"
            """
        ),
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "test", "-s", "/etc/cloud/cloud.cfg"]
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "yum", "update", "-y"])
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "yum",
            "install",
            "-y",
            "epel-release",
            "centos-release-scl",
        ]
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "yum", "update"])
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "yum", "install", "-y", *expected_packages]
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "yum", "autoremove", "-y"])
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "yum", "clean", "packages", "-y"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-active", "systemd-udevd"],
        stdout="active",
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-udevd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "start", "systemd-udevd"]
    )
    if no_cdn:
        fake_process.register_subprocess(
            [*DEFAULT_FAKE_CMD, "mkdir", "-p", "/etc/systemd/system/snapd.service.d"]
        )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "yum", "install", "-y", "snapd"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "ln", "-sf", "/var/lib/snapd/snap", "/snap"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "--now", "snapd.socket"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "snapd.service"]
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "wait", "system", "seed.loaded"]
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "snap", "refresh", "--hold"])
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "watch", "--last=auto-refresh?"]
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

    expected_push_file_io = [
        {
            "destination": "/etc/craft-instance.conf",
            "content": (f"compatibility_tag: {expected_tag}\nsetup: false\n").encode(),
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        },
        {
            "destination": "/etc/craft-instance.conf",
            "content": (f"compatibility_tag: {expected_tag}\n").encode(),
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        },
        {
            "destination": "/etc/environment",
            "content": etc_environment_content,
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        },
        {
            "destination": "/etc/hostname",
            "content": b"test-hostname\n",
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        },
        {
            "destination": "/etc/craft-instance.conf",
            "content": (f"compatibility_tag: {expected_tag}\nsetup: true\n").encode(),
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        },
    ]
    expected_push_file = []
    if no_cdn:
        expected_push_file.append(
            {
                "source": Path("/etc/systemd/system/snapd.service.d/no-cdn.conf"),
                "destination": Path("/etc/systemd/system/snapd.service.d/no-cdn.conf"),
            }
        )

    assert fake_executor.records_of_push_file_io == expected_push_file_io
    assert fake_executor.records_of_pull_file == []
    assert fake_executor.records_of_push_file == expected_push_file
    assert mock_install_from_store.mock_calls == expected_snap_call


def test_snaps_no_channel_raises_errors(fake_executor):
    """Verify the Snap model raises an error when the channel is an empty string."""
    with pytest.raises(BaseConfigurationError) as exc_info:
        Snap(name="snap1", channel="")

    assert exc_info.value == BaseConfigurationError(
        brief="channel cannot be empty",
        resolution="set channel to a non-empty string or `None`",
    )


def test_install_snaps_install_from_store(fake_executor, mock_install_from_store):
    """Verify installing snaps calls install_from_store()."""
    my_snaps = [
        Snap(name="snap1"),
        Snap(name="snap2", channel="edge"),
        Snap(name="snap3", channel="edge", classic=True),
    ]
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, snaps=my_snaps)

    base._install_snaps(executor=fake_executor)

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
        Snap(name="snap1", channel=None),
        Snap(name="snap2", channel=None, classic=True),
    ]
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, snaps=my_snaps)

    base._install_snaps(executor=fake_executor)

    assert mock_inject_from_host.mock_calls == [
        call(executor=fake_executor, snap_name="snap1", classic=False),
        call(executor=fake_executor, snap_name="snap2", classic=True),
    ]


def test_install_snaps_inject_from_host_not_linux_error(fake_executor, mocker):
    """Verify install_snaps raises an error when injecting from host on
    a non-linux system."""
    mocker.patch("sys.platform", return_value="darwin")
    my_snaps = [Snap(name="snap1", channel=None)]
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, snaps=my_snaps)

    with pytest.raises(BaseConfigurationError) as exc_info:
        base._install_snaps(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="cannot inject snap 'snap1' from host on a non-linux system",
        resolution="install the snap from the store by setting the 'channel' parameter",
    )


def test_install_snaps_install_from_store_error(fake_executor, mocker):
    """Verify install_snaps raises an error when install_from_store fails."""
    mocker.patch(
        "craft_providers.actions.snap_installer.install_from_store",
        side_effect=SnapInstallationError(brief="test error"),
    )
    my_snaps = [Snap(name="snap1", channel="candidate")]
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, snaps=my_snaps)

    with pytest.raises(BaseConfigurationError) as exc_info:
        base._install_snaps(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
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
    my_snaps = [Snap(name="snap1", channel=None)]
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, snaps=my_snaps)

    with pytest.raises(BaseConfigurationError) as exc_info:
        base._install_snaps(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="failed to inject host's snap 'snap1' into target environment."
    )


def test_enable_yum_extra_repos(fake_executor, fake_process):
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "yum",
            "install",
            "-y",
            "epel-release",
            "centos-release-scl",
        ],
    )

    base._enable_yum_extra_repos(executor=fake_executor)


def test_setup_packages(fake_executor, fake_process):
    """Verify packages are installed as expected."""
    packages = ["grep", "git"]
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, packages=packages)
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "yum",
            "update",
            "-y",
        ]
    )

    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "yum",
            "install",
            "-y",
            "autoconf",
            "automake",
            "gcc",
            "gcc-c++",
            "git",
            "make",
            "patch",
            "rh-python38-python",
            "rh-python38-python-devel",
            "rh-python38-python-pip",
            "rh-python38-python-pip-wheel",
            "rh-python38-python-setuptools",
            "grep",
            "git",
        ]
    )

    base._setup_packages(executor=fake_executor)


def test_setup_yum_install_default(fake_executor, fake_process):
    """Verify only default packages are installed."""
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "yum", "update", "-y"])
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "yum",
            "install",
            "-y",
            "autoconf",
            "automake",
            "gcc",
            "gcc-c++",
            "git",
            "make",
            "patch",
            "rh-python38-python",
            "rh-python38-python-devel",
            "rh-python38-python-pip",
            "rh-python38-python-pip-wheel",
            "rh-python38-python-setuptools",
        ]
    )

    base._setup_packages(executor=fake_executor)


def test_setup_yum_install_override_system(fake_executor, fake_process):
    """Verify override default packages."""
    base = centos.CentOSBase(
        alias=centos.CentOSBaseAlias.SEVEN,
        packages=["clang"],
        use_default_packages=False,
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "yum", "update", "-y"])
    fake_process.register_subprocess(
        [
            *DEFAULT_FAKE_CMD,
            "yum",
            "install",
            "-y",
            "clang",
        ]
    )

    base._setup_packages(executor=fake_executor)


def test_setup_yum_install_packages_install_error(mocker, fake_executor, fake_process):
    """Verify error is caught from `yum install` call."""
    error = subprocess.CalledProcessError(100, ["error"])
    base = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    side_effects = [
        error,  # make yum install fail
        subprocess.CompletedProcess("args", returncode=0),  # network connectivity check
    ]
    mocker.patch.object(fake_executor, "execute_run", side_effect=side_effects)

    with pytest.raises(BaseConfigurationError) as exc_info:
        base._setup_packages(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to update system using yum.",
        details="* Command that failed: 'error'\n* Command exit code: 100",
    )


def test_ensure_image_version_compatible_failure(fake_executor, monkeypatch):
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    monkeypatch.setattr(
        InstanceConfiguration,
        "load",
        lambda **kwargs: InstanceConfiguration(compatibility_tag="invalid-tag"),
    )

    with pytest.raises(BaseCompatibilityError) as exc_info:
        base_config._ensure_instance_config_compatible(executor=fake_executor)

    assert exc_info.value == BaseCompatibilityError(
        "Expected image compatibility tag 'centos-base-v7', found 'invalid-tag'"
    )


def test_get_os_release(fake_process, fake_executor):
    """`_get_os_release` should parse data from `/etc/os-release` to a dict."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout='NAME="CentOS Linux"\nVERSION="7 (Core)"\nID="centos"\n'
        'ID_LIKE="rhel fedora"\nVERSION_ID="7"\n',
    )

    result = base_config._get_os_release(executor=fake_executor)

    assert result == {
        "NAME": "CentOS Linux",
        "ID": "centos",
        "VERSION": "7 (Core)",
        "VERSION_ID": "7",
        "ID_LIKE": "rhel fedora",
    }


def test_ensure_os_compatible(fake_executor, fake_process, mock_get_os_release):
    """Do nothing if the OS is compatible."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    base_config._ensure_os_compatible(executor=fake_executor)

    mock_get_os_release.assert_called_once()


def test_ensure_os_compatible_name_failure(
    fake_executor, fake_process, mock_get_os_release
):
    """Raise an error if the OS name does not match."""
    mock_get_os_release.return_value = {"ID": "ubuntu", "VERSION_ID": "22.04"}
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseCompatibilityError) as exc_info:
        base_config._ensure_os_compatible(executor=fake_executor)

    assert exc_info.value == BaseCompatibilityError(
        "Expected OS 'centos', found 'ubuntu'"
    )

    mock_get_os_release.assert_called_once()


def test_ensure_os_compatible_version_failure(
    fake_executor, fake_process, mock_get_os_release
):
    """Raise an error if the OS version id does not match."""
    mock_get_os_release.return_value = {"ID": "centos", "VERSION_ID": "8"}
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseCompatibilityError) as exc_info:
        base_config._ensure_os_compatible(executor=fake_executor)

    assert exc_info.value == BaseCompatibilityError(
        "Expected OS version '7', found '8'"
    )

    mock_get_os_release.assert_called_once()


def test_setup_hostname_failure(fake_process, fake_executor):
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "hostname", "-F", "/etc/hostname"],
        returncode=-1,
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._setup_hostname(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to set hostname.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_setup_snapd_proxy(fake_executor, fake_process):
    """Verify snapd proxy is set or unset."""
    environment = {
        "http_proxy": "http://foo.bar:8080",
        "https_proxy": "http://foo.bar:8081",
    }
    base_config = centos.CentOSBase(
        alias=centos.CentOSBaseAlias.SEVEN,
        environment=environment,  # type: ignore
    )
    fake_process.keep_last_process(True)
    fake_process.register([fake_process.any()])

    base_config._setup_snapd_proxy(executor=fake_executor)
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
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

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

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._setup_snapd_proxy(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to set the snapd proxy.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.usefixtures("stub_verify_network")
@pytest.mark.parametrize("fail_index", list(range(0, 2)))
def test_pre_setup_snapd_failures(fake_process, fake_executor, fail_index):
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    return_codes = [0, 0]
    return_codes[fail_index] = 1

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-active", "systemd-udevd"],
        stdout="inactive",
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "systemd-udevd"],
        returncode=return_codes[0],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "start", "systemd-udevd"],
        returncode=return_codes[1],
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._pre_setup_snapd(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to enable systemd-udevd service.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.usefixtures("stub_verify_network")
def test_setup_snapd_failures(fake_process, fake_executor):
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "yum", "install", "-y", "snapd"],
        returncode=1,
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._setup_snapd(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to setup snapd.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.parametrize("fail_index", list(range(0, 8)))
def test_post_setup_snapd_failures(fake_process, fake_executor, fail_index):
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    return_codes = [0] * 8
    return_codes[fail_index] = 1
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "ln", "-sf", "/var/lib/snapd/snap", "/snap"],
        returncode=return_codes[0],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "enable", "--now", "snapd.socket"],
        returncode=return_codes[1],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "restart", "snapd.service"],
        returncode=return_codes[2],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "wait", "system", "seed.loaded"],
        returncode=return_codes[3],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "refresh", "--hold"],
        returncode=return_codes[4],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "watch", "--last=auto-refresh?"],
        returncode=return_codes[5],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.http"],
        returncode=return_codes[6],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.https"],
        returncode=return_codes[7],
    )

    with pytest.raises(BaseConfigurationError):
        base_config._post_setup_snapd(executor=fake_executor)


@pytest.mark.parametrize("fail_index", list(range(0, 2)))
def test_post_warmup_snapd_failures(fake_process, fake_executor, fail_index):
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    return_codes = [0] * 2
    return_codes[fail_index] = 1
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.http"],
        returncode=return_codes[0],
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "unset", "system", "proxy.https"],
        returncode=return_codes[1],
    )

    with pytest.raises(BaseConfigurationError) as raised:
        base_config._warmup_snapd(executor=fake_executor)

    assert raised.value == BaseConfigurationError(
        brief="Failed to set the snapd proxy.",
        details=details_from_called_process_error(
            raised.value.__cause__  # type: ignore
        ),
    )


@pytest.mark.parametrize("alias", list(centos.CentOSBaseAlias))
@pytest.mark.parametrize("system_running_ready_stdout", ["degraded", "running"])
def test_wait_for_system_ready(
    fake_executor, fake_process, alias, system_running_ready_stdout
):
    base_config = centos.CentOSBase(alias=alias)
    base_config._retry_wait = 0.01
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

    base_config.wait_until_ready(executor=fake_executor)

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


@pytest.mark.parametrize("alias", list(centos.CentOSBaseAlias))
def test_wait_for_system_ready_timeout(fake_executor, fake_process, alias):
    base_config = centos.CentOSBase(
        alias=alias,
    )
    base_config._timeout_simple = 0.01
    base_config._retry_wait = 0.01
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"],
        stdout="not-ready",
        returncode=-1,
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config.wait_until_ready(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Timed out waiting for environment to be ready."
    )


@pytest.mark.parametrize("alias", list(centos.CentOSBaseAlias))
def test_wait_for_system_ready_timeout_in_network(
    fake_executor, fake_process, alias, monkeypatch
):
    base_config = centos.CentOSBase(alias=alias)
    base_config._timeout_simple = 0.01
    base_config._retry_wait = 0.01
    monkeypatch.setattr(
        base_config, "_setup_wait_for_system_ready", lambda **kwargs: None
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "getent", "hosts", "snapcraft.io"],
        returncode=-1,
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config.wait_until_ready(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Timed out waiting for networking to be ready."
    )


def test_update_compatibility_tag(fake_executor, mock_load):
    """`update_compatibility_tag()` should update the instance config."""
    base_config = centos.CentOSBase(
        alias=centos.CentOSBaseAlias.SEVEN, compatibility_tag="test-tag"
    )
    base_config._update_compatibility_tag(executor=fake_executor)

    assert fake_executor.records_of_push_file_io == [
        {
            "content": b"compatibility_tag: test-tag\n",
            "destination": "/etc/craft-instance.conf",
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        }
    ]


@pytest.mark.parametrize("status", [True, False])
def test_update_setup_status(fake_executor, mock_load, status):
    """`update_setup_status()` should update the instance config."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    base_config._update_setup_status(
        executor=fake_executor,
        status=status,
    )

    assert fake_executor.records_of_push_file_io == [
        {
            "content": (
                "compatibility_tag: centos-base-v7\n"
                f"setup: {str(status).lower()}\n".encode()
            ),
            "destination": "/etc/craft-instance.conf",
            "file_mode": "0644",
            "group": "root",
            "user": "root",
        }
    ]


def test_ensure_config_compatible_validation_error(
    fake_executor, mock_load, fake_validation_error
):
    mock_load.side_effect = fake_validation_error

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._ensure_instance_config_compatible(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to parse instance configuration file."
    )


def test_ensure_config_compatible_empty_config_returns_none(fake_executor, mock_load):
    mock_load.return_value = None

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    assert (
        base_config._ensure_instance_config_compatible(executor=fake_executor) is None
    )


def test_ensure_setup_completed(fake_executor, logs, mock_load):
    """Verify the setup was completed by checking the instance config file."""
    mock_load.return_value = InstanceConfiguration(setup=True)

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    assert base_config._ensure_setup_completed(executor=fake_executor) is None

    assert "Instance has already been setup." in logs.debug


def test_ensure_setup_completed_validation_error(
    fake_executor, mock_load, fake_validation_error
):
    """Raise an error when the instance config cannot be loaded."""
    mock_load.side_effect = fake_validation_error

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseCompatibilityError) as raised:
        base_config._ensure_setup_completed(executor=fake_executor)

    assert raised.value == BaseCompatibilityError(
        "failed to parse instance configuration file"
    )


def test_ensure_setup_completed_file_not_found_error(fake_executor, mock_load):
    """Raise an error when the instance config cannot be loaded."""
    mock_load.side_effect = FileNotFoundError

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseCompatibilityError) as raised:
        base_config._ensure_setup_completed(executor=fake_executor)

    assert raised.value == BaseCompatibilityError("failed to find instance config file")


def test_ensure_setup_completed_empty_config(fake_executor, mock_load):
    """Raise an error if the instance config is empty."""
    mock_load.return_value = None

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseCompatibilityError) as raised:
        base_config._ensure_setup_completed(executor=fake_executor)

    assert raised.value == BaseCompatibilityError("instance config is empty")


@pytest.mark.parametrize("status", [None, False])
def test_ensure_setup_completed_not_setup(status, fake_executor, mock_load):
    """Raise an error if the setup was not completed (setup field is None or False)."""
    mock_load.return_value = InstanceConfiguration(setup=status)

    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    with pytest.raises(BaseCompatibilityError) as raised:
        base_config._ensure_setup_completed(executor=fake_executor)

    assert raised.value == BaseCompatibilityError("instance is marked as not setup")


@pytest.mark.parametrize(
    "environment",
    [
        None,
        {
            "https_proxy": "http://foo.bar:8081",
            "http_proxy": "http://foo.bar:8080",
        },
    ],
)
@pytest.mark.parametrize("cache_path", [None, pathlib.Path("/tmp")])
def test_warmup_overall(
    environment, fake_process, fake_executor, mock_load, mocker, cache_path
):
    mock_load.return_value = InstanceConfiguration(
        compatibility_tag="centos-base-v7", setup=True
    )
    alias = centos.CentOSBaseAlias.SEVEN

    if environment is None:
        environment = centos.CentOSBase.default_command_environment()

    base_config = centos.CentOSBase(alias=alias, environment=environment)

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
            VERSION_ID="{alias.value}"
            """
        ),
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "systemctl", "is-system-running"], stdout="degraded"
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "bash", "-c", "echo -n ${XDG_CACHE_HOME:-${HOME}/.cache}"],
        stdout="/root/.cache",
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
    mock_load.return_value = InstanceConfiguration(
        compatibility_tag="centos-base-v7", setup=True
    )
    base_config = centos.CentOSBase(
        alias=centos.CentOSBaseAlias.SEVEN,
        environment=centos.CentOSBase.default_command_environment(),
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
    mock_load.return_value = InstanceConfiguration(
        compatibility_tag="centos-base-v7", setup=True
    )
    alias = centos.CentOSBaseAlias.SEVEN
    base_config = centos.CentOSBase(
        alias=alias,
        environment=centos.CentOSBase.default_command_environment(),
    )
    base_config.compatibility_tag = "different-tag"

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
            VERSION_ID="{alias.value}"
            """
        ),
    )

    with pytest.raises(BaseCompatibilityError):
        base_config.warmup(executor=fake_executor)


@pytest.mark.parametrize("setup", [False, None])
def test_warmup_not_setup(setup, fake_process, fake_executor, mock_load):
    """Raise a BaseConfigurationError if the instance is not setup."""
    mock_load.return_value = InstanceConfiguration(
        compatibility_tag="centos-base-v7", setup=setup
    )
    alias = centos.CentOSBaseAlias.SEVEN
    base_config = centos.CentOSBase(
        alias=alias,
        environment=centos.CentOSBase.default_command_environment(),
    )

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
            VERSION_ID="{alias.value}"
            """
        ),
    )

    with pytest.raises(BaseCompatibilityError) as raised:
        base_config.warmup(executor=fake_executor)

    assert raised.value == BaseCompatibilityError("instance is marked as not setup")


def test_warmup_never_ready(fake_process, fake_executor, mock_load):
    mock_load.return_value = InstanceConfiguration(
        compatibility_tag="centos-base-v7", setup=True
    )
    alias = centos.CentOSBaseAlias.SEVEN
    base_config = centos.CentOSBase(
        alias=alias,
        environment=centos.CentOSBase.default_command_environment(),
    )
    base_config._timeout_simple = 0.01
    base_config._retry_wait = 0.02

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
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
        base_config.warmup(executor=fake_executor)


def test_warmup_never_network(fake_process, fake_executor, mock_load):
    mock_load.return_value = InstanceConfiguration(
        compatibility_tag="centos-base-v7", setup=True
    )
    alias = centos.CentOSBaseAlias.SEVEN
    base_config = centos.CentOSBase(
        alias=alias,
        environment=centos.CentOSBase.default_command_environment(),
    )
    base_config._timeout_simple = 0.01
    base_config._retry_wait = 0.02

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "bash", "-c", "echo -n ${XDG_CACHE_HOME:-${HOME}/.cache}"],
        stdout="/root/.cache",
    )
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "cat", "/etc/os-release"],
        stdout=dedent(
            f"""\
            NAME="CentOS Linux"
            ID="centos"
            ID_LIKE="rhel fedora"
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
        base_config.warmup(executor=fake_executor)


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
    base_config = centos.CentOSBase(
        alias=centos.CentOSBaseAlias.SEVEN,
        hostname=hostname,
    )

    assert base_config._hostname == hostname
    assert Exact(f"Using hostname '{hostname}'") in logs.debug


@pytest.mark.parametrize(
    ("hostname", "expected_hostname"),
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
    base_config = centos.CentOSBase(
        alias=centos.CentOSBaseAlias.SEVEN,
        hostname=hostname,
    )

    assert base_config._hostname == expected_hostname
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
        centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN, hostname=hostname)

    assert error.value == BaseConfigurationError(
        brief=f"failed to create base with hostname {hostname!r}.",
        details="hostname must contain at least one alphanumeric character",
    )


def test_execute_run_default(fake_executor):
    """Default _execute_run behaviour."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]
    with patch.object(fake_executor, "execute_run") as mock:
        base_config._execute_run(command, executor=fake_executor)

    mock.assert_called_with(
        command, check=True, capture_output=True, text=False, timeout=None
    )


def test_execute_run_options_for_run(fake_executor):
    """Different options to control how run is called."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]
    with patch.object(fake_executor, "execute_run") as mock:
        base_config._execute_run(
            command,
            executor=fake_executor,
            check=False,
            capture_output=False,
            text=True,
            timeout=None,
        )

    mock.assert_called_with(
        command, check=False, capture_output=False, text=True, timeout=None
    )


def test_execute_run_command_failed_no_verify_network(fake_process, fake_executor):
    """The command failed but network verification was not asked."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, *command], returncode=1)

    # we know that network is not verified because otherwise we'll get
    # a ProcessNotRegisteredError for the verification process
    with pytest.raises(subprocess.CalledProcessError):
        base_config._execute_run(command, executor=fake_executor)


@pytest.mark.parametrize("proxy_variable_name", ["HTTPS_PROXY", "https_proxy"])
def test_execute_run_command_failed_verify_network_proxy(
    fake_process, fake_executor, monkeypatch, proxy_variable_name
):
    """The command failed, network verification was asked, but there is a proxy."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, *command], returncode=1)

    monkeypatch.setenv(proxy_variable_name, "https://someproxy.net:8080/")

    # we know that network is not verified because otherwise we'll get
    # a ProcessNotRegisteredError for the verification process
    with pytest.raises(subprocess.CalledProcessError):
        base_config._execute_run(command, executor=fake_executor, verify_network=True)


def test_execute_run_verify_network_run_ok(fake_process, fake_executor):
    """Indicated network verification but process completed ok."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, *command], returncode=0)

    # we know that network is not verified because otherwise we'll get
    # a ProcessNotRegisteredError for the verification process
    proc = base_config._execute_run(
        command, executor=fake_executor, verify_network=True
    )
    assert proc.returncode == 0


@pytest.mark.usefixtures("stub_verify_network")
def test_execute_run_verify_network_connectivity_ok(fake_process, fake_executor):
    """Network verified after process failure, connectivity ok."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]

    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, *command], returncode=1)

    with pytest.raises(subprocess.CalledProcessError):
        base_config._execute_run(command, executor=fake_executor, verify_network=True)


def test_execute_run_verify_network_connectivity_missing(fake_process, fake_executor):
    """Network verified after process failure, no connectivity."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    command = ["the", "command"]

    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "bash", "-c", "exec 3<> /dev/tcp/snapcraft.io/443"],
        returncode=1,
    )
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, *command], returncode=1)

    with pytest.raises(NetworkError) as exc_info:
        base_config._execute_run(command, executor=fake_executor, verify_network=True)
    assert isinstance(exc_info.value.__cause__, subprocess.CalledProcessError)


def test_execute_run_bad_check_verifynetwork_combination(fake_executor):
    """Cannot ask for network verification and avoid checking."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    with pytest.raises(RuntimeError):
        base_config._execute_run(
            ["cmd"], executor=fake_executor, check=False, verify_network=True
        )


@pytest.mark.usefixtures("stub_verify_network")
def test_network_connectivity_yes(fake_executor, fake_process):
    """Connectivity is ok."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)

    assert base_config._network_connected(executor=fake_executor) is True


def test_network_connectivity_no(fake_executor, fake_process):
    """Connectivity missing."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "bash", "-c", "exec 3<> /dev/tcp/snapcraft.io/443"],
        returncode=1,
    )
    assert base_config._network_connected(executor=fake_executor) is False


def test_network_connectivity_timeouts(fake_executor, fake_process):
    """Check that timeout is used.

    This test does not register the fake subprocess with a long wait because to make it
    resilient to CIs it would need a too long waiting.
    """
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    cmd = ["bash", "-c", "exec 3<> /dev/tcp/snapcraft.io/443"]
    timeout_expired = subprocess.TimeoutExpired(cmd, timeout=5)
    with patch.object(
        fake_executor, "execute_run", side_effect=timeout_expired
    ) as mock:
        assert base_config._network_connected(executor=fake_executor) is False
    mock.assert_called_with(cmd, check=False, capture_output=True, timeout=10)


def test_disable_and_wait_for_snap_refresh_hold_error(fake_process, fake_executor):
    """Raise BaseConfigurationError when the command to hold snap refreshes fails."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "refresh", "--hold"],
        returncode=-1,
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._disable_and_wait_for_snap_refresh(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to hold snap refreshes.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_disable_and_wait_for_snap_refresh_wait_error(fake_process, fake_executor):
    """Raise BaseConfigurationError when the `snap watch` command fails."""
    base_config = centos.CentOSBase(alias=centos.CentOSBaseAlias.SEVEN)
    fake_process.register_subprocess([*DEFAULT_FAKE_CMD, "snap", "refresh", "--hold"])
    fake_process.register_subprocess(
        [*DEFAULT_FAKE_CMD, "snap", "watch", "--last=auto-refresh?"],
        returncode=-1,
    )

    with pytest.raises(BaseConfigurationError) as exc_info:
        base_config._disable_and_wait_for_snap_refresh(executor=fake_executor)

    assert exc_info.value == BaseConfigurationError(
        brief="Failed to wait for snap refreshes to complete.",
        details=details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )
