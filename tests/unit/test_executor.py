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

import shutil

import pytest


@pytest.fixture
def fake_executor_local_pull(fake_executor):
    """Provide an executor that copies the file locally on 'pull'."""

    def copy_file(source, destination):
        shutil.copy(source, destination)

    fake_executor.pull_file = copy_file
    return fake_executor


def test_pullfiletemp_ok(monkeypatch, tmp_path, fake_executor_local_pull):
    """Successful case."""
    # change dir so the temp file is created in a temp dir
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "source.txt"
    source.write_text("test content")

    with fake_executor_local_pull.pull_file_as_temp(source=source) as localfilepath:
        # temp file located "here" and with proper naming
        assert localfilepath.parent == tmp_path
        assert localfilepath.name.startswith("craft-providers-")
        assert localfilepath.name.endswith(".temp")

        # content copied and accessible
        assert localfilepath.read_text() == "test content"

    # file is removed afterwards
    assert not localfilepath.exists()


def test_pullfiletemp_missing_file_error(
    monkeypatch, tmp_path, fake_executor_local_pull
):
    """The source is missing, by default it's an error."""
    source = tmp_path / "source.txt"  # note we're not creating it in disk

    with pytest.raises(FileNotFoundError):
        with fake_executor_local_pull.pull_file_as_temp(source=source):
            pass


def test_pullfiletemp_missing_file_ok(monkeypatch, tmp_path, fake_executor_local_pull):
    """The source is missing, but it's ok."""
    # change dir so the temp file is created in a temp dir
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "source.txt"  # note we're not creating it in disk

    with fake_executor_local_pull.pull_file_as_temp(
        source=source, missing_ok=True
    ) as localfilepath:
        assert localfilepath is None


def test_pullfiletemp_temp_file_cleaned(
    monkeypatch, tmp_path, fake_executor_local_pull
):
    """The temp file is cleaned after usage."""
    # change dir so the temp file is created in a temp dir
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "source.txt"
    source.write_text("test content")

    with pytest.raises(ValueError):
        with fake_executor_local_pull.pull_file_as_temp(source=source) as localfilepath:
            # internal crash
            raise ValueError("boom")

    # file is removed afterwards
    assert not localfilepath.exists()  # pyright: ignore [reportUnboundVariable]
