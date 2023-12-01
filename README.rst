***************
Craft providers
***************

|doc-build-status-badge|_ |weekly-test-status-badge|_ |code-coverage-badge|_

Description
-----------
This project provides Python interfaces for instantiating and executing
builds for a variety of target environments.

Initial providers include:

- `LXD containers`_
- `Multipass VMs`_

Host support is targeted for:

- Linux
- Mac OS X
- Windows

License
-------
Free software: GNU Lesser General Public License v3

Documentation
--------------
https://canonical-craft-providers.readthedocs-hosted.com/en/latest/

Contributing
------------
See the HACKING.rst document for details on how to contribute.

.. _`LXD containers`: https://ubuntu.com/lxd/
.. _`Multipass VMs`: https://multipass.run/
.. |doc-build-status-badge| image:: https://readthedocs.com/projects/canonical-craft-providers/badge/?version=latest
.. _doc-build-status-badge: https://canonical-craft-providers.readthedocs-hosted.com/en/latest/?badge=latest
.. |weekly-test-status-badge| image:: https://github.com/canonical/craft-providers/actions/workflows/tests-weekly.yaml/badge.svg?branch=main
.. _weekly-test-status-badge: https://github.com/canonical/craft-providers/actions/workflows/tests-weekly.yaml
.. |code-coverage-badge| image:: https://codecov.io/gh/canonical/craft-providers/graph/badge.svg?token=CTEPNPXrn5
.. _code-coverage-badge: https://codecov.io/gh/canonical/craft-providers
