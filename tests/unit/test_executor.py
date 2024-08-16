#
# Copyright 2022 Canonical Ltd.
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

import contextlib
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def fake_executor_local_pull(fake_executor):
    """Provide an executor that copies the file locally on 'pull'."""

    def copy_file(source, destination):
        shutil.copy(source, destination)

    fake_executor.pull_file = copy_file
    return fake_executor


@pytest.fixture
def mock_home_temp_file(mocker, tmp_path):
    """Mock `home_temporary_file()`."""

    @contextlib.contextmanager
    def _mock_home_temp_file():
        tmp_file = Path(tmp_path / "fake-temp-file.txt")
        try:
            yield tmp_file
        finally:
            tmp_file.unlink()

    return mocker.patch(
        "craft_providers.util.temp_paths.home_temporary_file",
        wraps=_mock_home_temp_file,
    )


def test_temporarypull_ok(
    mock_home_temp_file, mocker, tmp_path, fake_executor_local_pull
):
    """Successful case."""
    source = tmp_path / "source.txt"
    source.write_text("test content")

    with fake_executor_local_pull.temporarily_pull_file(source=source) as localfilepath:
        # content copied and accessible
        assert localfilepath.read_text() == "test content"

    # file is removed afterwards
    assert not localfilepath.exists()

    # temp_paths.home_temporary_file() is used for the local file
    mock_home_temp_file.assert_called_once()


def test_temporarypull_missing_file_error(tmp_path, fake_executor_local_pull):
    """The source is missing, by default it's an error."""
    source = tmp_path / "source.txt"  # note we're not creating it in disk

    with pytest.raises(FileNotFoundError):
        with fake_executor_local_pull.temporarily_pull_file(source=source):
            pass


def test_temporarypull_missing_file_ok(tmp_path, fake_executor_local_pull):
    """The source is missing, but it's ok."""
    source = tmp_path / "source.txt"  # note we're not creating it in disk

    with fake_executor_local_pull.temporarily_pull_file(
        source=source, missing_ok=True
    ) as localfilepath:
        assert localfilepath is None


def test_temporarypull_temp_file_cleaned(
    mock_home_temp_file, tmp_path, fake_executor_local_pull
):
    """The temp file is cleaned after usage."""
    source = tmp_path / "source.txt"
    source.write_text("test content")

    with pytest.raises(ValueError), fake_executor_local_pull.temporarily_pull_file(
        source=source
    ) as localfilepath:
        # internal crash
        raise ValueError("boom")

    # file is removed afterwards
    assert not localfilepath.exists()  # pyright: ignore [reportUnboundVariable]
