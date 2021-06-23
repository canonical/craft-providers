#
# Copyright 2021 Canonical Ltd.
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
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

import pytest

from craft_providers import errors
from craft_providers.lxd import LXC, LXDError, LXDInstance


@pytest.fixture
def project_path(tmp_path):
    project_path = tmp_path / "git" / "project"
    project_path.mkdir(parents=True)
    yield project_path


@pytest.fixture(autouse=True)
def mock_lxc(project_path):
    with mock.patch("craft_providers.lxd.lxd_instance.LXC", spec=LXC) as lxc:
        lxc.list.return_value = [
            {"name": "test-instance", "status": "Running"},
            {"name": "stopped-instance", "status": "Stopped"},
        ]
        lxc.config_device_show.return_value = {
            "test_mount": {
                "path": "/root/project",
                "source": project_path.as_posix(),
                "type": "disk",
            },
            "disk-/target": {
                "path": "/target",
                "source": "/source",
                "type": "disk",
            },
        }
        lxc.info.return_value = {
            "environment": {"kernel_features": {}},
        }
        yield lxc


@pytest.fixture
def mock_named_temporary_file():
    with mock.patch(
        "craft_providers.lxd.lxd_instance.tempfile.NamedTemporaryFile",
        spec=tempfile.NamedTemporaryFile,
    ) as mock_tf:
        mock_tf.return_value.__enter__.return_value.name = "test-tmp-file"
        yield mock_tf.return_value


@pytest.fixture
def mock_shutil_copyfileobj():
    with mock.patch.object(shutil, "copyfileobj") as mock_copyfileobj:
        yield mock_copyfileobj


@pytest.fixture
def mock_os_unlink():
    with mock.patch.object(os, "unlink") as mock_unlink:
        yield mock_unlink


@pytest.fixture
def instance(mock_lxc):
    yield LXDInstance(name="test-instance", lxc=mock_lxc)


def test_push_file_io(
    mock_lxc,
    mock_named_temporary_file,
    mock_shutil_copyfileobj,
    mock_os_unlink,
    instance,
):
    mock_lxc.exec.side_effect = [
        None,
        None,
        None,
        None,
    ]

    instance.push_file_io(
        destination=pathlib.Path("/etc/test.conf"),
        content=io.BytesIO(b"foo"),
        file_mode="0644",
    )

    assert mock_lxc.mock_calls == [
        mock.call.file_push(
            instance_name="test-instance",
            source=pathlib.Path("test-tmp-file"),
            destination=pathlib.Path("/etc/test.conf"),
            mode="0644",
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.exec(
            instance_name="test-instance",
            command=[
                "chown",
                "root:root",
                "/etc/test.conf",
            ],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            capture_output=True,
            check=True,
        ),
    ]

    assert mock_named_temporary_file.mock_calls == [
        mock.call.__enter__(),
        mock.call.__exit__(None, None, None),
    ]
    assert mock_shutil_copyfileobj.mock_calls == [
        mock.call(mock.ANY, mock_named_temporary_file.__enter__.return_value)
    ]
    assert mock_os_unlink.mock_calls == [mock.call("test-tmp-file")]


def test_push_file_io_error(mock_lxc, instance):
    error = subprocess.CalledProcessError(
        -1, ["chown", "root:root", "/etc/test.conf"], "test stdout", "test stderr"
    )

    mock_lxc.exec.side_effect = error

    with pytest.raises(LXDError) as exc_info:
        instance.push_file_io(
            destination=pathlib.Path("/etc/test.conf"),
            content=io.BytesIO(b"foo"),
            file_mode="0644",
        )

    assert exc_info.value == LXDError(
        brief="Failed to create file '/etc/test.conf' in instance 'test-instance'.",
        details=errors.details_from_called_process_error(error),
    )


def test_delete(mock_lxc, instance):
    instance.delete()

    assert mock_lxc.mock_calls == [
        mock.call.delete(
            instance_name="test-instance",
            project=instance.project,
            remote=instance.remote,
            force=True,
        )
    ]


def test_execute_popen(mock_lxc, instance):
    instance.execute_popen(command=["test-command", "flags"], input="foo")

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["test-command", "flags"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.Popen,
            input="foo",
        )
    ]


def test_execute_popen_with_env(mock_lxc, instance):
    instance.execute_popen(command=["test-command", "flags"], env=dict(foo="bar"))

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["env", "foo=bar", "test-command", "flags"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.Popen,
        )
    ]


def test_execute_run(mock_lxc, instance):
    instance.execute_run(command=["test-command", "flags"], input="foo")

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["test-command", "flags"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            input="foo",
        )
    ]


def test_execute_run_with_default_command_env(mock_lxc):
    instance = LXDInstance(
        name="test-instance",
        default_command_environment={"env_key": "some-value"},
        lxc=mock_lxc,
    )

    instance.execute_run(command=["test-command", "flags"], env=dict(foo="bar"))

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["env", "env_key=some-value", "foo=bar", "test-command", "flags"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
        )
    ]


def test_execute_run_with_default_command_env_unset(mock_lxc):
    instance = LXDInstance(
        name="test-instance",
        default_command_environment={"env_key": "some-value"},
        lxc=mock_lxc,
    )

    instance.execute_run(
        command=["test-command", "flags"], env={"foo": "bar", "env_key": None}
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["env", "-u", "env_key", "foo=bar", "test-command", "flags"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
        )
    ]


def test_execute_run_with_env(mock_lxc, instance):
    instance.execute_run(command=["test-command", "flags"], env=dict(foo="bar"))

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=["env", "foo=bar", "test-command", "flags"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
        )
    ]


def test_execute_run_with_env_unset(mock_lxc, instance):
    instance.execute_run(
        command=["test-command", "flags"], env=dict(foo="bar", TERM=None)
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name="test-instance",
            command=[
                "env",
                "foo=bar",
                "-u",
                "TERM",
                "test-command",
                "flags",
            ],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
        )
    ]


def test_exists(mock_lxc, instance):
    assert instance.exists() is True
    assert mock_lxc.mock_calls == [
        mock.call.list(project=instance.project, remote=instance.remote)
    ]


def test_exists_false(mock_lxc):
    instance = LXDInstance(name="does-not-exist", lxc=mock_lxc)

    assert instance.exists() is False
    assert mock_lxc.mock_calls == [
        mock.call.list(project=instance.project, remote=instance.remote)
    ]


def test_get_disk_devices_path_parse_error(mock_lxc, instance):
    mock_lxc.config_device_show.return_value = {
        "mount_missing_path": {
            "source": "/foo",
            "type": "disk",
        },
    }

    with pytest.raises(LXDError) as exc_info:
        instance._get_disk_devices()  # pylint: disable=protected-access

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc device 'mount_missing_path'.",
        details="* Device configuration: {'mount_missing_path': {'source': '/foo', 'type': 'disk'}}",
    )


def test_get_disk_devices_source_parse_error(mock_lxc, instance):
    mock_lxc.config_device_show.return_value = {
        "mount_missing_source": {
            "path": "/foo",
            "type": "disk",
        },
    }

    with pytest.raises(LXDError) as exc_info:
        instance._get_disk_devices()  # pylint: disable=protected-access

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc device 'mount_missing_source'.",
        details="* Device configuration: {'mount_missing_source': {'path': '/foo', 'type': 'disk'}}",
    )


def test_is_mounted_false(mock_lxc, instance):
    project_path = pathlib.Path.home() / "not-mounted"

    assert (
        instance.is_mounted(
            host_source=pathlib.Path(project_path),
            target=pathlib.Path("/root/project"),
        )
        is False
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_is_mounted_true(mock_lxc, instance, project_path):
    assert (
        instance.is_mounted(
            host_source=project_path,
            target=pathlib.Path("/root/project"),
        )
        is True
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_is_running_false(mock_lxc):
    instance = LXDInstance(name="stopped-instance", lxc=mock_lxc)

    assert instance.is_running() is False

    assert mock_lxc.mock_calls == [
        mock.call.list(project=instance.project, remote=instance.remote)
    ]


def test_is_running_true(mock_lxc, instance):
    assert instance.is_running() is True

    assert mock_lxc.mock_calls == [
        mock.call.list(project=instance.project, remote=instance.remote)
    ]


def test_is_running_error(mock_lxc):
    instance = LXDInstance(name="invalid-instance", lxc=mock_lxc)

    with pytest.raises(LXDError) as exc_info:
        instance.is_running()

    assert exc_info.value == LXDError(
        brief="Instance 'invalid-instance' does not exist.",
    )


def test_launch(mock_lxc, instance):
    instance.launch(
        image="20.04",
        image_remote="ubuntu",
    )

    assert mock_lxc.mock_calls == [
        mock.call.info(project=instance.project, remote=instance.remote),
        mock.call.launch(
            config_keys={},
            ephemeral=False,
            instance_name=instance.name,
            image="20.04",
            image_remote="ubuntu",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on windows")
def test_launch_all_opts(mock_lxc, instance):
    instance.launch(
        image="20.04",
        image_remote="ubuntu",
        ephemeral=True,
        map_user_uid=True,
    )

    uid = str(os.getuid())
    assert mock_lxc.mock_calls == [
        mock.call.info(project=instance.project, remote=instance.remote),
        mock.call.launch(
            config_keys={"raw.idmap": f"both {uid} 0"},
            ephemeral=True,
            instance_name=instance.name,
            image="20.04",
            image_remote="ubuntu",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_launch_with_mknod(mock_lxc, instance):
    mock_lxc.info.return_value = {
        "environment": {"kernel_features": {"seccomp_listener": "true"}}
    }

    instance.launch(
        image="20.04",
        image_remote="ubuntu",
    )

    assert mock_lxc.mock_calls == [
        mock.call.info(project=instance.project, remote=instance.remote),
        mock.call.launch(
            config_keys={
                "security.syscalls.intercept.mknod": "true",
            },
            ephemeral=False,
            instance_name=instance.name,
            image="20.04",
            image_remote="ubuntu",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_mount(mock_lxc, tmp_path, instance):
    instance.mount(host_source=tmp_path, target=pathlib.Path("/mnt/foo"))

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_add_disk(
            instance_name=instance.name,
            source=tmp_path,
            path=pathlib.Path("/mnt/foo"),
            device="disk-/mnt/foo",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_mount_all_opts(mock_lxc, tmp_path, instance):
    instance.mount(
        host_source=tmp_path, target=pathlib.Path("/mnt/foo"), device_name="disk-xfoo"
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_add_disk(
            instance_name=instance.name,
            source=tmp_path,
            path=pathlib.Path("/mnt/foo"),
            device="disk-xfoo",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_mount_already_mounted(mock_lxc, instance, project_path):
    instance.mount(
        host_source=project_path,
        target=pathlib.Path("/root/project"),
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_pull_file(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=0)

    source = pathlib.Path("/tmp/src.txt")
    destination = tmp_path / "dst.txt"

    instance.pull_file(
        source=source,
        destination=destination,
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.name,
            command=["test", "-f", "/tmp/src.txt"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
        ),
        mock.call.file_pull(
            instance_name=instance.name,
            source=source,
            destination=destination,
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_pull_file_no_source(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=1)

    source = pathlib.Path("/tmp/src.txt")
    destination = tmp_path / "dst.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.pull_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.name,
            command=["test", "-f", "/tmp/src.txt"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
        ),
    ]
    assert str(exc_info.value) == "File not found: '/tmp/src.txt'"


def test_pull_file_no_parent_directory(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=0)

    source = pathlib.Path("/tmp/src.txt")
    destination = tmp_path / "not-created" / "dst.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.pull_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.name,
            command=["test", "-f", "/tmp/src.txt"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
        ),
    ]
    assert str(exc_info.value) == f"Directory not found: {str(destination.parent)!r}"


def test_push_file(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=0)

    source = tmp_path / "src.txt"
    source.write_text("this is a test")
    destination = pathlib.Path("/tmp/dst.txt")

    instance.push_file(
        source=source,
        destination=destination,
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.name,
            command=["test", "-d", "/tmp"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
        ),
        mock.call.file_push(
            instance_name=instance.name,
            source=source,
            destination=destination,
            project=instance.project,
            remote=instance.remote,
            gid=0,
            uid=0,
        ),
    ]


def test_push_file_no_source(mock_lxc, instance, tmp_path):
    source = tmp_path / "src.txt"
    destination = pathlib.Path("/tmp/dst.txt")

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.push_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == []
    assert str(exc_info.value) == f"File not found: {str(source)!r}"


def test_push_file_no_parent_directory(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=1)

    source = tmp_path / "src.txt"
    source.write_text("this is a test")
    destination = pathlib.Path("/tmp/dst.txt")

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.push_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.name,
            command=["test", "-d", "/tmp"],
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
        ),
    ]
    assert str(exc_info.value) == "Directory not found: '/tmp'"


def test_start(mock_lxc, instance):
    instance.start()

    assert mock_lxc.mock_calls == [
        mock.call.start(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_stop(mock_lxc, instance):
    instance.stop()

    assert mock_lxc.mock_calls == [
        mock.call.stop(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_supports_mount(instance):
    instance.remote = "local"

    assert instance.supports_mount() is True

    instance.remote = "some-remote"

    assert instance.supports_mount() is False


def test_unmount(mock_lxc, instance):
    instance.unmount(target=pathlib.Path("/root/project"))

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_remove(
            instance_name=instance.name,
            device="test_mount",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_unmount_all(mock_lxc, instance):
    instance.unmount_all()

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_remove(
            instance_name=instance.name,
            device="test_mount",
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_remove(
            instance_name=instance.name,
            device="disk-/target",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_unmount_error(mock_lxc, instance):
    mock_lxc.config_device_show.return_value = {
        "disk-/target": {
            "path": "/target",
            "source": "/source",
            "type": "disk",
        },
    }

    with pytest.raises(LXDError) as exc_info:
        instance.unmount(target=pathlib.Path("not-mounted"))

    assert exc_info.value == LXDError(
        brief="Failed to unmount 'not-mounted' in instance 'test-instance' - no such disk.",
        details="* Disk device configuration: {'disk-/target': {'path': '/target', 'source': '/source', 'type': 'disk'}}",
    )
