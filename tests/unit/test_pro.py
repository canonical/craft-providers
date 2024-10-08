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

import json

import pytest
import responses
from craft_providers import pro
from craft_providers.errors import GuestTokenError, MachineTokenError

MACHINE_TOKEN = "machine_test_token"  # noqa: S105
MACHINE_ID = "XYZ"
CONTRACT_ID = "ABC"
GUEST_TOKEN = "guest_test_token"  # noqa: S105
_CONTRACTS_API_URL = "https://contracts.canonical.com"
_CONTRACTS_API_ENDPOINT = (
    f"/v1/contracts/{CONTRACT_ID}/context/machines/{MACHINE_ID}/guest-token"
)


assert_requests = responses.activate(assert_all_requests_are_fired=True)


@pytest.fixture
def mock_machinetoken_open_success(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        return_value=json.dumps(
            {
                "machineToken": MACHINE_TOKEN,
                "machineTokenInfo": {
                    "machineId": MACHINE_ID,
                    "contractInfo": {
                        "id": CONTRACT_ID,
                    },
                },
            }
        ),
    )


@pytest.fixture
def mock_machinetoken_open_no_machinetoken(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        return_value=json.dumps({"machineToken": ""}),
    )


@pytest.fixture
def mock_machinetoken_open_no_machineid(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        return_value=json.dumps(
            {
                "machineToken": MACHINE_TOKEN,
                "machineTokenInfo": {
                    "machineId": "",
                    "contractInfo": {
                        "id": CONTRACT_ID,
                    },
                },
            }
        ),
    )


@pytest.fixture
def mock_machinetoken_open_no_contractid(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        return_value=json.dumps(
            {
                "machineToken": MACHINE_TOKEN,
                "machineTokenInfo": {
                    "machineId": MACHINE_ID,
                    "contractInfo": {
                        "id": "",
                    },
                },
            }
        ),
    )


@pytest.fixture
def mock_machinetoken_open_filenotfound(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        side_effect=FileNotFoundError,
    )


@pytest.fixture
def mock_machinetoken_open_nopermission(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        side_effect=PermissionError,
    )


def test_retrieve_pro_host_info_success(mock_machinetoken_open_success):
    output = pro.retrieve_pro_host_info()
    assert output.machine_token == MACHINE_TOKEN
    assert output.machine_id == MACHINE_ID
    assert output.contract_id == CONTRACT_ID


def test_retrieve_pro_host_info_no_machinetoken(mock_machinetoken_open_no_machinetoken):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_info()
    assert raised.value.brief == "No machineToken in machine token file."


def test_retrieve_pro_host_info_no_machineid(mock_machinetoken_open_no_machineid):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_info()
    assert raised.value.brief == "No machineId in machine token file."


def test_retrieve_pro_host_info_no_contractid(mock_machinetoken_open_no_contractid):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_info()
    assert raised.value.brief == "No contractID in machine token file."


def test_retrieve_pro_host_info_filenotfound(mock_machinetoken_open_filenotfound):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_info()
    assert raised.value.brief == "Machine token file does not exist."


def test_retrieve_pro_host_info_nopermission(mock_machinetoken_open_nopermission):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_info()
    assert raised.value.brief == "Machine token file is not accessible."


@pytest.fixture
def mock_retrieve_pro_host_info(mocker):
    """Mock retrieve_pro_host_info function."""
    return mocker.patch.object(
        pro,
        "retrieve_pro_host_info",
        return_value=pro.ProHostInfo(MACHINE_TOKEN, MACHINE_ID, CONTRACT_ID),
    )


@assert_requests
def test_request_pro_guest_token_success(mock_retrieve_pro_host_info):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        json={"guestToken": GUEST_TOKEN},
        status=200,
    )
    assert pro.request_pro_guest_token() == GUEST_TOKEN


@assert_requests
def test_request_pro_guest_token_emptytoken(mock_retrieve_pro_host_info):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        json={"guestToken": ""},
        status=200,
    )

    with pytest.raises(GuestTokenError) as raised:
        pro.request_pro_guest_token()
    assert raised.value.brief == "API response does not contain a guest token."


@assert_requests
def test_request_pro_guest_token_http400(mock_retrieve_pro_host_info):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        status=400,
    )

    with pytest.raises(GuestTokenError) as raised:
        pro.request_pro_guest_token()
    assert (
        raised.value.brief == "Request error when trying to retrieve the guest token."
    )


@assert_requests
def test_request_pro_guest_token_jsonerror(mock_retrieve_pro_host_info):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        body="random",
        status=200,
    )

    with pytest.raises(GuestTokenError) as raised:
        pro.request_pro_guest_token()
    assert raised.value.brief == "Error decoding JSON data when retrieving guest token."
