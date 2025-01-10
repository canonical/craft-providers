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
import hashlib
import re
import shutil
from pathlib import Path

import pytest
from craft_providers.errors import ProviderError
from craft_providers.executor import get_instance_name


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


@pytest.mark.parametrize(
    "name",
    [
        "t",
        "test",
        "test1",
        "test-1",
        "this-is-40-characters-xxxxxxxxxxxxxxxxxx",
        "this-is-63-characters-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ],
)
def test_set_instance_name_unchanged(logs, name):
    """Verify names that are already compliant are not changed."""
    instance_name = get_instance_name(name, ProviderError)

    assert instance_name == name
    assert re.escape(f"Converted name {name!r} to instance name {name!r}") in logs.debug


@pytest.mark.parametrize(
    ("name", "expected_name"),
    [
        # trim away invalid beginning characters
        ("1test", "test"),
        ("123test", "test"),
        ("-test", "test"),
        ("1-2-3-test", "test"),
        # trim away invalid ending characters
        ("test-", "test"),
        ("test--", "test"),
        ("test1-", "test1"),
        # trim away invalid characters
        ("test$", "test"),
        ("test-!@#$%^&*()test", "test-test"),
        ("$1test", "test"),
        ("test-$", "test"),
        ("test-𝔣𝔯𝔞𝔨𝔱𝔲𝔯'𝔡 𝔭𝔩𝔞𝔱𝔣𝔬𝔯𝔪", "test"),  # noqa: RUF001 (ambiguous-unicode)
        # this name contains invalid characters so it gets converted, even
        # though it is 63 characters
        (
            "this-is-63-characters-with-invalid-characters-$$$xxxxxxxxxxxxxX",
            "this-is-63-characters-with-invalid-chara",
        ),
        # this name is longer than 63 characters, so it gets converted
        (
            "this-is-70-characters-and-valid-xxxxxxxXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "this-is-70-characters-and-valid-xxxxxxxX",
        ),
    ],
)
def test_set_instance_name(logs, name, expected_name):
    """Verify name is compliant with naming conventions."""
    # compute hash
    hashed_name = hashlib.sha1(name.encode()).hexdigest()[:20]

    instance_name = get_instance_name(name, ProviderError)

    assert instance_name == f"{expected_name}-{hashed_name}"
    assert len(instance_name) <= 63
    assert (
        re.escape(f"Converted name {name!r} to instance name {instance_name!r}")
        in logs.debug
    )


def test_set_instance_name_hash_value():
    """Verify hash is formatted as expected.

    The first 20 characters of the SHA-1 hash of
    "hello-world$" is 'b993dc52118c0f489570'

    The name "hello-world$" should be hashed, not the trimmed name "hello-world".
    """
    instance_name = get_instance_name("hello-world$", ProviderError)

    assert instance_name == "hello-world-b993dc52118c0f489570"
    assert len(instance_name) <= 63


@pytest.mark.parametrize(
    "name",
    [
        "",
        "-",
        "$$$",
        "-$-$-",
        "𝔣𝔯𝔞𝔨𝔱𝔲𝔯'𝔡 𝔭𝔩𝔞𝔱𝔣𝔬𝔯𝔪",  # noqa: RUF001 (ambiguous-unicode)
    ],
)
def test_set_instance_name_invalid(name):
    """Verify invalid names raise an error."""
    with pytest.raises(ProviderError) as error:
        get_instance_name(name, ProviderError)

    assert error.value == ProviderError(
        brief=f"failed to create an instance with name {name!r}.",
        details="name must contain at least one alphanumeric character",
    )
