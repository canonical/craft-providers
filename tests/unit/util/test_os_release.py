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

import textwrap

import pytest

from craft_providers.util.os_release import parse_os_release


@pytest.mark.parametrize(
    "config,expected_dict",
    [
        (
            textwrap.dedent(
                """\
                NAME="Ubuntu"
                VERSION="20.10 (Groovy Gorilla)"
                ID=ubuntu
                ID_LIKE=debian
                PRETTY_NAME="Ubuntu 20.10"
                VERSION_ID="20.10"
                HOME_URL="https://www.ubuntu.com/"
                SUPPORT_URL="https://help.ubuntu.com/"
                BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
                PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
                VERSION_CODENAME=groovy
                UBUNTU_CODENAME=groovy"""
            ),
            {
                "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
                "HOME_URL": "https://www.ubuntu.com/",
                "ID": "ubuntu",
                "ID_LIKE": "debian",
                "NAME": "Ubuntu",
                "PRETTY_NAME": "Ubuntu 20.10",
                "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
                "SUPPORT_URL": "https://help.ubuntu.com/",
                "UBUNTU_CODENAME": "groovy",
                "VERSION": "20.10 (Groovy Gorilla)",
                "VERSION_CODENAME": "groovy",
                "VERSION_ID": "20.10",
            },
        ),
        ('foo="quotes-to-remove"', {"foo": "quotes-to-remove"}),
        ("foo=extra=equal", {"foo": "extra=equal"}),
        ('foo="quote-in-"the-middle"', {"foo": 'quote-in-"the-middle'}),
    ],
)
def test_parse_os_release(config, expected_dict):
    assert parse_os_release(config) == expected_dict
