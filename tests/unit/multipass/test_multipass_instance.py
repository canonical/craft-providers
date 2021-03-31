# Copyright 2021 Canonical Ltd.
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
import copy
import io
import pathlib
import subprocess
import sys
from unittest import mock

import pytest

from craft_providers import errors
from craft_providers.multipass import Multipass, MultipassInstance
from craft_providers.multipass.errors import MultipassError

if sys.platform == "win32":
    EXAMPLE_MOUNTS = {
        "/root/project": {
            "gid_mappings": ["-2:default"],
            "source_path": "<insert>",
            "uid_mappings": ["-2:default"],
        }
    }
else:
    EXAMPLE_MOUNTS = {
        "/root/project": {
            "gid_mappings": ["1000:0"],
            "source_path": "<insert>",
            "uid_mappings": ["1000:0"],
        }
    }

EXAMPLE_INFO = {
    "errors": [],
    "info": {
        "flowing-hawfinch": {
            "disks": {"sda1": {}},
            "image_hash": "c5f2f08c6a1adee1f2f96d84856bf0162d33ea182dae0e8ed45768a86182d110",
            "image_release": "20.04 LTS",
            "ipv4": [],
            "load": [],
            "memory": {},
            "mounts": {},
            "release": "",
            "state": "Stopped",
        },
        "test-instance": {
            "disks": {"sda1": {"total": "266219864064", "used": "1457451008"}},
            "image_hash": "7c5c8f24046ca7b82897e0ca49fbd4dbdc771c2abd616991d10e6e09cc43002f",
            "image_release": "Snapcraft builder for Core 18",
            "ipv4": ["10.114.154.133"],
            "load": [1.53, 0.84, 0.33],
            "memory": {"total": 2089697280, "used": 153190400},
            "mounts": EXAMPLE_MOUNTS,
            "release": "Ubuntu 18.04.5 LTS",
            "state": "Running",
        },
    },
}


@pytest.fixture
def project_path(tmp_path):
    project_path = tmp_path / "git" / "project"
    project_path.mkdir(parents=True)
    yield project_path


@pytest.fixture(autouse=True)
def mock_multipass(project_path):
    with mock.patch(
        "craft_providers.multipass.multipass_instance.Multipass", spec=Multipass
    ) as multipass_mock:
        platform_info = copy.deepcopy(EXAMPLE_INFO)
        platform_info["info"]["test-instance"]["mounts"]["/root/project"][
            "source_path"
        ] = project_path.as_posix()

        multipass_mock.info.return_value = platform_info

        multipass_mock.list.return_value = ["flowing-hawfinch", "test-instance"]
        yield multipass_mock


@pytest.fixture
def instance(mock_multipass):
    yield MultipassInstance(name="test-instance", multipass=mock_multipass)


@pytest.fixture
def mock_os_getgid():
    """Mock os_getgid(), creating (non-existent) attribute on Windows."""
    create = False
    if sys.platform == "win32":
        create = True

    with mock.patch("os.getgid", create=create, return_value=1234) as getgid_mock:
        yield getgid_mock


@pytest.fixture
def mock_os_getuid():
    """Mock os_getuid(), creating (non-existent) attribute on Windows."""
    create = False
    if sys.platform == "win32":
        create = True

    with mock.patch("os.getuid", create=create, return_value=4567) as getuid_mock:
        yield getuid_mock


def test_create_file(mock_multipass, instance):
    mock_multipass.exec.side_effect = [
        mock.Mock(stdout="/tmp/mktemp-result\n"),
        None,
        None,
        None,
        None,
    ]

    instance.create_file(
        destination=pathlib.Path("/etc/test.conf"),
        content=io.BytesIO(b"foo"),
        file_mode="0644",
    )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["mktemp"],
            runner=subprocess.run,
            capture_output=True,
            check=True,
            text=True,
        ),
        mock.call.transfer_source_io(
            source=mock.ANY, destination="test-instance:/tmp/mktemp-result"
        ),
        mock.call.exec(
            instance_name="test-instance",
            command=[
                "sudo",
                "-H",
                "--",
                "sudo",
                "chown",
                "root:root",
                "/tmp/mktemp-result",
            ],
            runner=subprocess.run,
            capture_output=True,
            check=True,
        ),
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "sudo", "chmod", "0644", "/tmp/mktemp-result"],
            runner=subprocess.run,
            capture_output=True,
            check=True,
        ),
        mock.call.exec(
            instance_name="test-instance",
            command=[
                "sudo",
                "-H",
                "--",
                "sudo",
                "mv",
                "/tmp/mktemp-result",
                "/etc/test.conf",
            ],
            runner=subprocess.run,
            capture_output=True,
            check=True,
        ),
    ]


def test_create_file_error(mock_multipass, instance):
    error = subprocess.CalledProcessError(-1, ["mktemp"], "test stdout", "test stderr")

    mock_multipass.exec.side_effect = error

    with pytest.raises(MultipassError) as exc_info:
        instance.create_file(
            destination=pathlib.Path("/etc/test.conf"),
            content=io.BytesIO(b"foo"),
            file_mode="0644",
        )

    assert exc_info.value == MultipassError(
        brief="Failed to create file '/etc/test.conf' in 'test-instance' VM.",
        details=errors.details_from_called_process_error(error),
    )


def test_delete(mock_multipass, instance):
    instance.delete()

    assert mock_multipass.mock_calls == [
        mock.call.delete(instance_name="test-instance", purge=True)
    ]


def test_execute_popen(mock_multipass, instance):
    instance.execute_popen(command=["test-command", "flags"], input="foo")

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test-command", "flags"],
            runner=subprocess.Popen,
            input="foo",
        )
    ]


def test_execute_popen_with_env(mock_multipass, instance):
    instance.execute_popen(command=["test-command", "flags"], env=dict(foo="bar"))

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "env", "foo=bar", "test-command", "flags"],
            runner=subprocess.Popen,
        )
    ]


def test_execute_run(mock_multipass, instance):
    instance.execute_run(command=["test-command", "flags"], input="foo")

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test-command", "flags"],
            runner=subprocess.run,
            input="foo",
        )
    ]


def test_execute_run_with_env(mock_multipass, instance):
    instance.execute_run(command=["test-command", "flags"], env=dict(foo="bar"))

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "env", "foo=bar", "test-command", "flags"],
            runner=subprocess.run,
        )
    ]


def test_execute_run_with_env_unset(mock_multipass, instance):
    instance.execute_run(
        command=["test-command", "flags"], env=dict(foo="bar", TERM=None)
    )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=[
                "sudo",
                "-H",
                "--",
                "env",
                "foo=bar",
                "-u",
                "TERM",
                "test-command",
                "flags",
            ],
            runner=subprocess.run,
        )
    ]


def test_exists(mock_multipass, instance):
    assert instance.exists() is True
    assert mock_multipass.mock_calls == [mock.call.list()]


def test_exists_false(mock_multipass):
    assert (
        MultipassInstance(name="does-not-exist", multipass=mock_multipass).exists()
        is False
    )
    assert mock_multipass.mock_calls == [mock.call.list()]


def test_is_mounted_false(mock_multipass, instance):
    project_path = pathlib.Path.home() / "not-mounted"

    assert (
        instance.is_mounted(
            host_source=pathlib.Path(project_path),
            target=pathlib.Path("/root/project"),
        )
        is False
    )

    assert mock_multipass.mock_calls == [mock.call.info(instance_name="test-instance")]


def test_is_mounted_true(mock_multipass, instance, project_path):
    assert (
        instance.is_mounted(
            host_source=project_path,
            target=pathlib.Path("/root/project"),
        )
        is True
    )

    assert mock_multipass.mock_calls == [mock.call.info(instance_name="test-instance")]


def test_is_running_false(mock_multipass):
    assert (
        MultipassInstance(
            name="flowing-hawfinch", multipass=mock_multipass
        ).is_running()
        is False
    )

    assert mock_multipass.mock_calls == [
        mock.call.info(instance_name="flowing-hawfinch")
    ]


def test_is_running_true(mock_multipass, instance):
    assert instance.is_running() is True

    assert mock_multipass.mock_calls == [mock.call.info(instance_name="test-instance")]


def test_launch(mock_multipass, instance):
    instance.launch(image="test-image")

    assert mock_multipass.mock_calls == [
        mock.call.launch(
            instance_name="test-instance",
            image="test-image",
            cpus="2",
            disk="256G",
            mem="2G",
        )
    ]


def test_launch_all_opts(mock_multipass, instance):
    instance.launch(image="test-image", cpus=4, disk_gb=5, mem_gb=6)

    assert mock_multipass.mock_calls == [
        mock.call.launch(
            instance_name="test-instance",
            image="test-image",
            cpus="4",
            disk="5G",
            mem="6G",
        )
    ]


def test_mount(mock_multipass, project_path, mock_os_getgid, mock_os_getuid):
    MultipassInstance(name="flowing-hawfinch", multipass=mock_multipass).mount(
        host_source=project_path,
        target=pathlib.Path("/root/project"),
    )

    if sys.platform == "win32":
        gid_map = None
        uid_map = None
    else:
        gid_map = {str(mock_os_getgid.return_value): "0"}
        uid_map = {str(mock_os_getuid.return_value): "0"}

    assert mock_multipass.mock_calls == [
        mock.call.info(instance_name="flowing-hawfinch"),
        mock.call.mount(
            source=project_path,
            target="flowing-hawfinch:/root/project",
            uid_map=uid_map,
            gid_map=gid_map,
        ),
    ]

    if sys.platform == "win32":
        assert mock_os_getgid.mock_calls == []
        assert mock_os_getuid.mock_calls == []
    else:
        assert mock_os_getgid.mock_calls == [mock.call()]
        assert mock_os_getuid.mock_calls == [mock.call()]


def test_mount_all_opts(mock_multipass, project_path):
    if sys.platform == "win32":
        with pytest.raises(MultipassError) as exc_info:
            MultipassInstance(name="flowing-hawfinch", multipass=mock_multipass).mount(
                host_source=project_path,
                target=pathlib.Path("/root/project"),
                host_uid="1",
                host_gid="2",
            )

        assert exc_info.value == MultipassError(
            brief="Mounting with user/group ID mappings is not supported on Windows"
        )
    else:
        MultipassInstance(name="flowing-hawfinch", multipass=mock_multipass).mount(
            host_source=project_path,
            target=pathlib.Path("/root/project"),
            host_uid="1",
            host_gid="2",
        )

        assert mock_multipass.mock_calls == [
            mock.call.info(instance_name="flowing-hawfinch"),
            mock.call.mount(
                source=project_path,
                target="flowing-hawfinch:/root/project",
                uid_map={"1": "0"},
                gid_map={"2": "0"},
            ),
        ]


def test_mount_already_mounted(mock_multipass, instance, project_path):
    instance.mount(
        host_source=project_path,
        target=pathlib.Path("/root/project"),
    )

    assert mock_multipass.mock_calls == [mock.call.info(instance_name="test-instance")]


def test_pull_file(mock_multipass, instance, tmp_path):
    mock_multipass.exec.return_value = mock.Mock(returncode=0)

    source = pathlib.Path("/tmp/src.txt")
    destination = tmp_path / "dst.txt"

    instance.pull_file(
        source=source,
        destination=destination,
    )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test", "-f", "/tmp/src.txt"],
            runner=subprocess.run,
            check=False,
        ),
        mock.call.transfer(
            source="test-instance:/tmp/src.txt", destination=str(destination)
        ),
    ]


def test_pull_file_no_source(mock_multipass, instance, tmp_path):
    mock_multipass.exec.return_value = mock.Mock(returncode=1)

    source = pathlib.Path("/tmp/src.txt")
    destination = tmp_path / "dst.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.pull_file(
            source=source,
            destination=destination,
        )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test", "-f", "/tmp/src.txt"],
            runner=subprocess.run,
            check=False,
        ),
    ]
    assert str(exc_info.value) == "File not found: '/tmp/src.txt'"


def test_pull_file_no_parent_directory(mock_multipass, instance, tmp_path):
    mock_multipass.exec.return_value = mock.Mock(returncode=0)

    source = pathlib.Path("/tmp/src.txt")
    destination = tmp_path / "not-created" / "dst.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.pull_file(
            source=source,
            destination=destination,
        )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test", "-f", "/tmp/src.txt"],
            runner=subprocess.run,
            check=False,
        ),
    ]
    assert str(exc_info.value) == f"Directory not found: {str(destination.parent)!r}"


def test_push_file(mock_multipass, instance, tmp_path):
    mock_multipass.exec.return_value = mock.Mock(returncode=0)

    source = tmp_path / "src.txt"
    source.write_text("this is a test")
    destination = pathlib.Path("/tmp/dst.txt")

    instance.push_file(
        source=source,
        destination=destination,
    )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test", "-d", "/tmp"],
            runner=subprocess.run,
            check=False,
        ),
        mock.call.transfer(
            source=str(source), destination="test-instance:/tmp/dst.txt"
        ),
    ]


def test_push_file_no_source(mock_multipass, instance, tmp_path):
    source = tmp_path / "src.txt"
    destination = pathlib.Path("/tmp/dst.txt")

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.push_file(
            source=source,
            destination=destination,
        )

    assert mock_multipass.mock_calls == []
    assert str(exc_info.value) == f"File not found: {str(source)!r}"


def test_push_file_no_parent_directory(mock_multipass, instance, tmp_path):
    mock_multipass.exec.return_value = mock.Mock(returncode=1)

    source = tmp_path / "src.txt"
    source.write_text("this is a test")
    destination = pathlib.Path("/tmp/dst.txt")

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.push_file(
            source=source,
            destination=destination,
        )

    assert mock_multipass.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["sudo", "-H", "--", "test", "-d", "/tmp"],
            runner=subprocess.run,
            check=False,
        ),
    ]
    assert str(exc_info.value) == "Directory not found: '/tmp'"


def test_start(mock_multipass, instance):
    instance.start()

    assert mock_multipass.mock_calls == [mock.call.start(instance_name="test-instance")]


def test_stop(mock_multipass, instance):
    instance.stop()

    assert mock_multipass.mock_calls == [
        mock.call.stop(instance_name="test-instance", delay_mins=0)
    ]


def test_stop_all_opts(mock_multipass, instance):
    instance.stop(delay_mins=4)

    assert mock_multipass.mock_calls == [
        mock.call.stop(instance_name="test-instance", delay_mins=4)
    ]


def test_unmount(mock_multipass, instance):
    instance.unmount(target=pathlib.Path("/mnt"))

    assert mock_multipass.mock_calls == [mock.call.umount(mount="test-instance:/mnt")]


def test_unmount_all(mock_multipass, instance):
    instance.unmount_all()

    assert mock_multipass.mock_calls == [mock.call.umount(mount="test-instance")]
