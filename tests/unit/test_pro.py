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


@pytest.mark.usefixtures("mock_machinetoken_open_success")
def test_retrieve_pro_host_token_success():
    assert ProToken.retrieve_pro_host_token() == "test_token"


@pytest.mark.usefixtures("mock_machinetoken_open_notoken")
def test_retrieve_pro_host_token_notoken():
    with pytest.raises(MachineTokenError) as excinfo:
        ProToken.retrieve_pro_host_token()

    assert str(excinfo.value) == "No token in machine token file."


@pytest.mark.usefixtures("mock_machinetoken_open_filenotfound")
def test_retrieve_pro_host_token_filenotfound():
    with pytest.raises(MachineTokenError) as excinfo:
        ProToken.retrieve_pro_host_token()

    assert str(excinfo.value) == "Machine token file does not exist."


@pytest.mark.usefixtures("mock_machinetoken_open_nopermission")
def test_retrieve_pro_host_token_nopermission():
    with pytest.raises(MachineTokenError) as excinfo:
        ProToken.retrieve_pro_host_token()

    assert str(excinfo.value) == (
        "Machine token file is not accessible. Make sure you are running with "
        "root access."
    )


@pytest.fixture
def mock_retrieve_pro_host_token():
    return mock.patch.object(
        ProToken, "retrieve_pro_host_token", return_value="mock_machine_token"
    )


@mock.patch("requests.get")
def test_request_pro_guest_token_success(mock_get, mock_retrieve_pro_host_token):
    """Test successful guest token retrieval."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"guestToken": "mock_guest_token"}
    mock_get.return_value = mock_response

    with mock_retrieve_pro_host_token:
        guest_token = ProToken.request_pro_guest_token()

    assert guest_token == "mock_guest_token"  # noqa: S105
    mock_get.assert_called_once_with(
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        headers={"Authorization": "Bearer mock_machine_token"},
        timeout=15,
    )


@mock.patch("requests.get")
def test_request_pro_guest_token_fallback_due_to_status_code(
    mock_get, mock_retrieve_pro_host_token
):
    """Test fallback to machine token due to non-200 status code."""
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_get.return_value = mock_response

    with mock_retrieve_pro_host_token:
        token = ProToken.request_pro_guest_token()

    assert token == "mock_machine_token"  # noqa: S105
    mock_get.assert_called_once()


@mock.patch("requests.get")
def test_request_pro_guest_token_fallback_due_to_empty_guest_token(
    mock_get, mock_retrieve_pro_host_token
):
    """Test fallback to machine token due to empty guest token."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"guestToken": ""}
    mock_get.return_value = mock_response

    with mock_retrieve_pro_host_token:
        token = ProToken.request_pro_guest_token()

    assert token == "mock_machine_token"  # noqa: S105
    mock_get.assert_called_once()


@mock.patch("requests.get")
def test_request_pro_guest_token_fallback_due_to_json_decode_error(
    mock_get, mock_retrieve_pro_host_token
):
    """Test fallback to machine token due to JSONDecodeError."""
    mock_get.side_effect = JSONDecodeError("Error", "json", 0)

    with mock_retrieve_pro_host_token:
        token = ProToken.request_pro_guest_token()

    assert token == "mock_machine_token"  # noqa: S105
    mock_get.assert_called_once()


@mock.patch("requests.get")
def test_request_pro_guest_token_fallback_due_to_request_exception(
    mock_get, mock_retrieve_pro_host_token
):
    """Test fallback to machine token due to RequestException."""
    mock_get.side_effect = RequestException

    with mock_retrieve_pro_host_token:
        token = ProToken.request_pro_guest_token()

    assert token == "mock_machine_token"  # noqa: S105
    mock_get.assert_called_once()
