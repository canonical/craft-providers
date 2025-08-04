# Craft providers

![Documentation Status](https://readthedocs.com/projects/canonical-craft-providers/badge/?version=latest)
![weekly-test-status-badge](https://github.com/canonical/craft-providers/actions/workflows/tests-weekly.yaml/badge.svg?branch=main)
![code-coverage-badge](https://codecov.io/gh/canonical/craft-providers/graph/badge.svg?token=CTEPNPXrn5)

[![Documentation Status][rtd-badge]][rtd-latest]
[![Codecov Status][codecov-badge]][codecov-status]
[![Ruff status][ruff-badge]][ruff-site]

This project provides Python interfaces for instantiating and executing
builds for a variety of target environments.

Initial providers include:

- [LXD containers](https://ubuntu.com/lxd/)
- [Multipass VMs](https://multipass.run/)

Host support is targeted for:

- Linux
- Mac OS X
- Windows

## Documentation

The [Craft Providers documentation][rtd-latest] provides guidance about understanding
and using the library.

## Community and support

You can report any issues or bugs on the project's [GitHub
repository](https://github.com/canonical/craft-providers/issues).

Craft Providers is covered by the [Ubuntu Code of
Conduct](https://ubuntu.com/community/ethos/code-of-conduct).

## Contribute to Craft Providers

Craft Providers is open source and part of the Canonical family. We would love your
help.

If you're interested, start with the [contribution guide](CONTRIBUTING.md).

We welcome any suggestions and help with the docs. The [Canonical Open Documentation
Academy](https://github.com/canonical/open-documentation-academy) is the hub for doc
development, including Craft Providers docs. No prior coding experience is required.

## License and Copyright

Craft Providers is licensed under the [LGPL-3.0 license](LICENSE).

[rtd-badge]: https://readthedocs.com/projects/canonical-craft-providers/badge/?version=latest
[rtd-latest]: https://canonical-craft-providers.readthedocs-hosted.com/en/latest/
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-site]: https://github.com/astral-sh/ruff
[codecov-badge]: https://codecov.io/github/canonical/craft-providers/coverage.svg?branch=master
[codecov-status]: https://codecov.io/github/canonical/craft-providers?branch=master
