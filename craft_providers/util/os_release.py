"""Parser for /etc/os-release."""
from typing import Dict


def parse_os_release(content: str) -> Dict[str, str]:
    """Parser for /etc/os-release.

    Example os-release contents::

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
        UBUNTU_CODENAME=groovy

    :param content: String contents of os-release file.

    :returns: Dictionary of key-mappings found in os-release.  Values are
              stripped of encapsulating double-quotes.
    """

    mappings: Dict[str, str] = {}
    for line in content.split("\n"):
        line = line.strip()
        if "=" in line:
            key, value = line.split("=", maxsplit=1)
            mappings[key] = value.strip('"')
    return mappings
