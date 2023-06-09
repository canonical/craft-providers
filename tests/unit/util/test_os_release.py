#
# Copyright 2021-2023 Canonical Ltd.
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

import textwrap

import pytest
from craft_providers.util.os_release import parse_os_release


@pytest.mark.parametrize(
    ("config", "expected_dict"),
    [
        (
            textwrap.dedent(
                """\
                NAME="Ubuntu"
                VERSION="22.04 (Jammy Jellyfish)"
                ID=ubuntu
                ID_LIKE=debian
                PRETTY_NAME="Ubuntu 22.04"
                VERSION_ID="22.04"
                HOME_URL="https://www.ubuntu.com/"
                SUPPORT_URL="https://help.ubuntu.com/"
                BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
                PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
                VERSION_CODENAME=jammy
                UBUNTU_CODENAME=jammy"""
            ),
            {
                "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
                "HOME_URL": "https://www.ubuntu.com/",
                "ID": "ubuntu",
                "ID_LIKE": "debian",
                "NAME": "Ubuntu",
                "PRETTY_NAME": "Ubuntu 22.04",
                "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
                "SUPPORT_URL": "https://help.ubuntu.com/",
                "UBUNTU_CODENAME": "jammy",
                "VERSION": "22.04 (Jammy Jellyfish)",
                "VERSION_CODENAME": "jammy",
                "VERSION_ID": "22.04",
            },
        ),
        (
            textwrap.dedent(
                """\
                NAME=Fedora
                VERSION="32 (Workstation Edition)"
                ID=fedora
                VERSION_ID=32
                PRETTY_NAME="Fedora 32 (Workstation Edition)"
                ANSI_COLOR="0;38;2;60;110;180"
                LOGO=fedora-logo-icon
                CPE_NAME="cpe:/o:fedoraproject:fedora:32"
                HOME_URL="https://fedoraproject.org/"
                DOCUMENTATION_URL="https://docs.fedoraproject.org/en-US/fedora/f32/system-administrators-guide/"
                SUPPORT_URL="https://fedoraproject.org/wiki/Communicating_and_getting_help"
                BUG_REPORT_URL="https://bugzilla.redhat.com/"
                REDHAT_BUGZILLA_PRODUCT="Fedora"
                REDHAT_BUGZILLA_PRODUCT_VERSION=32
                REDHAT_SUPPORT_PRODUCT="Fedora"
                REDHAT_SUPPORT_PRODUCT_VERSION=32
                PRIVACY_POLICY_URL="https://fedoraproject.org/wiki/Legal:PrivacyPolicy"
                VARIANT="Workstation Edition"
                VARIANT_ID=workstation
                """
            ),
            {
                "ANSI_COLOR": "0;38;2;60;110;180",
                "BUG_REPORT_URL": "https://bugzilla.redhat.com/",
                "CPE_NAME": "cpe:/o:fedoraproject:fedora:32",
                "DOCUMENTATION_URL": "https://docs.fedoraproject.org/en-US/fedora/f32/system-administrators-guide/",
                "HOME_URL": "https://fedoraproject.org/",
                "ID": "fedora",
                "LOGO": "fedora-logo-icon",
                "NAME": "Fedora",
                "PRETTY_NAME": "Fedora 32 (Workstation Edition)",
                "PRIVACY_POLICY_URL": "https://fedoraproject.org/wiki/Legal:PrivacyPolicy",
                "REDHAT_BUGZILLA_PRODUCT": "Fedora",
                "REDHAT_BUGZILLA_PRODUCT_VERSION": "32",
                "REDHAT_SUPPORT_PRODUCT": "Fedora",
                "REDHAT_SUPPORT_PRODUCT_VERSION": "32",
                "SUPPORT_URL": "https://fedoraproject.org/wiki/Communicating_and_getting_help",
                "VARIANT": "Workstation Edition",
                "VARIANT_ID": "workstation",
                "VERSION": "32 (Workstation Edition)",
                "VERSION_ID": "32",
            },
        ),
        ('foo="double-quotes-to-remove"', {"foo": "double-quotes-to-remove"}),
        ("foo='single-quotes-to-remove'", {"foo": "single-quotes-to-remove"}),
        ('foo="double"-quote-in-the-start', {"foo": '"double"-quote-in-the-start'}),
        ("foo='single'-quote-in-the-start", {"foo": "'single'-quote-in-the-start"}),
        ('foo=double-quote-in-"the"-middle', {"foo": 'double-quote-in-"the"-middle'}),
        ("foo=single-quote-in-'the'-middle", {"foo": "single-quote-in-'the'-middle"}),
        ('foo=double-quote-in-"the-end"', {"foo": 'double-quote-in-"the-end"'}),
        ("foo=single-quote-in-'the-end'", {"foo": "single-quote-in-'the-end'"}),
        ("foo=extra=equal", {"foo": "extra=equal"}),
        ("# ignore commented line", {}),
        ("", {}),
    ],
)
def test_parse_os_release(config, expected_dict):
    assert parse_os_release(config) == expected_dict
