#
# Copyright 2021-2024 Canonical Ltd.
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

import json

from craft_providers import pro

MACHINE_TOKEN = "test_token"  # noqa: S105


def setup_machine_token_file(tmp_path, content):
    machine_token_dir = tmp_path / "var" / "lib" / "ubuntu-advantage" / "private"
    machine_token_dir.mkdir(parents=True, exist_ok=True)

    machine_token_file = machine_token_dir / "machine-token.json"
    machine_token_file.write_text(json.dumps(content))

    return machine_token_file


def test_retrieve_pro_host_token(tmp_path, monkeypatch):
    token_file = setup_machine_token_file(tmp_path, {"machineToken": MACHINE_TOKEN})
    monkeypatch.setattr(pro, "Path", lambda x: token_file)
    assert pro.retrieve_pro_host_token() == MACHINE_TOKEN
