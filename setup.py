#!/usr/bin/env python3
#
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


"""The setup script."""

from setuptools import find_packages, setup  # type: ignore

with open("README.md") as readme_file:
    readme = readme_file.read()

install_requires = [
    "pyyaml",
]

dev_requires = [
    "autoflake",
    "twine",
]

doc_requires = [
    "sphinx",
    "sphinx-autodoc-typehints",
    "sphinx-rtd-theme",
]

test_requires = [
    "coverage",
    "black",
    "codespell",
    "flake8",
    "isort",
    "mypy",
    "pydocstyle",
    "pylint",
    "pytest",
    "pytest-subprocess",
    "tox",
]

extras_requires = {
    "dev": dev_requires + doc_requires + test_requires,
    "doc": doc_requires,
    "test": test_requires,
}

setup(
    name="craft-providers",
    version="0.0.0",
    description="Craft provider tooling",
    long_description=readme,
    author="Canonical Ltd.",
    author_email="Canonical Ltd.",
    url="https://github.com/canonical/craft-providers",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    license="GNU General Public License v3",
    python_requires=">=3.8",
    packages=find_packages(include=["craft_providers", "craft_providers.*"]),
    entry_points={
        "console_scripts": [
            "craft_providers=craft_providers.cli:main",
        ],
    },
    install_requires=install_requires,
    extras_require=extras_requires,
    package_data={"craft_providers": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
)
