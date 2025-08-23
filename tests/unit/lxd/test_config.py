# Copyright 2025 Canonical Ltd.
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
"""Unit tests for LXC configuration."""

import pathlib
import shutil

<<<<<<< Updated upstream
from pyfakefs.fake_filesystem import FakeFilesystem
import pytest
import yaml
from craft_providers.lxd import config
=======
import pytest
import yaml
from craft_providers.lxd import config
from pyfakefs.fake_filesystem import FakeFilesystem
>>>>>>> Stashed changes

SAMPLE_CONFIGS = [
    pytest.param(path / "config.yml", id=path.name)
    for path in (pathlib.Path(__file__).parent / "sample_configs").iterdir()
]


@pytest.mark.parametrize("path", SAMPLE_CONFIGS)
def test_load_config_success(path: pathlib.Path):
    raw_yaml = yaml.safe_load(path.read_text())
    c = config.UserConfig.load(path)

    assert c.model_dump(mode="json", by_alias=True) == raw_yaml


<<<<<<< Updated upstream

@pytest.mark.parametrize("orig_path", SAMPLE_CONFIGS)
@pytest.mark.parametrize("fake_path", [config.SNAP_CONFIG, config.APT_CONFIG])
def test_load_default_config(fs: FakeFilesystem, orig_path: pathlib.Path, fake_path: pathlib.Path):
=======
@pytest.mark.parametrize("orig_path", SAMPLE_CONFIGS)
@pytest.mark.parametrize("fake_path", [config.SNAP_CONFIG, config.APT_CONFIG])
def test_load_default_config(
    fs: FakeFilesystem, orig_path: pathlib.Path, fake_path: pathlib.Path
):
>>>>>>> Stashed changes
    fs.add_real_file(source_path=orig_path, target_path=fake_path)

    raw_yaml = yaml.safe_load(fake_path.read_text())
    c = config.UserConfig.load()

    assert c.model_dump(mode="json", by_alias=True) == raw_yaml


@pytest.mark.parametrize("orig_path", SAMPLE_CONFIGS)
def test_save_config_success(tmp_path: pathlib.Path, orig_path: pathlib.Path):
    path = tmp_path / "config.yml"
    shutil.copy(orig_path, path)

    c = config.UserConfig.load(path)
    c.save()

    # Comments have been removed.
    assert path.read_text() != orig_path.read_text()

    c2 = config.UserConfig.load(path)
    assert c == c2
