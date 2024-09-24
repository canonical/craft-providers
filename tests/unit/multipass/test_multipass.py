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
import json
import pathlib
import subprocess
from unittest import mock

import pytest
from craft_providers.errors import details_from_command_error
from craft_providers.multipass import Multipass
from craft_providers.multipass.errors import MultipassError

# Shortcut any calls to time.sleep with pytest-time's instant_sleep
pytestmark = pytest.mark.usefixtures("instant_sleep")

EXAMPLE_INFO = """\
{
    "errors": [
    ],
    "info": {
        "flowing-hawfinch": {
            "disks": {
                "sda1": {
                    "total": "5019643904",
                    "used": "1339375616"
                }
            },
            "image_hash": "c5f2f08c6a1adee1f2f96d84856bf0162d33ea182dae0e8ed45768a86182d110",
            "image_release": "22.04 LTS",
            "ipv4": [
                "10.114.154.206"
            ],
            "load": [
                0.29,
                0.08,
                0.02
            ],
            "memory": {
                "total": 1028894720,
                "used": 152961024
            },
            "mounts": {
            },
            "release": "Ubuntu 22.04.2 LTS",
            "state": "Running"
        }
    }
}
"""

EXAMPLE_LIST = """\
{
    "list": [
        {
            "ipv4": [
            ],
            "name": "manageable-snipe",
            "release": "22.04 LTS",
            "state": "Starting"
        },
        {
            "ipv4": [
                "10.114.154.206"
            ],
            "name": "flowing-hawfinch",
            "release": "22.04 LTS",
            "state": "Running"
        }
    ]
}
"""


@pytest.fixture
def mock_details_from_process_error():
    details = "<details>"
    with mock.patch(
        "craft_providers.errors.details_from_called_process_error",
        return_value=details,
    ) as mock_details:
        yield mock_details


@pytest.fixture
def mock_details_from_command_error():
    details = "<details>"
    with mock.patch(
        "craft_providers.errors.details_from_command_error",
        return_value=details,
    ) as mock_details:
        yield mock_details


def test_delete(fake_process):
    fake_process.register_subprocess(["multipass", "delete", "test-instance"])

    Multipass().delete(instance_name="test-instance", purge=False)

    assert len(fake_process.calls) == 1


def test_delete_purge(fake_process):
    fake_process.register_subprocess(
        ["multipass", "delete", "test-instance", "--purge"]
    )

    Multipass().delete(instance_name="test-instance", purge=True)

    assert len(fake_process.calls) == 1


def test_delete_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "delete", "test-instance", "--purge"],
        returncode=1,
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().delete(instance_name="test-instance", purge=True)

    assert exc_info.value == MultipassError(
        brief="Failed to delete VM 'test-instance'.",
        details=mock_details_from_process_error.return_value,
    )


def test_exec(fake_process):
    fake_process.register_subprocess(
        ["multipass", "exec", "test-instance", "--", "sleep", "1"]
    )

    Multipass().exec(command=["sleep", "1"], instance_name="test-instance")

    assert len(fake_process.calls) == 1


def test_exec_error_no_check(fake_process):
    fake_process.register_subprocess(
        ["multipass", "exec", "test-instance", "--", "false"],
        returncode=1,
    )

    proc = Multipass().exec(command=["false"], instance_name="test-instance")

    assert proc.returncode == 1


def test_exec_error_with_check(fake_process):
    fake_process.register_subprocess(
        ["multipass", "exec", "test-instance", "--", "false"],
        returncode=1,
    )

    with pytest.raises(subprocess.CalledProcessError):
        Multipass().exec(command=["false"], instance_name="test-instance", check=True)


def test_info(fake_process):
    fake_process.register_subprocess(
        ["multipass", "info", "test-instance", "--format", "json"], stdout=EXAMPLE_INFO
    )

    data = Multipass().info(instance_name="test-instance")

    assert len(fake_process.calls) == 1
    assert data == json.loads(EXAMPLE_INFO)


def test_info_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "info", "test-instance", "--format", "json"],
        stderr=(
            "info failed: The following errors occurred:\n"
            'instance "foo" does not exist'
        ),
        returncode=1,
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().info(instance_name="test-instance")

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to query info for VM 'test-instance'.",
        details=mock_details_from_process_error.return_value,
    )


@pytest.mark.parametrize(
    "version_output",
    [
        b"multipass  1.7.0\nmultipassd 1.7.0\n",
        b"multipass   1.15.0-dev.354+g533e02ffc\nmultipassd  1.15.0-dev.354+g533e02ffc\n",  # Snap multipass, edge channel
        b"multipass   1.15.0-dev.2929.pr661+gc67ef6641.mac\nmultipassd  1.15.0-dev.2929.pr661+gc67ef6641.mac",  # Dev build on a mac
    ],
)
def test_is_supported_version(fake_process, version_output):
    fake_process.register_subprocess(["multipass", "version"], stdout=version_output)

    assert Multipass().is_supported_version() is True

    assert len(fake_process.calls) == 1


@pytest.mark.parametrize(
    "version_output",
    [
        b"multipass  1.4.0\nmultipassd 1.4.0\n",
        b"multipass  1.invalid.15.999\nmultipassd 999\n",
    ],
)
def test_is_supported_version_false(fake_process, version_output):
    fake_process.register_subprocess(["multipass", "version"], stdout=version_output)

    assert Multipass().is_supported_version() is False

    assert len(fake_process.calls) == 1


def test_is_supported_version_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(["multipass", "version"], stdout="invalid output")

    with pytest.raises(MultipassError) as exc_info:
        Multipass().is_supported_version()

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Unable to parse version output: b'invalid output'"
    )


def test_launch(fake_process):
    fake_process.register_subprocess(
        ["multipass", "launch", "test-image", "--name", "test-instance"]
    )

    Multipass().launch(image="test-image", instance_name="test-instance")

    assert len(fake_process.calls) == 1


def test_launch_all_opts(fake_process):
    fake_process.register_subprocess(
        [
            "multipass",
            "launch",
            "test-image",
            "--name",
            "test-instance",
            "--cpus",
            "4",
            "--memory",
            "8G",
            "--disk",
            "80G",
        ]
    )

    Multipass().launch(
        image="test-image",
        instance_name="test-instance",
        cpus="4",
        mem="8G",
        disk="80G",
    )

    assert len(fake_process.calls) == 1


def test_launch_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "launch", "test-image", "--name", "test-instance"], returncode=1
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().launch(instance_name="test-instance", image="test-image")

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to launch VM 'test-instance'.",
        details=mock_details_from_process_error.return_value,
    )


def test_list(fake_process):
    fake_process.register_subprocess(
        ["multipass", "list", "--format", "json"], stdout=EXAMPLE_LIST
    )

    vm_list = Multipass().list()

    assert len(fake_process.calls) == 1
    assert vm_list == ["manageable-snipe", "flowing-hawfinch"]


def test_list_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "list", "--format", "json"], returncode=1
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().list()

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to query list of VMs.",
        details=mock_details_from_process_error.return_value,
    )


def test_mount(fake_process):
    project_path = pathlib.Path.home() / "my-project"
    fake_process.register_subprocess(
        ["multipass", "mount", str(project_path), "test-instance:/mnt"]
    )

    Multipass().mount(
        source=project_path,
        target="test-instance:/mnt",
        uid_map=None,
        gid_map=None,
    )

    assert len(fake_process.calls) == 1


def test_mount_all_opts(fake_process):
    project_path = pathlib.Path.home() / "my-project"
    fake_process.register_subprocess(
        [
            "multipass",
            "mount",
            str(project_path),
            "test-instance:/mnt",
            "--uid-map",
            "1:2",
            "--uid-map",
            "3:4",
            "--gid-map",
            "5:6",
            "--gid-map",
            "7:8",
        ]
    )

    Multipass().mount(
        source=project_path,
        target="test-instance:/mnt",
        uid_map={"1": "2", "3": "4"},
        gid_map={"5": "6", "7": "8"},
    )

    assert len(fake_process.calls) == 1


def test_mount_error(fake_process, mock_details_from_process_error):
    project_path = pathlib.Path.home() / "my-project"
    fake_process.register_subprocess(
        ["multipass", "mount", str(project_path), "test-instance:/mnt"],
        returncode=1,
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().mount(
            source=project_path,
            target="test-instance:/mnt",
        )

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief=f"Failed to mount {str(project_path)!r} to 'test-instance:/mnt'.",
        details=mock_details_from_process_error.return_value,
    )


def test_start(fake_process):
    fake_process.register_subprocess(["multipass", "start", "test-instance"])

    Multipass().start(instance_name="test-instance")

    assert len(fake_process.calls) == 1


def test_start_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "start", "test-instance"], returncode=1
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().start(instance_name="test-instance")

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to start VM 'test-instance'.",
        details=mock_details_from_process_error.return_value,
    )


def test_stop(fake_process):
    fake_process.register_subprocess(["multipass", "stop", "test-instance"])

    Multipass().stop(instance_name="test-instance")

    assert len(fake_process.calls) == 1


def test_stop_all_opts(fake_process):
    fake_process.register_subprocess(
        ["multipass", "stop", "test-instance", "--time", "5"]
    )

    Multipass().stop(instance_name="test-instance", delay_mins=5)

    assert len(fake_process.calls) == 1


def test_stop_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "stop", "test-instance"], returncode=1
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().stop(instance_name="test-instance")

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to stop VM 'test-instance'.",
        details=mock_details_from_process_error.return_value,
    )


def test_transfer(fake_process):
    fake_process.register_subprocess(
        ["multipass", "transfer", "test-instance:/test1", "/test2"]
    )

    Multipass().transfer(source="test-instance:/test1", destination="/test2")

    assert len(fake_process.calls) == 1


def test_transfer_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "transfer", "test-instance:/test1", "/test2"], returncode=1
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().transfer(source="test-instance:/test1", destination="/test2")

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to transfer 'test-instance:/test1' to '/test2'.",
        details=mock_details_from_process_error.return_value,
    )


def test_transfer_destination_io(fake_process):
    stream = mock.Mock()
    fake_process.register_subprocess(
        ["multipass", "transfer", "test-instance:/test1", "-"], stdout=b"Hello World!\n"
    )

    Multipass().transfer_destination_io(
        source="test-instance:/test1", destination=stream
    )

    assert len(fake_process.calls) == 1
    assert stream.mock_calls == [mock.call.write(b"Hello World!\n")]


def test_transfer_destination_io_chunk_size(fake_process):
    stream = mock.Mock()
    fake_process.register_subprocess(
        ["multipass", "transfer", "test-instance:/test1", "-"], stdout=b"Hello World!\n"
    )

    Multipass().transfer_destination_io(
        source="test-instance:/test1", destination=stream, chunk_size=4
    )

    assert len(fake_process.calls) == 1
    assert stream.mock_calls == [
        mock.call.write(b"Hell"),
        mock.call.write(b"o Wo"),
        mock.call.write(b"rld!"),
        mock.call.write(b"\n"),
    ]


def test_transfer_destination_io_error(fake_process):
    cmd = ["multipass", "transfer", "test-instance:/test1", "-"]
    returncode = 1
    stdout = None
    stderr = b"some stderr"

    fake_process.register_subprocess(
        cmd,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )

    with io.BytesIO() as stream, pytest.raises(MultipassError) as exc_info:
        Multipass().transfer_destination_io(
            source="test-instance:/test1", destination=stream
        )

    assert exc_info.value == MultipassError(
        brief="Failed to transfer file 'test-instance:/test1'.",
        details=details_from_command_error(
            cmd=cmd, returncode=returncode, stdout=stdout, stderr=stderr
        ),
    )


@mock.patch("subprocess.Popen")
def test_transfer_source_io(mock_popen):
    mock_popen.return_value.__enter__.return_value.returncode = 0

    test_io = io.BytesIO(b"Hello World!\n")

    Multipass().transfer_source_io(
        source=test_io,
        destination="test-instance:/tmp/foo",
    )

    assert mock_popen.mock_calls == [
        mock.call(
            ["multipass", "transfer", "-", "test-instance:/tmp/foo"],
            stdin=-1,
            stderr=-1,
        ),
        mock.call().__enter__(),
        mock.call().__enter__().stdin.write(b"Hello World!\n"),
        mock.call().__enter__().stdin.close(),
        mock.call().__enter__().stderr.read(),
        mock.call().__exit__(None, None, None),
    ]


@mock.patch("subprocess.Popen")
def test_transfer_source_io_chunk_size(mock_popen):
    mock_popen.return_value.__enter__.return_value.returncode = 0

    test_io = io.BytesIO(b"Hello World!\n")

    Multipass().transfer_source_io(
        source=test_io,
        destination="test-instance:/tmp/foo",
        chunk_size=4,
    )

    assert mock_popen.mock_calls == [
        mock.call(
            ["multipass", "transfer", "-", "test-instance:/tmp/foo"],
            stdin=-1,
            stderr=-1,
        ),
        mock.call().__enter__(),
        mock.call().__enter__().stdin.write(b"Hell"),
        mock.call().__enter__().stdin.write(b"o Wo"),
        mock.call().__enter__().stdin.write(b"rld!"),
        mock.call().__enter__().stdin.write(b"\n"),
        mock.call().__enter__().stdin.close(),
        mock.call().__enter__().stderr.read(),
        mock.call().__exit__(None, None, None),
    ]


@mock.patch("subprocess.Popen")
def test_transfer_source_io_error(mock_popen, mock_details_from_command_error):
    mock_popen.return_value.__enter__.return_value.returncode = -1
    test_io = io.BytesIO(b"Hello World!\n")

    with pytest.raises(MultipassError) as exc_info:
        Multipass().transfer_source_io(
            source=test_io,
            destination="test-instance:/tmp/foo",
        )

    assert exc_info.value == MultipassError(
        brief="Failed to transfer file to destination 'test-instance:/tmp/foo'.",
        details=mock_details_from_command_error.return_value,
    )
    assert mock_popen.mock_calls == [
        mock.call(
            ["multipass", "transfer", "-", "test-instance:/tmp/foo"],
            stdin=-1,
            stderr=-1,
        ),
        mock.call().__enter__(),
        mock.call().__enter__().stdin.write(b"Hello World!\n"),
        mock.call().__enter__().stdin.close(),
        mock.call().__enter__().stderr.read(),
        mock.call().__exit__(None, None, None),
    ]


def test_umount(fake_process):
    fake_process.register_subprocess(["multipass", "umount", "test-instance:/mnt"])

    Multipass().umount(mount="test-instance:/mnt")

    assert len(fake_process.calls) == 1


def test_umount_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(
        ["multipass", "umount", "test-instance:/mnt"], returncode=1
    )

    with pytest.raises(MultipassError) as exc_info:
        Multipass().umount(mount="test-instance:/mnt")

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to unmount 'test-instance:/mnt'.",
        details=mock_details_from_process_error.return_value,
    )


def test_wait_until_ready(fake_process, mocker):
    fake_process.register_subprocess(
        ["multipass", "version"],
        returncode=0,
        stdout="multipass  1.6.2\nmultipassd 1.6.3\n",
    )
    multipass = Multipass()
    mocker.patch(
        "craft_providers.const.RETRY_WAIT",
        return_value=0.01,
    )
    multipass_version, multipassd_version = multipass.wait_until_ready()

    assert len(fake_process.calls) == 1

    assert multipass_version == "1.6.2"
    assert multipassd_version == "1.6.3"


@pytest.mark.parametrize("wait_count", [0, 1, 2, 3, 4, 5])
def test_wait_until_ready_with_retries(fake_process, wait_count, mocker):
    for _ in range(0, wait_count):
        fake_process.register_subprocess(
            ["multipass", "version"], returncode=0, stdout="multipass  1.6.2\n"
        )

    fake_process.register_subprocess(
        ["multipass", "version"],
        returncode=0,
        stdout="multipass  1.6.2\nmultipassd 1.6.3\n",
    )

    mocker.patch(
        "craft_providers.const.RETRY_WAIT",
        return_value=0.01,
    )
    multipass = Multipass()
    multipass_version, multipassd_version = multipass.wait_until_ready()

    assert len(fake_process.calls) == wait_count + 1

    assert multipass_version == "1.6.2"
    assert multipassd_version == "1.6.3"


@pytest.mark.parametrize(
    ("time_values", "timeout", "version_calls"),
    [
        ([9.0, 9.5], 0.5, 1),
        ([9.0, 9.4, 9.5], 0.5, 2),
        ([10.0, 20.0, 30.0, 40.0], 30.0, 3),
    ],
)
def test_wait_until_ready_timeout_error(
    fake_process, time_values, timeout, version_calls, mocker
):
    fake_process.register_subprocess(
        ["multipass", "version"],
        returncode=0,
        stdout="multipass  1.6.2\n",
        occurrences=version_calls,
    )
    mocker.patch(
        "craft_providers.const.RETRY_WAIT",
        return_value=0.01,
    )

    with mock.patch("time.time", side_effect=time_values):
        with pytest.raises(MultipassError) as exc_info:
            multipass = Multipass()
            multipass.wait_until_ready(timeout=timeout)

    assert exc_info.value == MultipassError(
        "Timed out waiting for Multipass to become ready."
    )

    assert len(fake_process.calls) == version_calls


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("multipass  1.6.2\n", ("1.6.2", None)),
        ("multipass  1.6.2+mac\n", ("1.6.2", None)),
        ("multipass  1.6.2+win\r\n", ("1.6.2", None)),
        ("multipass  1.6.2\nmultipassd 1.6.3\n", ("1.6.2", "1.6.3")),
        ("multipass  1.6.2+mac\nmultipassd 1.6.3+mac\n", ("1.6.2", "1.6.3")),
        ("multipass  1.6.2+win\r\nmultipassd 1.6.3+win\r\n", ("1.6.2", "1.6.3")),
        (
            (
                "multipass  1.6.2+win\r\nmultipassd 1.6.3+win\r\n"
                "some\r\nother\r\nnotice\r\n"
            ),
            ("1.6.2", "1.6.3"),
        ),
        pytest.param(
            b"multipass   1.15.0-dev.354+g533e02ffc\nmultipassd  1.15.0-dev.354+g533e02ffc\n",
            ("1.15.0-dev.354", "1.15.0-dev.354"),
            id="snap-edge-channel",
        ),
        pytest.param(
            b"multipass   1.15.0-dev.2929.pr661+gc67ef6641.mac\nmultipassd  1.15.0-dev.2929.pr661+gc67ef6641.mac",
            ("1.15.0-dev.2929.pr661", "1.15.0-dev.2929.pr661"),
            id="macos-dev-build",
        ),
    ],
)
def test_version(fake_process, output, expected):
    fake_process.register_subprocess(["multipass", "version"], stdout=output)

    assert Multipass().version() == expected


def test_version_decode_error(fake_process):
    fake_process.register_subprocess(
        ["multipass", "version"], stdout=b"multipass 1.6.2\xd0"
    )

    with mock.patch("locale.getpreferredencoding", return_value="ascii"):
        with pytest.raises(MultipassError) as exc_info:
            Multipass().version()

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to check version.",
        details="Failed to decode output: b'multipass 1.6.2\\xd0'",
    )


def test_version_error(fake_process, mock_details_from_process_error):
    fake_process.register_subprocess(["multipass", "version"], returncode=1)

    with pytest.raises(MultipassError) as exc_info:
        Multipass().version()

    assert len(fake_process.calls) == 1
    assert exc_info.value == MultipassError(
        brief="Failed to check version.",
        details=mock_details_from_process_error.return_value,
    )


def test_generic_run_base():
    """The generic run should check the return code and capture the output."""
    with mock.patch("subprocess.run") as run_mock:
        Multipass()._run(["foo", "1"])
    run_mock.assert_called_with(
        ["multipass", "foo", "1"], check=True, capture_output=True
    )


def test_generic_run_extra_args():
    """Support for extra parameters in the generic run."""
    with mock.patch("subprocess.run") as run_mock:
        Multipass()._run(["foo", "1"], extra="whatever")
    run_mock.assert_called_with(
        ["multipass", "foo", "1"], check=True, capture_output=True, extra="whatever"
    )
