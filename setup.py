#!/usr/bin/env python3
#
# Copyright 2021-2022 Canonical Ltd.
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


"""The setup script."""

from setuptools import find_packages, setup  # type: ignore

with open("README.md") as readme_file:
    readme = readme_file.read()

install_requires = [
    "pydantic",
    "pyyaml",
    "requests_unixsocket",
]

dev_requires = [
    "autoflake",
    "twine",
]

doc_requires = [
    "sphinx",
    "sphinx-autodoc-typehints",
    "sphinx-pydantic",
    "sphinx-rtd-theme",
]

test_requires = [
    "coverage",
    "black",
    "codespell",
    "flake8",
    "isort",
    "mypy",
    "logassert",
    "pydocstyle",
    "pylint",
    "pylint-fixme-info",
    "pylint-pytest",
    "pytest",
    "pytest-mock",
    "pytest-subprocess",
    "responses",
    "types-requests",
    "types-setuptools",
    "types-pyyaml",
]

extras_requires = {
    "dev": dev_requires + test_requires,
    "doc": doc_requires,
    "test": test_requires,
}

setup(
    name="craft-providers",
    version="1.4.0",
    description="Craft provider tooling",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Canonical Ltd.",
    author_email="snapcraft@lists.snapcraft.io",
    url="https://github.com/canonical/craft-providers",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    license="GNU Lesser General Public License v3 (LGPLv3)",
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
