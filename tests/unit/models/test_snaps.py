#
# Copyright 2021 Canonical Ltd.
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
from typing import Any

import pydantic
import pytest
from craft_providers.models.snaps import SnapInfo

SNAPD_RESPONSE: dict[str, Any] = {
    "type": "sync",
    "status-code": 200,
    "status": "OK",
    "result": {
        "id": "vMTKRaLjnOJQetI78HjntT37VuoyssFE",
        "title": "snapcraft",
        "summary": "easily create snaps",
        "description": "Package, distribute, and update any app for Linux and IoT.",
        "icon": "/v2/icons/snapcraft/icon",
        "installed-size": 73154560,
        "install-date": "2026-02-09T22:06:00.45838953+05:30",
        "name": "snapcraft",
        "publisher": {
            "id": "canonical",
            "username": "canonical",
            "display-name": "Canonical",
            "validation": "verified",
        },
        "developer": "canonical",
        "status": "active",
        "type": "app",
        "base": "core24",
        "version": "8.13.2",
        "channel": "stable",
        "tracking-channel": "latest/stable",
        "ignore-validation": False,
        "revision": "16570",
        "confinement": "classic",
        "grade": "stable",
        "private": False,
        "devmode": False,
        "jailmode": False,
        "apps": [{"snap": "snapcraft", "name": "snapcraft"}],
        "license": "GPL-3.0",
        "mounted-from": "/var/lib/snapd/snaps/snapcraft_16570.snap",
        "links": {
            "contact": ["https://forum.snapcraft.io/c/snapcraft"],
            "website": ["https://github.com/snapcore/snapcraft"],
        },
        "contact": "https://forum.snapcraft.io/c/snapcraft",
        "website": "https://github.com/snapcore/snapcraft",
        "media": [
            {
                "type": "icon",
                "url": "https://dashboard.snapcraft.io/site_media/appmedia/2018/04/Snapcraft-logo-bird.png",
                "width": 256,
                "height": 256,
            }
        ],
    },
}


SNAPD_ERROR_RESPONSE: dict[str, Any] = {
    "type": "error",
    "status-code": 404,
    "status": "Not Found",
    "result": {
        "message": "snap not installed",
        "kind": "snap-not-found",
        "value": "foo",
    },
}


def test_full_real_snapd_response_validates():
    """A full real snapd response should validate correctly."""
    snap = SnapInfo.model_validate(SNAPD_RESPONSE["result"])

    assert snap.id == "vMTKRaLjnOJQetI78HjntT37VuoyssFE"
    assert snap.revision == "16570"
    assert snap.publisher is not None
    assert snap.publisher.id == "canonical"
    assert snap.base == "core24"


def test_snap_info_rejects_real_error_response():
    """A real snapd error response should not validate as SnapInfo."""
    with pytest.raises(pydantic.ValidationError):
        SnapInfo.model_validate(SNAPD_ERROR_RESPONSE)


@pytest.mark.parametrize("missing_key", ["id", "revision"])
def test_snap_info_missing_required_field(missing_key):
    """Missing required fields should raise ValidationError."""
    base = SNAPD_RESPONSE["result"]
    data = {k: v for k, v in base.items() if k != missing_key}

    with pytest.raises(pydantic.ValidationError, match=missing_key):
        SnapInfo.model_validate(data)


def test_snap_info_optional_fields_can_be_omitted():
    """Optional fields should not be required for validation."""
    minimal_data = {
        "id": "abc",
        "revision": "1",
    }

    snap = SnapInfo.model_validate(minimal_data)

    assert snap.name is None
    assert snap.type is None
    assert snap.version is None
    assert snap.channel is None
    assert snap.confinement is None
    assert snap.publisher is None
    assert snap.base is None


def test_snap_info_ignores_extra_fields():
    """Unknown fields from snapd should be ignored."""
    data = {
        "id": "abc",
        "revision": "1",
        "future-field": "something-new",
    }

    snap = SnapInfo.model_validate(data)

    assert snap.id == "abc"
    assert "future-field" not in snap.model_dump()
