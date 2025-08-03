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
import yaml

from craft_providers import pro

from tests.unit.test_pro import (
    CONTRACT_ID,
    MACHINE_ID,
    MACHINE_TOKEN,
    CONTRACTS_API_URL,
)


def test_retrieve_pro_host_info(tmp_path, monkeypatch):
    """Test that the Pro host information is retrieved correctly from the mock files."""
    machine_token_file = tmp_path / "machine-token.json"
    pro_config_file = tmp_path / "uaclient.conf"

    # Create mock file mapping
    mock_file_mapping = {
        "/var/lib/ubuntu-advantage/private/machine-token.json": machine_token_file,
        "/etc/ubuntu-advantage/uaclient.conf": pro_config_file,
    }

    machine_token_file.write_text(
        json.dumps(
            {
                "machineToken": MACHINE_TOKEN,
                "machineTokenInfo": {
                    "machineId": MACHINE_ID,
                    "contractInfo": {
                        "id": CONTRACT_ID,
                    },
                },
            }
        )
    )

    pro_config_file.write_text(
        yaml.safe_dump(
            {
                "contract_url": CONTRACTS_API_URL,
                "log_level": "debug",
            }
        )
    )

    monkeypatch.setattr(pro, "Path", lambda x: mock_file_mapping.get(str(x), x))
    output = pro.retrieve_pro_host_info()
    assert output.machine_token == MACHINE_TOKEN
    assert output.machine_id == MACHINE_ID
    assert output.contract_id == CONTRACT_ID
    assert output.contract_url == CONTRACTS_API_URL
