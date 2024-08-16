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
import pathlib
import subprocess
from textwrap import dedent
from unittest.mock import call

import pytest
from craft_providers import errors
from craft_providers.lxd import LXC, LXDError, lxc
from craft_providers.lxd.lxc import StdinType
from freezegun import freeze_time


@pytest.fixture
def mock_getpid(mocker):
    return mocker.patch("os.getpid", return_value=123)


def test_lxc_run_default(mocker, tmp_path):
    """Test _lxc_run with default arguments."""
    mock_run = mocker.patch("subprocess.run")

    LXC()._run_lxc(command=["test-command"])

    mock_run.assert_called_once_with(
        ["lxc", "test-command"],
        check=True,
        stdin=subprocess.DEVNULL,
    )


@pytest.mark.parametrize("check", [True, False])
def test_lxc_run_with_check(check, mocker, tmp_path):
    """Test check parameter."""
    mock_run = mocker.patch("subprocess.run")

    LXC()._run_lxc(command=["test-command"], check=check, project="test-project")

    mock_run.assert_called_once_with(
        ["lxc", "--project", "test-project", "test-command"],
        check=check,
        stdin=subprocess.DEVNULL,
    )


def test_lxc_run_with_project(mocker, tmp_path):
    """Test _lxc_run with project."""
    mock_run = mocker.patch("subprocess.run")

    LXC()._run_lxc(command=["test-command"], project="test-project")

    mock_run.assert_called_once_with(
        ["lxc", "--project", "test-project", "test-command"],
        check=True,
        stdin=subprocess.DEVNULL,
    )


def test_lxc_run_with_stdin(mocker, tmp_path):
    """Test _lxc_run with stdin argument."""
    mock_run = mocker.patch("subprocess.run")

    LXC()._run_lxc(
        command=["test-command"], project="test-project", stdin=lxc.StdinType.NULL
    )

    mock_run.assert_called_once_with(
        ["lxc", "--project", "test-project", "test-command"],
        check=True,
        stdin=None,
    )


def test_lxc_run_with_input(mocker, tmp_path):
    """Test _lxc_run with input argument."""
    mock_run = mocker.patch("subprocess.run")

    LXC()._run_lxc(
        command=["test-command"],
        project="test-project",
        stdin=lxc.StdinType.NULL,
        input="test-input",
    )

    mock_run.assert_called_once_with(
        ["lxc", "--project", "test-project", "test-command"],
        check=True,
        input="test-input",
    )


def test_lxc_run_with_input_and_stdin(mocker, tmp_path):
    """`stdin` argument is ignored when `input` is passed."""
    mock_run = mocker.patch("subprocess.run")

    LXC()._run_lxc(
        command=["test-command"],
        project="test-project",
        stdin=lxc.StdinType.NULL,
        input="test-input",
    )

    mock_run.assert_called_once_with(
        ["lxc", "--project", "test-project", "test-command"],
        check=True,
        input="test-input",
    )


def test_config_device_add_disk(fake_process, tmp_path):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "device",
            "add",
            "test-remote:test-instance",
            "disk_foo",
            "disk",
            f"source={tmp_path.as_posix()}",
            "path=/mnt",
        ]
    )

    LXC().config_device_add_disk(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        device="disk_foo",
        source=tmp_path,
        path=pathlib.PurePosixPath("/mnt"),
    )

    assert len(fake_process.calls) == 1


def test_config_device_add_disk_error(fake_process, tmp_path):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "device",
            "add",
            "test-remote:test-instance",
            "disk_foo",
            "disk",
            f"source={tmp_path.as_posix()}",
            "path=/mnt",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().config_device_add_disk(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
            device="disk_foo",
            source=tmp_path,
            path=pathlib.PurePosixPath("/mnt"),
        )

    assert exc_info.value == LXDError(
        brief="Failed to add disk to instance 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_config_device_remove(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "device",
            "remove",
            "test-remote:test-instance",
            "device_foo",
        ]
    )

    LXC().config_device_remove(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        device="device_foo",
    )

    assert len(fake_process.calls) == 1


def test_config_device_remove_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "device",
            "remove",
            "test-remote:test-instance",
            "device_foo",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().config_device_remove(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
            device="device_foo",
        )

    assert exc_info.value == LXDError(
        brief="Failed to remove device from instance 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_config_device_show(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "device",
            "show",
            "test-remote:test-instance",
        ],
        stdout="test_mount:\n  path: /tmp\n  source: /tmp\n  type: disk\n",
    )

    devices = LXC().config_device_show(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert devices == {"test_mount": {"path": "/tmp", "source": "/tmp", "type": "disk"}}


def test_config_device_show_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "device",
            "show",
            "test-remote:test-instance",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().config_device_show(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to show devices for instance 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_config_get(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "test-key",
        ],
    )

    LXC().config_get(
        instance_name="test-instance",
        key="test-key",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_config_get_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "test-key",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().config_get(
            instance_name="test-instance",
            key="test-key",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief=(
            "Failed to get value for config key 'test-key' "
            "for instance 'test-instance'."
        ),
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_config_set(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "set",
            "test-remote:test-instance",
            "test-key",
            "test-value",
        ],
    )

    LXC().config_set(
        instance_name="test-instance",
        key="test-key",
        value="test-value",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_config_set_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "set",
            "test-remote:test-instance",
            "test-key",
            "test-value",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().config_set(
            instance_name="test-instance",
            key="test-key",
            value="test-value",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief=(
            "Failed to set config key 'test-key' to 'test-value'"
            " for instance 'test-instance'."
        ),
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_copy(fake_process):
    """Test `copy()` with default arguments."""
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "default",
            "copy",
            "local:test-source-instance-name",
            "local:test-destination-instance-name",
        ],
    )

    LXC().copy(
        source_instance_name="test-source-instance-name",
        destination_instance_name="test-destination-instance-name",
    )

    assert len(fake_process.calls) == 1


def test_copy_all_opts(fake_process):
    """Test `copy() with all arguments defined`."""
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "copy",
            "test-source-remote:test-source-instance-name",
            "test-destination-remote:test-destination-instance-name",
        ],
    )

    LXC().copy(
        source_remote="test-source-remote",
        source_instance_name="test-source-instance-name",
        destination_remote="test-destination-remote",
        destination_instance_name="test-destination-instance-name",
        project="test-project",
    )

    assert len(fake_process.calls) == 1


def test_copy_error(fake_process):
    """A LXDError should be raised when the copy command fails."""
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "copy",
            "test-source-remote:test-source-instance-name",
            "test-destination-remote:test-destination-instance-name",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().copy(
            source_remote="test-source-remote",
            source_instance_name="test-source-instance-name",
            destination_remote="test-destination-remote",
            destination_instance_name="test-destination-instance-name",
            project="test-project",
        )

    assert exc_info.value == LXDError(
        brief=(
            "Failed to copy instance 'test-source-remote:test-source-instance-name' "
            "to 'test-destination-remote:test-destination-instance-name'."
        ),
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_delete(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "delete",
            "test-remote:test-instance",
        ],
    )

    LXC().delete(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_delete_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "delete",
            "test-remote:test-instance",
            "--force",
        ],
    )

    LXC().delete(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        force=True,
    )

    assert len(fake_process.calls) == 1


def test_delete_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "delete",
            "test-remote:test-instance",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().delete(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to delete instance 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_exec(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "exec",
            "test-remote:test-instance",
            "--",
            "echo",
            "hi",
        ],
    )

    LXC().exec(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        command=["echo", "hi"],
    )

    assert len(fake_process.calls) == 1


def test_exec_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "exec",
            "test-remote:test-instance",
            "--cwd",
            "/tmp",
            "--mode",
            "interactive",
            "--",
            "echo",
            "hi",
        ],
    )

    LXC().exec(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        command=["echo", "hi"],
        cwd="/tmp",
        mode="interactive",
        runner=subprocess.Popen,
    )

    assert len(fake_process.calls) == 1


def test_exec_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "exec",
            "test-remote:test-instance",
            "--",
            "/bin/false",
        ],
        returncode=1,
    )

    with pytest.raises(subprocess.CalledProcessError):
        LXC().exec(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
            command=["/bin/false"],
            check=True,
        )


def test_file_pull(fake_process, tmp_path):
    source = pathlib.PurePosixPath("/root/foo")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "file",
            "pull",
            "test-remote:test-instance/root/foo",
            tmp_path.as_posix(),
        ],
    )

    LXC().file_pull(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        source=source,
        destination=tmp_path,
    )

    assert len(fake_process.calls) == 1


def test_file_pull_all_opts(fake_process, tmp_path):
    source = pathlib.PurePosixPath("/root/foo")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "file",
            "pull",
            "test-remote:test-instance/root/foo",
            tmp_path.as_posix(),
            "--create-dirs",
            "--recursive",
        ],
    )

    LXC().file_pull(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        source=source,
        destination=tmp_path,
        create_dirs=True,
        recursive=True,
    )

    assert len(fake_process.calls) == 1


def test_file_pull_error(fake_process, tmp_path):
    source = pathlib.PurePosixPath("/root/foo")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "file",
            "pull",
            "test-remote:test-instance/root/foo",
            tmp_path.as_posix(),
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().file_pull(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
            source=source,
            destination=tmp_path,
        )

    assert exc_info.value == LXDError(
        brief="Failed to pull file '/root/foo' from instance 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_file_push(fake_process, tmp_path):
    destination = pathlib.PurePosixPath("/root/foo")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "file",
            "push",
            tmp_path.as_posix(),
            "test-remote:test-instance/root/foo",
        ],
    )

    LXC().file_push(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        source=tmp_path,
        destination=destination,
    )

    assert len(fake_process.calls) == 1


def test_file_push_all_opts(fake_process, tmp_path):
    destination = pathlib.PurePosixPath("/root/foo")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "file",
            "push",
            tmp_path.as_posix(),
            "test-remote:test-instance/root/foo",
            "--create-dirs",
            "--recursive",
            "--mode=0644",
            "--gid=1",
            "--uid=2",
        ],
    )

    LXC().file_push(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        source=tmp_path,
        destination=destination,
        create_dirs=True,
        recursive=True,
        gid=1,
        uid=2,
        mode="0644",
    )

    assert len(fake_process.calls) == 1


def test_file_push_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "file",
            "push",
            "/somefile",
            "test-remote:test-instance/root/foo",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().file_push(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
            source=pathlib.Path("/somefile"),
            destination=pathlib.PurePosixPath("/root/foo"),
        )

    assert exc_info.value == LXDError(
        brief="Failed to push file '/somefile' to instance 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_info(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:",
        ],
        stdout="config: {}\napi_extensions:\n - foo\n",
    )

    info = LXC().info(
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert info == {"config": {}, "api_extensions": ["foo"]}


def test_info_with_instance(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:test-instance",
        ],
        stdout="Name: test-instance\nLocation: none\n",
    )

    info = LXC().info(
        project="test-project",
        remote="test-remote",
        instance_name="test-instance",
    )

    assert len(fake_process.calls) == 1
    assert info == {"Name": "test-instance", "Location": "none"}


def test_info_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().info(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to get info for remote 'test-remote'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_info_parse_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:",
        ],
        stdout="fail:\nthis\n",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().info(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc info.",
        details=(
            "* Command that failed: 'lxc --project test-project info test-remote:'\n"
            "* Command output: b'fail:\\nthis\\n'"
        ),
    )


@pytest.mark.usefixtures("mock_getpid")
def test_launch(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "launch",
            "test-image-remote:test-image",
            "test-remote:test-instance",
            "--config",
            "user.craft_providers.status=STARTING",
            "--config",
            "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
            "--config",
            "user.craft_providers.pid=123",
        ]
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "set",
            "test-remote:test-instance",
            "user.craft_providers.status",
            "PREPARING",
        ]
    )

    with freeze_time("2023-01-01"):
        LXC().launch(
            instance_name="test-instance",
            image="test-image",
            image_remote="test-image-remote",
            project="test-project",
            remote="test-remote",
        )

    assert len(fake_process.calls) == 1


@pytest.mark.usefixtures("mock_getpid")
def test_launch_failed_retry_check(fake_process, mocker):
    """Test that we use check_instance_status if launch fails."""
    mock_launch = mocker.patch("craft_providers.lxd.lxc.LXC._run_lxc")
    mock_launch.side_effect = [
        subprocess.CalledProcessError(1, ["lxc", "fail", " test"]),
    ]
    mock_check = mocker.patch("craft_providers.lxd.lxc.LXC.check_instance_status")
    mocker.patch("time.sleep")

    with freeze_time("2023-01-01"):
        LXC().launch(
            instance_name="test-instance",
            image="test-image",
            image_remote="test-image-remote",
            project="test-project",
            remote="test-remote",
        )

    assert mock_launch.mock_calls == [
        call(
            [
                "launch",
                "test-image-remote:test-image",
                "test-remote:test-instance",
                "--config",
                "user.craft_providers.status=STARTING",
                "--config",
                "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
                "--config",
                "user.craft_providers.pid=123",
            ],
            capture_output=True,
            stdin=StdinType.INTERACTIVE,
            project="test-project",
        ),
    ]

    assert mock_check.mock_calls == [
        call(
            instance_name="test-instance", project="test-project", remote="test-remote"
        )
    ]


@pytest.mark.usefixtures("mock_getpid")
def test_launch_failed_retry_failed(fake_process, mocker):
    """Test that we retry launching an instance if it fails, but failed more than 3 times."""
    mock_launch = mocker.patch("craft_providers.lxd.lxc.LXC._run_lxc")
    mock_launch.side_effect = subprocess.CalledProcessError(1, ["lxc", "fail", " test"])
    mock_check = mocker.patch("craft_providers.lxd.lxc.LXC.check_instance_status")
    mock_check.side_effect = LXDError("test")
    mocker.patch("time.sleep")

    with pytest.raises(LXDError):
        with freeze_time("2023-01-01"):
            LXC().launch(
                instance_name="test-instance",
                image="test-image",
                image_remote="test-image-remote",
                project="test-project",
                remote="test-remote",
            )

    assert mock_launch.mock_calls == [
        call(
            [
                "launch",
                "test-image-remote:test-image",
                "test-remote:test-instance",
                "--config",
                "user.craft_providers.status=STARTING",
                "--config",
                "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
                "--config",
                "user.craft_providers.pid=123",
            ],
            capture_output=True,
            stdin=StdinType.INTERACTIVE,
            project="test-project",
        ),
        call(
            ["delete", "test-remote:test-instance", "--force"],
            capture_output=True,
            project="test-project",
        ),
        call(
            [
                "launch",
                "test-image-remote:test-image",
                "test-remote:test-instance",
                "--config",
                "user.craft_providers.status=STARTING",
                "--config",
                "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
                "--config",
                "user.craft_providers.pid=123",
            ],
            capture_output=True,
            stdin=StdinType.INTERACTIVE,
            project="test-project",
        ),
        call(
            ["delete", "test-remote:test-instance", "--force"],
            capture_output=True,
            project="test-project",
        ),
        call(
            [
                "launch",
                "test-image-remote:test-image",
                "test-remote:test-instance",
                "--config",
                "user.craft_providers.status=STARTING",
                "--config",
                "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
                "--config",
                "user.craft_providers.pid=123",
            ],
            capture_output=True,
            stdin=StdinType.INTERACTIVE,
            project="test-project",
        ),
    ]


@pytest.mark.usefixtures("mock_getpid")
def test_launch_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "launch",
            "test-image-remote:test-image",
            "test-remote:test-instance",
            "--ephemeral",
            "--config",
            "test-key=test-value",
            "--config",
            "test-key2=test-value2",
            "--config",
            "user.craft_providers.status=STARTING",
            "--config",
            "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
            "--config",
            "user.craft_providers.pid=123",
        ]
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "set",
            "test-remote:test-instance",
            "user.craft_providers.status",
            "PREPARING",
        ]
    )

    with freeze_time("2023-01-01"):
        LXC().launch(
            instance_name="test-instance",
            image="test-image",
            image_remote="test-image-remote",
            project="test-project",
            remote="test-remote",
            config_keys={"test-key": "test-value", "test-key2": "test-value2"},
            ephemeral=True,
        )

    assert len(fake_process.calls) == 1


@pytest.mark.usefixtures("mock_getpid")
def test_launch_error(fake_process, mocker):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "launch",
            "test-image-remote:test-image",
            "test-remote:test-instance",
            "--config",
            "user.craft_providers.status=STARTING",
            "--config",
            "user.craft_providers.timer=2023-01-01T00:00:00+00:00",
            "--config",
            "user.craft_providers.pid=123",
        ],
        returncode=1,
        occurrences=4,
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "delete",
            "test-remote:test-instance",
            "--force",
        ],
        returncode=0,
        occurrences=4,
    )

    mocker.patch("craft_providers.lxd.lxc.LXC.check_instance_status").side_effect = (
        LXDError("Failed to get instance status.")
    )

    mocker.patch("time.sleep")

    with pytest.raises(LXDError) as exc_info:
        with freeze_time("2023-01-01"):
            LXC().launch(
                instance_name="test-instance",
                image="test-image",
                image_remote="test-image-remote",
                project="test-project",
                remote="test-remote",
            )

    assert exc_info.value == LXDError(
        brief="Failed to launch instance 'test-instance'.",
        details="* Command that failed: 'lxc --project test-project launch test-image-remote:test-image test-remote:test-instance --config user.craft_providers.status=STARTING --config user.craft_providers.timer=2023-01-01T00:00:00+00:00 --config user.craft_providers.pid=123'\n* Command exit code: 1",
        resolution=None,
    )


def test_check_instance_status(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:test-instance",
        ],
        returncode=0,
        stdout=dedent(
            """\
            Name: test-instance
            Status: STOPPED
            Type: container
            Architecture: x86_64
            Created: 2023/08/02 14:04 EDT
            Last Used: 2023/08/08 09:44 EDT
            """
        ),
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "user.craft_providers.status",
        ],
        returncode=0,
        stdout="FINISHED",
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "user.craft_providers.timer",
        ],
        returncode=0,
        stdout="2023-01-01T00:00:00+00:00",
    )

    LXC().check_instance_status(
        instance_name="test-instance", project="test-project", remote="test-remote"
    )


def test_check_instance_status_retry(fake_process, mocker):
    time_time = mocker.patch("time.time")
    time_time.side_effect = [0, 10]
    mocker.patch("time.sleep")
    mock_instance = mocker.patch("craft_providers.lxd.lxc.LXC.info")
    mock_instance.side_effect = [
        {"Status": "STOPPED"},
        {"Status": "STOPPED"},
    ]
    mock_instance_config = mocker.patch("craft_providers.lxd.lxc.LXC.config_get")
    mock_instance_config.side_effect = [
        "STARTING",
        "10",
        "FINISHED",
        "20",
    ]

    LXC().check_instance_status(
        instance_name="test-instance", project="test-project", remote="test-remote"
    )


def test_check_instance_status_boot_failed(fake_process, mocker):
    time_time = mocker.patch("time.time")
    time_time.return_value = 0
    mocker.patch("time.sleep")
    mock_instance = mocker.patch("craft_providers.lxd.lxc.LXC.info")
    mock_instance.return_value = {"Status": "STOPPED"}
    mock_instance_config = mocker.patch("craft_providers.lxd.lxc.LXC.config_get")
    mock_instance_config.side_effect = [
        "STARTING",
        "2023-01-01T00:00:00+00:00",
    ] * 20

    with pytest.raises(LXDError):
        LXC().check_instance_status(
            instance_name="test-instance", project="test-project", remote="test-remote"
        )


def test_check_instance_status_wait(fake_process, mocker):
    time_time = mocker.patch("time.time")
    time_time.return_value = 0
    mocker.patch("time.sleep")
    mock_instance = mocker.patch("craft_providers.lxd.lxc.LXC.info")
    mock_instance.side_effect = [
        {"Status": "STOPPED"},  # STARTING
        {"Status": "RUNNING"},  # STARTING
        {"Status": "RUNNING"},  # PREPARING
        {"Status": "RUNNING"},  # PREPARING
        {"Status": "RUNNING"},  # FINISHED
        {"Status": "STOPPED"},  # FINISHED
    ]
    mock_instance_config = mocker.patch("craft_providers.lxd.lxc.LXC.config_get")
    mock_instance_config.side_effect = [
        "STARTING",
        "2023-01-01T00:00:00+00:00",
        "STARTING",
        "2023-01-01T00:00:05+00:00",
        "PREPARING",
        "2023-01-01T00:00:10+00:00",
        "PREPARING",
        "2023-01-01T00:00:15+00:00",
        "FINISHED",
        "2023-01-01T00:00:20+00:00",
        "FINISHED",
        "2023-01-01T00:00:30+00:00",
    ]

    LXC().check_instance_status(
        instance_name="test-instance", project="test-project", remote="test-remote"
    )
    assert mock_instance.call_count == 6
    assert mock_instance_config.call_count == 12


def test_check_instance_status_lxd_error(fake_process, mocker):
    time_time = mocker.patch("time.time")
    time_time.side_effect = [0, 1000, 2000]
    mocker.patch("time.sleep")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:test-instance",
        ],
        returncode=0,
        stdout=dedent(
            """\
            Name: test-instance
            Status: STOPPED
            Type: container
            Architecture: x86_64
            Created: 2023/08/02 14:04 EDT
            Last Used: 2023/08/08 09:44 EDT
            """
        ),
        occurrences=1000,
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "user.craft_providers.status",
        ],
        returncode=1,
        stdout="",
        occurrences=1000,
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "user.craft_providers.timer",
        ],
        returncode=1,
        stdout="",
        occurrences=1000,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().check_instance_status(
            instance_name="test-instance", project="test-project", remote="test-remote"
        )

    assert exc_info.value == LXDError(
        brief="Failed to get value for config key 'user.craft_providers.status' for instance 'test-instance'.",
        details="* Command that failed: 'lxc --project test-project config get test-remote:test-instance user.craft_providers.status'\n* Command exit code: 1",
        resolution=None,
    )


def test_check_instance_status_lxd_error_retry(fake_process, mocker):
    time_time = mocker.patch("time.time")
    time_time.side_effect = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900]
    mocker.patch("time.sleep")
    mock_instance = mocker.patch("craft_providers.lxd.lxc.LXC.info")
    mock_instance.side_effect = [
        LXDError(
            brief="Failed to get instance info.",
            details="* Command that failed: 'lxc --project test-project info test-remote:test-instance'\n* Command exit code: 1",
            resolution=None,
        ),
        {"Status": "STOPPED"},
        {"Status": "RUNNING"},
        {"Status": "RUNNING"},
        LXDError(
            brief="Failed to get instance info.",
            details="* Command that failed: 'lxc --project test-project info test-remote:test-instance'\n* Command exit code: 1",
            resolution=None,
        ),
        {"Status": "RUNNING"},
        {"Status": "RUNNING"},
        {"Status": "RUNNING"},
        {"Status": "STOPPED"},
    ]
    mock_instance_config = mocker.patch("craft_providers.lxd.lxc.LXC.config_get")
    mock_instance_config.side_effect = [
        LXDError(
            brief="Failed to get instance info.",
            details="* Command that failed: 'lxc --project test-project info test-remote:test-instance'\n* Command exit code: 1",
            resolution=None,
        ),
        LXDError(
            brief="Failed to get instance info.",
            details="* Command that failed: 'lxc --project test-project info test-remote:test-instance'\n* Command exit code: 1",
            resolution=None,
        ),
        "STARTING",
        "2023-01-01T00:00:00+00:00",
        "STARTING",
        "2023-01-01T00:00:10+00:00",
        "PREPARING",
        "2023-01-01T00:00:20+00:00",
        LXDError(
            brief="Failed to get instance info.",
            details="* Command that failed: 'lxc --project test-project info test-remote:test-instance'\n* Command exit code: 1",
            resolution=None,
        ),
        "FINISHED",
        "2023-01-01T00:00:40+00:00",
        "FINISHED",
        "2023-01-01T00:00:50+00:00",
    ]

    LXC().check_instance_status(
        instance_name="test-instance", project="test-project", remote="test-remote"
    )


def test_check_instance_status_error_timeout(fake_process, mocker):
    time_time = mocker.patch("time.time")
    time_time.side_effect = [0, 1000, 2000]
    mocker.patch("time.sleep")

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "info",
            "test-remote:test-instance",
        ],
        returncode=0,
        stdout=dedent(
            """\
            Name: test-instance
            Status: STOPPED
            Type: container
            Architecture: x86_64
            Created: 2023/08/02 14:04 EDT
            Last Used: 2023/08/08 09:44 EDT
            """
        ),
        occurrences=1000,
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "user.craft_providers.status",
        ],
        returncode=0,
        stdout="STARTING",
        occurrences=1000,
    )

    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "config",
            "get",
            "test-remote:test-instance",
            "user.craft_providers.timer",
        ],
        returncode=0,
        stdout="2023-01-01T00:00:00+00:00",
        occurrences=1000,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().check_instance_status(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Timed out waiting for instance to be ready."
    )


def test_has_image(fake_process):
    lxc = LXC()
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- aliases:\n  - name: image1\n- aliases:\n  - name: image2\n",
        occurrences=3,
    )
    fake_process.keep_last_process(True)

    assert lxc.has_image("image1", project="test-project", remote="test-remote") is True
    assert lxc.has_image("image2", project="test-project", remote="test-remote") is True
    assert (
        lxc.has_image("image3", project="test-project", remote="test-remote") is False
    )


def test_image_copy(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "copy",
            "test-image-remote:test-image",
            "test-remote:",
        ]
    )

    LXC().image_copy(
        image="test-image",
        image_remote="test-image-remote",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_image_copy_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "copy",
            "test-image-remote:test-image",
            "test-remote:",
            "--alias=test-alias",
        ]
    )

    LXC().image_copy(
        image="test-image",
        image_remote="test-image-remote",
        alias="test-alias",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_image_copy_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "copy",
            "test-image-remote:test-image",
            "test-remote:",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().image_copy(
            image="test-image",
            image_remote="test-image-remote",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to copy image 'test-image'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_image_delete(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "delete",
            "test-remote:test-image",
        ]
    )

    LXC().image_delete(
        image="test-image",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_image_delete_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "delete",
            "test-remote:test-image",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().image_delete(
            image="test-image",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to delete image 'test-image'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_image_list(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- image1: stuff\n- image2: stuff\n",
    )

    images = LXC().image_list(
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert images == [{"image1": "stuff"}, {"image2": "stuff"}]


def test_image_list_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().image_list(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to list images for project 'test-project'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_image_list_parse_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "image",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="fail:\nthis\n",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().image_list(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc image list.",
        details=(
            "* Command that failed:"
            " 'lxc --project test-project image list test-remote: --format=yaml'\n"
            "* Command output: b'fail:\\nthis\\n'"
        ),
    )


def test_list(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- name: test1\n- name: test2\n",
    )

    container_names = LXC().list(
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert container_names == [{"name": "test1"}, {"name": "test2"}]


def test_list_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().list(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to list instances for project 'test-project'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_list_parse_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="fail:\nthis\n",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().list(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc list.",
        details=(
            "* Command that failed:"
            " 'lxc --project test-project list test-remote: --format=yaml'\n"
            "* Command output: b'fail:\\nthis\\n'"
        ),
    )


def test_list_names(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- name: test1\n- name: test2\n",
    )

    container_names = LXC().list_names(
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert container_names == ["test1", "test2"]


def test_list_names_parse_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- foo: bar",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().list_names(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc list.",
        details=("* Data received from lxc list: [{'foo': 'bar'}]"),
    )


def test_profile_edit(fake_process):
    stdin_records = []
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "profile",
            "edit",
            "test-remote:test-profile",
        ],
        stdin_callable=stdin_records.append,
        stdout="- name: test1\n- name: test2\n",
    )

    LXC().profile_edit(
        profile="test-profile",
        config={"test-key": "test-value", "test-key2": "test-value2"},
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert stdin_records == [b"test-key: test-value\ntest-key2: test-value2\n"]


def test_profile_edit_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "profile",
            "edit",
            "test-remote:test-profile",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().profile_edit(
            profile="test-profile",
            config={"test-key": "test-value", "test-key2": "test-value2"},
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to set profile 'test-profile'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_profile_show(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "profile",
            "show",
            "test-remote:test-profile",
        ],
        stdout="config: {}\ndescription: LXD profile\n",
    )

    profile = LXC().profile_show(
        profile="test-profile",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert profile == {"config": {}, "description": "LXD profile"}


def test_profile_show_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "profile",
            "show",
            "test-remote:test-profile",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().profile_show(
            profile="test-profile",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to show profile 'test-profile'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_project_create(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "project",
            "create",
            "test-remote:test-project",
        ],
    )

    LXC().project_create(
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_project_create_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "project",
            "create",
            "test-remote:test-project",
        ],
        returncode=1,
    )
    fake_process.register_subprocess(
        [
            "lxc",
            "project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- config:\n  name: default\n",
        returncode=0,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().project_create(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to create project 'test-project'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_project_create_error_race(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "project",
            "create",
            "test-remote:test-project",
        ],
        returncode=1,
    )
    fake_process.register_subprocess(
        [
            "lxc",
            "project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- config:\n  name: default\n- config:\n  name: test-project\n",
        returncode=0,
    )

    LXC().project_create(
        project="test-project",
        remote="test-remote",
    )
    assert len(fake_process.calls) == 2


def test_project_delete(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "project",
            "delete",
            "test-remote:test-project",
        ],
    )

    LXC().project_delete(
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_project_delete_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "project",
            "delete",
            "test-remote:test-project",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().project_delete(
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to delete project 'test-project'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_project_list(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- name: default\n- name: myproject\n",
    )

    projects = LXC().project_list(
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1
    assert projects == ["default", "myproject"]


def test_project_list_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().project_list(
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to list projects on remote 'test-remote'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_project_list_parse_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="fail:\nthis\n",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().project_list(
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc project list.",
        details=(
            "* Command that failed: 'lxc project list test-remote: --format=yaml'\n"
            "* Command output: b'fail:\\nthis\\n'"
        ),
    )


def test_project_list_parse_error_missing_name(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "project",
            "list",
            "test-remote:",
            "--format=yaml",
        ],
        stdout="- foo: bar",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().project_list(
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc project list.",
        details=(
            "* Command that failed: 'lxc project list test-remote: --format=yaml'\n"
            "* Command output: b'- foo: bar'"
        ),
    )


def test_publish(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "publish",
            "test-remote:test-instance",
            "test-image-remote:",
        ],
    )

    LXC().publish(
        image_remote="test-image-remote",
        instance_name="test-instance",
        remote="test-remote",
        project="test-project",
    )

    assert len(fake_process.calls) == 1


def test_publish_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "publish",
            "test-remote:test-instance",
            "test-image-remote:",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().publish(
            instance_name="test-instance",
            remote="test-remote",
            image_remote="test-image-remote",
            project="test-project",
        )

    assert exc_info.value == LXDError(
        brief="Failed to publish image from 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_publish_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "publish",
            "test-remote:test-instance",
            "test-image-remote:",
            "--alias=test-alias",
            "--force",
        ],
    )

    LXC().publish(
        alias="test-alias",
        force=True,
        image_remote="test-image-remote",
        instance_name="test-instance",
        remote="test-remote",
        project="test-project",
    )

    assert len(fake_process.calls) == 1


def test_remote_add(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "remote",
            "add",
            "test-remote",
            "test-remote-addr",
            "--protocol=test-protocol",
        ],
    )

    LXC().remote_add(
        remote="test-remote",
        addr="test-remote-addr",
        protocol="test-protocol",
    )

    assert len(fake_process.calls) == 1


def test_remote_add_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "remote",
            "add",
            "test-remote",
            "test-remote-addr",
            "--protocol=test-protocol",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().remote_add(
            remote="test-remote",
            addr="test-remote-addr",
            protocol="test-protocol",
        )

    assert exc_info.value == LXDError(
        brief="Failed to add remote 'test-remote'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_remote_list(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "remote",
            "list",
            "--format=yaml",
        ],
        stdout="r1:\n  addr: a1\nr2:\n  addr: a2\n",
    )

    remotes = LXC().remote_list()

    assert len(fake_process.calls) == 1
    assert remotes == {"r1": {"addr": "a1"}, "r2": {"addr": "a2"}}


def test_remote_list_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "remote",
            "list",
            "--format=yaml",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().remote_list()

    assert exc_info.value == LXDError(
        brief="Failed to list remotes.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_remote_list_parse_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "remote",
            "list",
            "--format=yaml",
        ],
        stdout=b"fail:\nthis",
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().remote_list()

    assert exc_info.value == LXDError(
        brief="Failed to parse lxc remote list.",
        details=(
            "* Command that failed: 'lxc remote list --format=yaml'\n"
            "* Command output: b'fail:\\nthis'"
        ),
    )


def test_start(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "start",
            "test-remote:test-instance",
        ],
    )

    LXC().start(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_start_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "start",
            "test-remote:test-instance",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().start(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to start 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_restart(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "restart",
            "test-remote:test-instance",
        ],
    )

    LXC().restart(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_restart_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "restart",
            "test-remote:test-instance",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().restart(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to restart 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_stop(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "stop",
            "test-remote:test-instance",
        ],
    )

    LXC().stop(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
    )

    assert len(fake_process.calls) == 1


def test_stop_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "stop",
            "test-remote:test-instance",
            "--force",
            "--timeout=4",
        ],
    )

    LXC().stop(
        instance_name="test-instance",
        project="test-project",
        remote="test-remote",
        force=True,
        timeout=4,
    )

    assert len(fake_process.calls) == 1


def test_stop_error(fake_process):
    fake_process.register_subprocess(
        [
            "lxc",
            "--project",
            "test-project",
            "stop",
            "test-remote:test-instance",
        ],
        returncode=1,
    )

    with pytest.raises(LXDError) as exc_info:
        LXC().stop(
            instance_name="test-instance",
            project="test-project",
            remote="test-remote",
        )

    assert exc_info.value == LXDError(
        brief="Failed to stop 'test-instance'.",
        details=errors.details_from_called_process_error(
            exc_info.value.__cause__  # type: ignore
        ),
    )


def test_yaml_loader_invalid_timestamp():
    # This would throw a `ValueError: year 0 is out of range` if loader is
    # resolving timestamps.
    data = "last_used_at: 0000-01-01T00:00:00Z"

    obj = lxc.load_yaml(data)

    assert "last_used_at" in obj
    assert isinstance(obj["last_used_at"], str)
