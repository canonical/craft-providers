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
from unittest import mock

import pytest
from craft_providers.errors import MachineTokenError
from craft_providers.pro import ProToken
from requests.exceptions import JSONDecodeError, RequestException

_CONTRACTS_API_URL = "https://contracts.canonical.com"
_CONTRACTS_API_ENDPOINT = "/v1/guest/token"


@pytest.fixture
def mock_machinetoken_open_success():
    with mock.patch(
        "builtins.open",
        new_callable=mock.mock_open,
        read_data=json.dumps({"machineToken": "test_token"}),
    ) as mock_file:
        yield mock_file


@pytest.fixture
def mock_machinetoken_open_notoken():
    with mock.patch(
        "builtins.open",
        new_callable=mock.mock_open,
        read_data=json.dumps({"machineToken": ""}),
    ) as mock_file:
        yield mock_file


@pytest.fixture
def mock_machinetoken_open_filenotfound():
    with mock.patch(
        "builtins.open",
        side_effect=FileNotFoundError,
    ) as mock_file:
        yield mock_file


@pytest.fixture
def mock_machinetoken_open_nopermission():
    with mock.patch(
        "builtins.open",
        side_effect=PermissionError,
    ) as mock_file:
        yield mock_file


@pytest.mark.parametrize(
    (
        "fixture",
        "expected_output",
        "expected_exception",
        "expected_exception_message",
    ),
    [
        ("mock_machinetoken_open_success", "test_token", None, None),
        (
            "mock_machinetoken_open_notoken",
            None,
            MachineTokenError,
            "No token in machine token file.",
        ),
        (
            "mock_machinetoken_open_filenotfound",
            None,
            MachineTokenError,
            "Machine token file does not exist.",
        ),
        (
            "mock_machinetoken_open_nopermission",
            None,
            MachineTokenError,
            "Machine token file is not accessible. Make sure you are running with root access.",
        ),
    ],
)
def test_retrieve_pro_host_token(
    fixture,
    expected_output,
    expected_exception,
    expected_exception_message,
    request,
):
    request.getfixturevalue(fixture)

    if expected_exception:
        with pytest.raises(expected_exception) as excinfo:
            ProToken.retrieve_pro_host_token()
        assert str(excinfo.value) == expected_exception_message
    else:
        assert ProToken.retrieve_pro_host_token() == expected_output


@pytest.fixture
def mock_retrieve_pro_host_token():
    """Mock retrieve_pro_host_token function."""
    return mock.patch.object(
        ProToken, "retrieve_pro_host_token", return_value="mock_machine_token"
    )


@pytest.mark.parametrize(
    (
        "mock_response_status",
        "mock_response_json",
        "mock_side_effect",
        "expected_token",
    ),
    [
        (200, {"guestToken": "mock_guest_token"}, None, "mock_guest_token"),
        (400, None, None, "mock_machine_token"),
        (200, {"guestToken": ""}, None, "mock_machine_token"),
        (None, None, JSONDecodeError("Error", "json", 0), "mock_machine_token"),
        (None, None, RequestException, "mock_machine_token"),
    ],
)
@mock.patch("requests.get")
def test_request_pro_guest_token(
    mock_get,
    mock_response_status,
    mock_response_json,
    mock_side_effect,
    expected_token,
    mock_retrieve_pro_host_token,
):
    """Test request_pro_guest_token behavior with various scenarios."""
    if mock_side_effect:
        mock_get.side_effect = mock_side_effect
    else:
        mock_response = mock.Mock()
        mock_response.status_code = mock_response_status
        mock_response.json.return_value = mock_response_json
        mock_get.return_value = mock_response

    with mock_retrieve_pro_host_token:
        token = ProToken.request_pro_guest_token()

    assert token == expected_token
    mock_get.assert_called_once()
