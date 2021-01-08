#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup  # type: ignore

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("HISTORY.md") as history_file:
    history = history_file.read()

requirements = [
    "pyyaml",
]

setup_requirements = [
    "pytest-runner",
]

test_requirements = [
    "pytest>=3",
]

setup(
    author="Canonical Ltd",
    author_email="Canonical Ltd",
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
    ],
    description="Craft provider tooling",
    entry_points={
        "console_scripts": [
            "craft_providers=craft_providers.cli:main",
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="craft_providers",
    name="craft-providers",
    package_data={"craft_providers": ["py.typed"]},
    packages=find_packages(include=["craft_providers", "craft_providers.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/cjp256/craft_providers",
    version="0.0.3",
    zip_safe=False,
)
