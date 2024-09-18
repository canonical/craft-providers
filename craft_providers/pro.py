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
from pathlib import Path

import requests

from craft_providers.errors import MachineTokenError

logger = logging.getLogger(__name__)


def retrieve_pro_host_token() -> str:
    """Get the machine token from the pro host."""
    try:
        token_file = Path("/var/lib/ubuntu-advantage/private/machine-token.json")
        content = json.loads(token_file.read_text())
        machine_token = content.get("machineToken", "")
        if not machine_token:
            raise MachineTokenError("No token in machine token file.")
        return machine_token  # noqa: TRY300
    except FileNotFoundError:
        raise MachineTokenError("Machine token file does not exist.")
    except PermissionError:
        raise MachineTokenError(
            brief="Machine token file is not accessible.",
            resolution="Make sure you are running with root access.",
        )


def request_pro_guest_token() -> str:
    """Request a guest token from contracts API."""
    machine_token = retrieve_pro_host_token()

    try:
        base_url = "https://contracts.canonical.com"
        endpoint = "/v1/guest/token"
        response = requests.get(
            base_url + endpoint,
            headers={"Authorization": f"Bearer {machine_token}"},
            timeout=15,
        )
        if response.status_code != 200:
            # fallback mechanism
            logger.info(
                "Could not obtain a guest token. Falling back to machine \
                token."
            )
            return machine_token

        guest_token = response.json().get("guestToken", "")
        if not guest_token:
            # fallback to machine token
            logger.info("Guest token is empty. Falling back to machine token.")
            return machine_token
        logger.info("Guest token received successfully.")
        return guest_token  # noqa: TRY300
    except requests.exceptions.JSONDecodeError:
        # recrived data was not in json format
        logger.info(
            "Error decoding JSON data when retrieving guest token. Falling\
            back to machine token."
        )
        return machine_token
    except requests.exceptions.RequestException:
        # guest token acquiring failed
        logger.info(
            "Request error when trying to retrieve the guest token. \
            Falling back to machine token."
        )
        return machine_token
