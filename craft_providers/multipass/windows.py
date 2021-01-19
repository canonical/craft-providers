#
# Copyright (C) 2020-2021 Canonical Ltd
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

"""Windows support for Multipass."""

import logging
import os
import os.path
import pathlib
import shutil
import subprocess
import sys
import tempfile

import requests

from craft_providers.util.path import calculate_file_hash

if sys.platform == "win32":
    import winreg  # pylint: disable=import-error
else:
    winreg = None  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)


_MULTIPASS_RELEASES_API_URL = (
    "https://api.github.com/repos/CanonicalLtd/multipass/releases/latest"
)
_MULTIPASS_DL_VERSION = "0.8.0"
_MULTIPASS_DL_NAME = "multipass-{version}+win-win64.exe".format(
    version=_MULTIPASS_DL_VERSION
)
_MULTIPASS_DL_SHA3_384 = "a1ac2eeb77b2a98fe5dee198be70dbf1a985d94b9707ce33ea0d3828dbc90d07fccb9662b7c97a3cfa194895b4f56676"


class MultipassWindowsInstallError(Exception):
    """Multipass Installation Error.

    :param reason: Reason for install failure.
    """

    def __init__(self, reason: str) -> None:
        super().__init__()

        self.reason = reason

    def __str__(self) -> str:
        return self.reason


def reload_multipass_path_env(winreg_module=winreg):
    """Update PATH to include installed Multipass, if not already set."""
    assert winreg_module

    key = winreg_module.OpenKey(winreg_module.HKEY_CURRENT_USER, "Environment")

    paths = os.environ["PATH"].split(";")

    # Drop empty placeholder for trailing comma, if present.
    if paths[-1] == "":
        del paths[-1]

    reg_user_path, _ = winreg_module.QueryValueEx(key, "Path")
    for path in reg_user_path.split(";"):
        if path not in paths and "Multipass" in path:
            paths.append(path)

    # Restore path with trailing comma.
    os.environ["PATH"] = ";".join(paths) + ";"


def _run_installer(installer: pathlib.Path):
    """Execute multipass installer."""
    logger.info("Installing Multipass...")

    # Multipass requires administrative privileges to install, which requires
    # the use of `runas` functionality. Some of the options included:
    # (1) https://stackoverflow.com/a/34216774
    # (2) ShellExecuteW and wait on installer by attempting to delete it.
    # Windows would prevent us from deleting installer with a PermissionError:
    # PermissionError: [WinError 32] The process cannot access the file because
    # it is being used by another process: <path>
    # (3) Use PowerShell's "Start-Process" with RunAs verb as shown below.
    # None of the options are quite ideal, but #3 will do.
    cmd = """
    & {{
        try {{
            $Output = Start-Process -FilePath {path!r} -Args /S -Verb RunAs -Wait -PassThru
        }} catch {{
            [Environment]::Exit(1)
        }}
      }}
    """.format(
        path=str(installer)
    )

    try:
        subprocess.check_call(["powershell.exe", "-Command", cmd])
    except subprocess.CalledProcessError as error:
        raise MultipassWindowsInstallError(
            reason="Failed to launch installer."
        ) from error

    # Reload path environment to see if we can find multipass now.
    reload_multipass_path_env()

    if not shutil.which("multipass.exe"):
        raise MultipassWindowsInstallError("installation did not complete successfully")

    logger.info("Multipass installation completed successfully.")


def _requests_exception_hint(error: requests.RequestException) -> str:
    # Use the __doc__ description to give the user a hint. It seems to be a
    # a decent option over trying to enumerate all of possible types.
    if error.__doc__:
        split_lines = error.__doc__.splitlines()
        if split_lines:
            return error.__doc__.splitlines()[0].strip()

    # Should never get here.
    return "unknown download error"


def _fetch_installer_url(
    url: str = _MULTIPASS_RELEASES_API_URL, asset_name: str = _MULTIPASS_DL_NAME
) -> str:
    """Fetch latest installer executable from github.

    If the latest release on github is newer than what snapcraft knows
    about in _MULTIPASS_DL_NAME_*, we skip the download and inform the
    user to go download it manually.  This way we will only ever directly
    execute whitelisted executables on behalf of the user.  Verify the
    installer using a SHA3-384 digest.
    """
    try:
        resp = requests.get(url)
    except requests.RequestException as error:
        hint = _requests_exception_hint(error)
        raise MultipassWindowsInstallError(
            reason=f"Failed to download Multipass installer from {url!r}: {hint}"
        ) from error

    try:
        data = resp.json()
    except ValueError as error:
        raise MultipassWindowsInstallError(
            reason=f"Failed to download valid release data from: {url}"
        ) from error

    # Find matching asset by name.
    for asset in data.get("assets", list()):
        if asset.get("name") != asset_name:
            continue

        url = asset.get("browser_download_url")
        if url is not None:
            return url

    raise MultipassWindowsInstallError(
        reason="Please install Multipass manually - see https://multipass.run/docs/installing-on-windows for more information."
    )


def _download_multipass(
    dl_dir: pathlib.Path, chunk_size: int = 32 * 1024
) -> pathlib.Path:
    """Create temporary dir to download installer."""
    dl_url = _fetch_installer_url()
    dl_basename = os.path.basename(dl_url)
    dl_path = dl_dir / dl_basename

    logger.info("Downloading Multipass installer from %s to %s...", dl_url, dl_path)

    try:
        request = requests.get(dl_url, stream=True, allow_redirects=True)
        with dl_path.open(mode="wb") as dst:
            for chunk in request.iter_content(chunk_size):
                dst.write(chunk)
    except requests.RequestException as error:
        hint = _requests_exception_hint(error)
        raise MultipassWindowsInstallError(
            reason=f"Failed to download Multipass installer from {dl_url!r}: {hint}"
        ) from error

    digest = calculate_file_hash(file_path=dl_path, algorithm="sha3_384")
    if digest != _MULTIPASS_DL_SHA3_384:
        raise MultipassWindowsInstallError(
            reason=f"Downad failed verification.  Expected hash {_MULTIPASS_DL_SHA3_384!r}, found {digest!r}."
        )

    logger.info("Verified installer successfully...")
    return dl_path


def install_multipass() -> None:
    """Download and install multipass."""
    assert sys.platform == "win32"

    dl_dir = pathlib.Path(tempfile.mkdtemp())
    dl_path = _download_multipass(dl_dir)
    _run_installer(dl_path)

    # Cleanup.
    shutil.rmtree(dl_dir)
