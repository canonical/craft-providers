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


from craft_providers.util import snap_cmd


def test_ack(tmp_path):
    command = snap_cmd.formulate_ack_command(snap_assert_path=tmp_path)
    assert command == ["snap", "ack", tmp_path.as_posix()]


def test_known(tmp_path):
    command = snap_cmd.formulate_known_command(query=["test1", "test2"])
    assert command == ["snap", "known", "test1", "test2"]


def test_local_install_strict(tmp_path):
    assert snap_cmd.formulate_local_install_command(
        classic=False, dangerous=False, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix()]


def test_local_install_classic(tmp_path):
    assert snap_cmd.formulate_local_install_command(
        classic=True, dangerous=False, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix(), "--classic"]


def test_local_install_dangerous(tmp_path):
    assert snap_cmd.formulate_local_install_command(
        classic=False, dangerous=True, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix(), "--dangerous"]


def test_local_install_all_opts(tmp_path):
    assert snap_cmd.formulate_local_install_command(
        classic=True, dangerous=True, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix(), "--classic", "--dangerous"]


def test_pack():
    command = snap_cmd.formulate_pack_command(
        snap_name="testsnap", output_file_path="testpath"
    )
    assert command == ["snap", "pack", "/snap/testsnap/current/", "--filename=testpath"]


def test_remote_install_strict():
    snap_name, channel = "testsnap", "edge"
    cmd = snap_cmd.formulate_remote_install_command(snap_name, channel, classic=False)
    assert cmd == ["snap", "install", snap_name, "--channel", channel]


def test_remote_install_classic():
    snap_name, channel = "testsnap", "edge"
    cmd = snap_cmd.formulate_remote_install_command(snap_name, channel, classic=True)
    assert cmd == ["snap", "install", snap_name, "--channel", channel, "--classic"]


def test_refresh():
    snap_name, channel = "testsnap", "edge"
    cmd = snap_cmd.formulate_refresh_command(snap_name, channel)
    assert cmd == ["snap", "refresh", snap_name, "--channel", channel]


def test_remove():
    snap_name = "testsnap"
    cmd = snap_cmd.formulate_remove_command(snap_name)
    assert cmd == ["snap", "remove", snap_name]
