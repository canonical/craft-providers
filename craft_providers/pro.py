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

"""Pro-related module."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from craft_providers.errors import GuestTokenError, MachineTokenError

logger = logging.getLogger(__name__)


@dataclass
class ProHostInfo:
    """Dataclass for info obtained from a pro host."""

    machine_token: str
    machine_id: str
    contract_id: str


def retrieve_pro_host_info() -> ProHostInfo:
    """Get the machine info from the pro host."""
    try:
        token_file = Path("/var/lib/ubuntu-advantage/private/machine-token.json")
        content = json.loads(token_file.read_text())
        machine_token = content.get("machineToken", "")
        machine_id = content.get("machineTokenInfo", {}).get("machineId")
        contract_id = (
            content.get("machineTokenInfo", {}).get("contractInfo", {}).get("id")
        )
        if not machine_token:
            raise MachineTokenError("No machineToken in machine token file.")
        if not machine_id:
            raise MachineTokenError("No machineId in machine token file.")
        if not contract_id:
            raise MachineTokenError("No contractID in machine token file.")
        return ProHostInfo(machine_token, machine_id, contract_id)
    except FileNotFoundError:
        raise MachineTokenError("Machine token file does not exist.")
    except PermissionError:
        raise MachineTokenError(
            brief="Machine token file is not accessible.",
            resolution="Make sure you are running with root access.",
        )


def request_pro_guest_token() -> str:
    """Request a guest token from contracts API."""
    info = retrieve_pro_host_info()

    try:
        base_url = "https://contracts.canonical.com"
        endpoint = f"/v1/contracts/{info.contract_id}/context/machines/{info.machine_id}/guest-token"
        response = requests.get(
            base_url + endpoint,
            headers={"Authorization": f"Bearer {info.machine_token}"},
            timeout=20,
        )
        response.raise_for_status()

        guest_token = response.json().get("guestToken", "")
        if not guest_token:
            raise GuestTokenError(brief="API response does not contain a guest token.")
        logger.info("Guest token received successfully.")
        return guest_token  # noqa: TRY300
    except requests.exceptions.JSONDecodeError:
        # recrived data was not in json format
        raise GuestTokenError(
            brief="Error decoding JSON data when retrieving guest token."
        )
    except requests.exceptions.RequestException:
        # guest token acquiring failed
        raise GuestTokenError(
            brief="Request error when trying to retrieve the guest token."
        )
