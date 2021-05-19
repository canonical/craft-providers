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


from craft_providers.util import snap_cmd


def test_install_strict(tmp_path):
    assert snap_cmd.formulate_install_command(
        classic=False, dangerous=False, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix()]


def test_install_classic(tmp_path):
    assert snap_cmd.formulate_install_command(
        classic=True, dangerous=False, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix(), "--classic"]


def test_install_dangerous(tmp_path):
    assert snap_cmd.formulate_install_command(
        classic=False, dangerous=True, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix(), "--dangerous"]


def test_install_all_opts(tmp_path):
    assert snap_cmd.formulate_install_command(
        classic=True, dangerous=True, snap_path=tmp_path
    ) == ["snap", "install", tmp_path.as_posix(), "--classic", "--dangerous"]
