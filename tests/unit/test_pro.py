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
import responses
from craft_providers import pro
from craft_providers.errors import MachineTokenError
from requests.exceptions import RequestException

_CONTRACTS_API_URL = "https://contracts.canonical.com"
_CONTRACTS_API_ENDPOINT = "/v1/guest/token"
MACHINE_TOKEN = "machine_test_token"  # noqa: S105
GUEST_TOKEN = "guest_test_token"  # noqa: S105


assert_requests = responses.activate(assert_all_requests_are_fired=True)


@pytest.fixture
def mock_machinetoken_open_success(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        return_value=json.dumps({"machineToken": MACHINE_TOKEN}),
    )


@pytest.fixture
def mock_machinetoken_open_notoken(mocker):
    return mocker.patch(
        "pathlib.Path.read_text",
        return_value=json.dumps({"machineToken": ""}),
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


def test_retrieve_pro_host_token_success(mock_machinetoken_open_success):
    assert pro.retrieve_pro_host_token() == MACHINE_TOKEN


def test_retrieve_pro_host_token_notoken(mock_machinetoken_open_notoken):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_token()
    assert raised.value.brief == "No token in machine token file."


def test_retrieve_pro_host_token_filenotfound(mock_machinetoken_open_filenotfound):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_token()
    assert raised.value.brief == "Machine token file does not exist."


def test_retrieve_pro_host_token_nopermission(mock_machinetoken_open_nopermission):
    with pytest.raises(MachineTokenError) as raised:
        pro.retrieve_pro_host_token()
    assert raised.value.brief == "Machine token file is not accessible."


@pytest.fixture
def mock_retrieve_pro_host_token(mocker):
    """Mock retrieve_pro_host_token function."""
    return mocker.patch.object(
        pro, "retrieve_pro_host_token", return_value=MACHINE_TOKEN
    )


@assert_requests
def test_request_pro_guest_token_success(mock_retrieve_pro_host_token):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        json={"guestToken": GUEST_TOKEN},
        status=200,
    )
    assert pro.request_pro_guest_token() == GUEST_TOKEN


@assert_requests
def test_request_pro_guest_token_emptytoken(mock_retrieve_pro_host_token):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        json={"guestToken": ""},
        status=200,
    )
    assert pro.request_pro_guest_token() == MACHINE_TOKEN


@assert_requests
def test_request_pro_guest_token_http400(mock_retrieve_pro_host_token):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        status=400,
    )
    assert pro.request_pro_guest_token() == MACHINE_TOKEN


@assert_requests
def test_request_pro_guest_token_jsonerror(mock_retrieve_pro_host_token):
    responses.add(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        body="random",
        status=200,
    )
    assert pro.request_pro_guest_token() == MACHINE_TOKEN


def raise_request_exception(request):
    raise RequestException


@assert_requests
def test_request_pro_guest_token_requesterror(mock_retrieve_pro_host_token):
    responses.add_callback(
        responses.GET,
        _CONTRACTS_API_URL + _CONTRACTS_API_ENDPOINT,
        callback=raise_request_exception,
    )
    assert pro.request_pro_guest_token() == MACHINE_TOKEN
