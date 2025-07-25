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

import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from unittest import mock
from unittest.mock import call

import pytest
from craft_providers import errors
from craft_providers.lxd import LXC, LXDError, LXDInstance
from craft_providers.lxd.lxd_instance_status import (
    LXDInstanceState,
    ProviderInstanceStatus,
)

# These names include invalid characters so a lxd-compatible instance_name
# is generated. This ensures an Instance's `name` and `instance_name` are
# differentiated when testing.
_TEST_INSTANCE = {
    "name": "test-instance-$",
    "instance-name": "test-instance-fa2d407652a1c51f6019",
}

_STOPPED_INSTANCE = {
    "name": "stopped-instance-$",
    "instance-name": "stopped-instance-b4598eebe37eb50c4612",
}

_INVALID_INSTANCE = {
    "name": "invalid-instance-$",
    "instance-name": "invalid-instance-86be3150e96a80a04e31",
}


@pytest.fixture
def project_path(tmp_path):
    project_path = tmp_path / "git" / "project"
    project_path.mkdir(parents=True)
    return project_path


@pytest.fixture(autouse=True)
def mock_lxc(project_path):
    with mock.patch("craft_providers.lxd.lxd_instance.LXC", spec=LXC) as lxc:
        lxc.list.return_value = [
            {
                "name": _TEST_INSTANCE["instance-name"],
                "status": LXDInstanceState.RUNNING.value.title(),
            },
            {
                "name": _STOPPED_INSTANCE["instance-name"],
                "status": LXDInstanceState.STOPPED.value.title(),
            },
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
    return LXDInstance(name=_TEST_INSTANCE["name"], lxc=mock_lxc)


def test_config_get(mock_lxc, instance):
    instance.config_get(key="test-key")

    assert mock_lxc.mock_calls == [
        call.config_get(
            instance_name="test-instance-fa2d407652a1c51f6019",
            key="test-key",
            project="default",
            remote="local",
        )
    ]


def test_config_set(mock_lxc, instance):
    instance.config_set(key="test-key", value="test-value")

    assert mock_lxc.mock_calls == [
        call.config_set(
            instance_name="test-instance-fa2d407652a1c51f6019",
            key="test-key",
            value="test-value",
            project="default",
            remote="local",
        )
    ]


def test_info(mock_lxc, instance):
    instance.info()

    assert mock_lxc.mock_calls == [
        call.info(
            instance_name="test-instance-fa2d407652a1c51f6019",
            project="default",
            remote="local",
        )
    ]


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
        destination=pathlib.PurePosixPath("/etc/test.conf"),
        content=io.BytesIO(b"foo"),
        file_mode="0644",
    )

    assert mock_lxc.mock_calls == [
        mock.call.file_push(
            instance_name=instance.instance_name,
            source=pathlib.Path("test-tmp-file"),
            destination=pathlib.PurePosixPath("/etc/test.conf"),
            mode="0644",
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.exec(
            instance_name=instance.instance_name,
            command=[
                "chown",
                "root:root",
                "/etc/test.conf",
            ],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            capture_output=True,
            check=True,
            timeout=60,
        ),
    ]

    assert mock_named_temporary_file.mock_calls == [
        mock.call.__enter__(),
        mock.call.__enter__().flush(),
        mock.call.__exit__(None, None, None),
    ]
    assert mock_shutil_copyfileobj.mock_calls == [
        mock.call(mock.ANY, mock_named_temporary_file.__enter__.return_value)
    ]


def test_push_file_io_error(mock_lxc, instance):
    error = subprocess.CalledProcessError(
        -1, ["chown", "root:root", "/etc/test.conf"], "test stdout", "test stderr"
    )

    mock_lxc.exec.side_effect = error

    with pytest.raises(LXDError) as exc_info:
        instance.push_file_io(
            destination=pathlib.PurePosixPath("/etc/test.conf"),
            content=io.BytesIO(b"foo"),
            file_mode="0644",
        )

    assert exc_info.value == LXDError(
        brief=(
            "Failed to create file '/etc/test.conf' "
            f"in instance '{_TEST_INSTANCE['instance-name']}'."
        ),
        details=errors.details_from_called_process_error(error),
    )


def test_delete(mock_lxc, instance):
    instance.delete()

    assert mock_lxc.mock_calls == [
        mock.call.delete(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
            force=True,
        )
    ]


def test_execute_popen(mock_lxc, instance):
    instance.execute_popen(command=["test-command", "flags"], input="foo")

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.Popen,
            input="foo",
            timeout=None,
        )
    ]


def test_execute_popen_with_cwd(mock_lxc, instance):
    instance.execute_popen(
        command=["test-command", "flags"],
        cwd=pathlib.PurePosixPath("/tmp"),
        input="foo",
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test-command", "flags"],
            cwd="/tmp",
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.Popen,
            input="foo",
            timeout=None,
        )
    ]


def test_execute_popen_with_env(mock_lxc, instance):
    instance.execute_popen(command=["test-command", "flags"], env={"foo": "bar"})

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["env", "foo=bar", "test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.Popen,
            timeout=None,
        )
    ]


def test_execute_run(mock_lxc, instance):
    instance.execute_run(command=["test-command", "flags"], input="foo")

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            input="foo",
            timeout=None,
            check=False,
        )
    ]


def test_execute_run_with_cwd(mock_lxc, instance):
    instance.execute_run(
        command=["test-command", "flags"],
        cwd=pathlib.PurePosixPath("/tmp"),
        input="foo",
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test-command", "flags"],
            cwd="/tmp",
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            input="foo",
            timeout=None,
            check=False,
        )
    ]


@pytest.mark.parametrize("check", [True, False])
def test_execute_run_with_check(check, mock_lxc, instance):
    instance.execute_run(command=["test-command", "flags"], input="foo", check=check)

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            input="foo",
            timeout=None,
            check=check,
        )
    ]


def test_execute_run_with_default_command_env(mock_lxc):
    instance = LXDInstance(
        name=_TEST_INSTANCE["name"],
        default_command_environment={"env_key": "some-value"},
        lxc=mock_lxc,
    )

    instance.execute_run(command=["test-command", "flags"], env={"foo": "bar"})

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["env", "env_key=some-value", "foo=bar", "test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            timeout=None,
            check=False,
        )
    ]


def test_execute_run_with_default_command_env_unset(mock_lxc):
    instance = LXDInstance(
        name=_TEST_INSTANCE["name"],
        default_command_environment={"env_key": "some-value"},
        lxc=mock_lxc,
    )

    instance.execute_run(
        command=["test-command", "flags"], env={"foo": "bar", "env_key": None}
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["env", "-u", "env_key", "foo=bar", "test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            timeout=None,
            check=False,
        )
    ]


def test_execute_run_with_env(mock_lxc, instance):
    instance.execute_run(command=["test-command", "flags"], env={"foo": "bar"})

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["env", "foo=bar", "test-command", "flags"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            timeout=None,
            check=False,
        )
    ]


def test_execute_run_with_env_unset(mock_lxc, instance):
    instance.execute_run(
        command=["test-command", "flags"], env={"foo": "bar", "TERM": None}
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=[
                "env",
                "foo=bar",
                "-u",
                "TERM",
                "test-command",
                "flags",
            ],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            timeout=None,
            check=False,
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
        instance._get_disk_devices()

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc device 'mount_missing_path'.",
        details=(
            "* Device configuration:"
            " {'mount_missing_path': {'source': '/foo', 'type': 'disk'}}"
        ),
    )


def test_get_disk_devices_source_parse_error(mock_lxc, instance):
    mock_lxc.config_device_show.return_value = {
        "mount_missing_source": {
            "path": "/foo",
            "type": "disk",
        },
    }

    with pytest.raises(LXDError) as exc_info:
        instance._get_disk_devices()

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc device 'mount_missing_source'.",
        details=(
            "* Device configuration:"
            " {'mount_missing_source': {'path': '/foo', 'type': 'disk'}}"
        ),
    )


def test_is_mounted_false(mock_lxc, instance):
    project_path = pathlib.Path.home() / "not-mounted"

    assert (
        instance.is_mounted(
            host_source=pathlib.Path(project_path),
            target=pathlib.PurePosixPath("/root/project"),
        )
        is False
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_is_mounted_true(mock_lxc, instance, project_path):
    assert (
        instance.is_mounted(
            host_source=project_path,
            target=pathlib.PurePosixPath("/root/project"),
        )
        is True
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_is_running_false(mock_lxc):
    instance = LXDInstance(name=_STOPPED_INSTANCE["name"], lxc=mock_lxc)

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
    instance = LXDInstance(name=_INVALID_INSTANCE["name"], lxc=mock_lxc)

    with pytest.raises(LXDError) as exc_info:
        instance.is_running()

    assert exc_info.value == LXDError(
        brief=f"Instance '{_INVALID_INSTANCE['instance-name']}' does not exist.",
    )


def test_launch(mock_lxc, instance):
    instance.launch(
        image="22.04",
        image_remote="ubuntu",
    )

    assert mock_lxc.mock_calls == [
        mock.call.info(project=instance.project, remote=instance.remote),
        mock.call.launch(
            config_keys={},
            ephemeral=False,
            instance_name=instance.instance_name,
            image="22.04",
            image_remote="ubuntu",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on windows")
def test_launch_all_opts(mock_lxc, instance):
    instance.launch(
        image="22.04",
        image_remote="ubuntu",
        ephemeral=True,
        map_user_uid=True,
    )

    uid = str(os.getuid())
    gid = str(os.getgid())
    assert mock_lxc.mock_calls == [
        mock.call.info(project=instance.project, remote=instance.remote),
        mock.call.launch(
            config_keys={"raw.idmap": f"uid {uid} 0\ngid {gid} 0"},
            ephemeral=True,
            instance_name=instance.instance_name,
            image="22.04",
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
        image="22.04",
        image_remote="ubuntu",
    )

    assert mock_lxc.mock_calls == [
        mock.call.info(project=instance.project, remote=instance.remote),
        mock.call.launch(
            config_keys={
                "security.syscalls.intercept.mknod": "true",
            },
            ephemeral=False,
            instance_name=instance.instance_name,
            image="22.04",
            image_remote="ubuntu",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_mount(mock_lxc, tmp_path, instance):
    """Verify calls to mount a directory."""
    instance.mount(host_source=tmp_path, target=pathlib.PurePosixPath("/mnt/foo"))

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_add_disk(
            instance_name=instance.instance_name,
            source=tmp_path,
            path=pathlib.PurePosixPath("/mnt/foo"),
            device="disk-/mnt/foo",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_mount_already_mounted(mock_lxc, instance, project_path):
    """Do not mount if directory is already mounted."""
    instance.mount(
        host_source=project_path, target=pathlib.PurePosixPath("/root/project")
    )

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


def test_pull_file(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=0)

    source = pathlib.PurePosixPath("/tmp/src.txt")
    destination = tmp_path / "dst.txt"

    instance.pull_file(
        source=source,
        destination=destination,
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test", "-f", "/tmp/src.txt"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
            timeout=60,
        ),
        mock.call.file_pull(
            instance_name=instance.instance_name,
            source=source,
            destination=destination,
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_pull_file_no_source(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=1)

    source = pathlib.PurePosixPath("/tmp/src.txt")
    destination = tmp_path / "dst.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.pull_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test", "-f", "/tmp/src.txt"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
            timeout=60,
        ),
    ]
    assert str(exc_info.value) == "File not found: '/tmp/src.txt'"


def test_pull_file_no_parent_directory(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=0)

    source = pathlib.PurePosixPath("/tmp/src.txt")
    destination = tmp_path / "not-created" / "dst.txt"

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.pull_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test", "-f", "/tmp/src.txt"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
            timeout=60,
        ),
    ]
    assert str(exc_info.value) == f"Directory not found: {str(destination.parent)!r}"


def test_push_file(mock_lxc, instance, tmp_path):
    mock_lxc.exec.return_value = mock.Mock(returncode=0)

    source = tmp_path / "src.txt"
    source.write_text("this is a test")
    destination = pathlib.PurePosixPath("/tmp/dst.txt")

    instance.push_file(
        source=source,
        destination=destination,
    )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test", "-d", "/tmp"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
            timeout=60,
        ),
        mock.call.file_push(
            instance_name=instance.instance_name,
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
    destination = pathlib.PurePosixPath("/tmp/dst.txt")

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
    destination = pathlib.PurePosixPath("/tmp/dst.txt")

    with pytest.raises(FileNotFoundError) as exc_info:
        instance.push_file(
            source=source,
            destination=destination,
        )

    assert mock_lxc.mock_calls == [
        mock.call.exec(
            instance_name=instance.instance_name,
            command=["test", "-d", "/tmp"],
            cwd=None,
            project=instance.project,
            remote=instance.remote,
            runner=subprocess.run,
            check=False,
            timeout=60,
        ),
    ]
    assert str(exc_info.value) == "Directory not found: '/tmp'"


def test_start_from_stopped(mock_lxc, instance):
    instance.start()

    assert mock_lxc.mock_calls == [
        mock.call.info(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.start(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.list(
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_set(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
            key="user.craft_providers.status",
            value="IN_USE",
        ),
    ]


def test_start_from_running(mock_lxc, instance):
    mock_lxc.info.return_value = {"Status": LXDInstanceState.RUNNING.value}
    mock_lxc.config_get.return_value = ProviderInstanceStatus.FINISHED.value

    instance.start()

    assert mock_lxc.mock_calls == [
        mock.call.info(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_get(
            instance_name=instance.instance_name,
            key="user.craft_providers.status",
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_set(
            instance_name=instance.instance_name,
            key="user.craft_providers.status",
            value="IN_USE",
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.exec(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
            command=["shutdown", "-c"],
            timeout=None,
            cwd=None,
            check=False,
            runner=mock.ANY,
        ),
    ]


@pytest.mark.usefixtures("instant_sleep")
@pytest.mark.parametrize("wait_count", list(range(6)))
def test_start_with_retries(wait_count, mocker, mock_lxc, instance):
    """Retry while waiting for an instance to start."""
    mock_is_running = mocker.patch.object(
        instance,
        "_get_state",
        side_effect=[LXDInstanceState.STARTING] * wait_count
        + [LXDInstanceState.RUNNING],
    )

    instance.start()

    mock_lxc.start.assert_called_once_with(
        instance_name=instance.instance_name,
        project=instance.project,
        remote=instance.remote,
    )
    mock_is_running.assert_has_calls([mock.call()] * (wait_count + 1))


@pytest.mark.usefixtures("instant_sleep")
def test_start_timeout(mocker, mock_lxc, instance):
    """Timeout if the instance doesn't start."""
    mocker.patch("craft_providers.lxd.lxd_instance.TIMEOUT_SIMPLE", 0.01)
    mocker.patch.object(instance, "_get_state", side_effect=LXDInstanceState.STARTING)

    with pytest.raises(LXDError, match="Instance failed to start."):
        instance.start()


def test_restart(mock_lxc, instance):
    """Restart an instance."""
    instance.restart()

    assert mock_lxc.mock_calls == [
        call.restart(
            instance_name="test-instance-fa2d407652a1c51f6019",
            project="default",
            remote="local",
        ),
        mock.call.list(
            project=instance.project,
            remote=instance.remote,
        ),
    ]


@pytest.mark.usefixtures("instant_sleep")
@pytest.mark.parametrize("wait_count", list(range(6)))
def test_restart_with_retries(wait_count, mocker, mock_lxc, instance):
    """Retry while waiting for an instance to restart."""
    mock_is_running = mocker.patch.object(
        instance,
        "_get_state",
        side_effect=[LXDInstanceState.STARTING] * wait_count
        + [LXDInstanceState.RUNNING],
    )

    instance.restart()

    mock_lxc.restart.assert_called_once_with(
        instance_name=instance.instance_name,
        project=instance.project,
        remote=instance.remote,
    )
    mock_is_running.assert_has_calls([mock.call()] * (wait_count + 1))


@pytest.mark.usefixtures("instant_sleep")
def test_restart_timeout(mocker, mock_lxc, instance):
    """Timeout if the instance doesn't restart."""
    mocker.patch("craft_providers.lxd.lxd_instance.TIMEOUT_SIMPLE", 0.01)
    mocker.patch.object(instance, "_get_state", side_effect=LXDInstanceState.STARTING)

    with pytest.raises(LXDError, match="Instance failed to restart."):
        instance.restart()


def test_stop_immediately(mock_lxc, mocker):
    """Stop an instance."""
    instance = LXDInstance(name=_STOPPED_INSTANCE["name"], lxc=mock_lxc)
    mocker.patch.object(instance, "exists", return_value=True)

    instance.stop()

    assert mock_lxc.mock_calls == [
        mock.call.stop(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.list(
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_set(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
            key="user.craft_providers.status",
            value=ProviderInstanceStatus.FINISHED.value,
        ),
    ]


def test_stop_delay(mock_lxc, mocker):
    """Stop an instance."""
    instance = LXDInstance(name=_STOPPED_INSTANCE["name"], lxc=mock_lxc)
    mocker.patch.object(instance, "exists", return_value=True)

    instance.stop(delay_mins=1)

    assert mock_lxc.mock_calls == [
        mock.call.config_set(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
            key="user.craft_providers.status",
            value=ProviderInstanceStatus.FINISHED.value,
        ),
        mock.call.exec(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
            command=["shutdown", "+1", "Shutdown triggered by craft-providers."],
            runner=mock.ANY,
            timeout=None,
            cwd=None,
            check=True,
            capture_output=True,
        ),
    ]


def test_stop_ephemeral(mock_lxc, instance, mocker):
    """Stop an ephemeral instance."""
    # ephemeral instances don't exist after stopping
    mocker.patch.object(instance, "exists", return_value=False)

    instance.stop()

    assert mock_lxc.mock_calls == [
        mock.call.stop(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        )
    ]


@pytest.mark.usefixtures("instant_sleep")
@pytest.mark.parametrize("wait_count", list(range(6)))
def test_stop_with_retries(wait_count, mocker, mock_lxc, instance):
    """Retry while waiting for an instance to stop."""
    mocker.patch.object(instance, "exists", return_value=True)
    mock_is_running = mocker.patch.object(
        instance,
        "_get_state",
        side_effect=[[LXDInstanceState.STOPPING]] * wait_count
        + [LXDInstanceState.STOPPED],
    )

    instance.stop()

    mock_lxc.stop.assert_called_once_with(
        instance_name=instance.instance_name,
        project=instance.project,
        remote=instance.remote,
    )
    mock_is_running.assert_has_calls([mock.call()] * (wait_count + 1))


@pytest.mark.usefixtures("instant_sleep")
def test_stop_timeout(mocker, mock_lxc, instance):
    """Timeout if the instance doesn't stop."""
    mocker.patch.object(instance, "exists", return_value=True)
    mocker.patch("craft_providers.lxd.lxd_instance.TIMEOUT_SIMPLE", 0.01)
    mocker.patch.object(instance, "_get_state", side_effect=[LXDInstanceState.STOPPING])

    with pytest.raises(LXDError, match="Instance failed to stop."):
        instance.stop()


def test_supports_mount(instance):
    instance.remote = "local"

    assert instance.supports_mount() is True

    instance.remote = "some-remote"

    assert instance.supports_mount() is False


def test_unmount(mock_lxc, instance):
    instance.unmount(target=pathlib.PurePosixPath("/root/project"))

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_remove(
            instance_name=instance.instance_name,
            device="test_mount",
            project=instance.project,
            remote=instance.remote,
        ),
    ]


def test_unmount_all(mock_lxc, instance):
    instance.unmount_all()

    assert mock_lxc.mock_calls == [
        mock.call.config_device_show(
            instance_name=instance.instance_name,
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_remove(
            instance_name=instance.instance_name,
            device="test_mount",
            project=instance.project,
            remote=instance.remote,
        ),
        mock.call.config_device_remove(
            instance_name=instance.instance_name,
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
        instance.unmount(target=pathlib.PurePosixPath("not-mounted"))

    assert exc_info.value == LXDError(
        brief=(
            "Failed to unmount 'not-mounted'"
            f" in instance '{_TEST_INSTANCE['instance-name']}' - no such disk."
        ),
        details=(
            "* Disk device configuration: {'disk-/target':"
            " {'path': '/target', 'source': '/source', 'type': 'disk'}}"
        ),
    )


@pytest.mark.parametrize(
    ("name", "expected_instance_name"),
    [
        ("simple-name", "simple-name"),
        (
            "$$$-this-is-70-characters-with-invalid-characters-$$$xxxxxxxxxxxxxxxxX",
            "this-is-70-characters-with-invalid-chara-bf117c12825011de054e",
        ),
    ],
)
def test_instance_name(logs, mock_lxc, name, expected_instance_name):
    """Verify name is compliant with LXD naming conventions."""
    instance = LXDInstance(name=name, lxc=mock_lxc)

    assert instance.name == name
    assert instance.instance_name == expected_instance_name
    assert len(instance.instance_name) <= 63
    assert (
        re.escape(
            f"Converted name {name!r} to instance name {instance.instance_name!r}"
        )
        in logs.debug
    )


def test_set_instance_name_invalid(mock_lxc):
    """Verify invalid names raise an error."""
    with pytest.raises(LXDError) as error:
        LXDInstance(name="-", lxc=mock_lxc)

    assert error.value == LXDError(
        brief="failed to create an instance with name '-'.",
        details="name must contain at least one alphanumeric character",
    )
