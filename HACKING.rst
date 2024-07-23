***************
Craft Providers
***************

Welcome to Craft Providers! We hope this document helps you get started. Before
contributing any code, please sign the `Canonical contributor licence
agreement`_.

Setting up a development environment
------------------------------------
We use a forking, feature-based workflow, so you should start by forking the
repository. Once you've done that, clone the project to your computer using git
clone's ``--recurse-submodules`` parameter. (See more on the `git submodules`_
documentation.)

Tooling
=======
We use a large number of tools for our project. Most of these are installed for
you with tox, but you'll need to install:

- Python 3.8 (default on Ubuntu 20.04, available on Ubuntu 22.04 through the
  deadsnakes_ PPA) with setuptools.
- tox_ version 4 or later. (3.8+ will automatically provision a v4 virtualenv)
- Pyright_ (it's recommended you install with
  ``snap install --classic pyright``)
- ShellCheck_  (also available via snap: ``snap install shellcheck``)
- pre-commit_
- ruff_ (also available via snap: ``snap install ruff``)

Once you have all of those installed, you can install the necessary virtual
environments for this repository using tox.

Other tools
###########
Some other tools we use for code quality include:

- Black_ for code formatting
- pytest_ for testing

A complete list is kept in our pyproject.toml_ file in dev dependencies.

Initial Setup
#############

After cloning the repository but before making any changes, it's worth ensuring
that the tests, linting and tools all run on your machine. Running ``tox`` with
no parameters will create the necessary virtual environments for linting and
testing and run those::

    tox

If you want to install the environments but not run the tests, you can run::

    tox --notest

If you'd like to run the tests with a newer version of Python, you can pass a
specific environment. You must have an appropriately versioned Python
interpreter installed. For example, to run with Python 3.10, run::

    tox -e test-py310

While the use of pre-commit_ is optional, it is highly encouraged, as it runs
automatic fixes for files when ``git commit`` is called, including code
formatting with ``black`` and ``ruff``.  The versions available in ``apt``
from Debian 11 (bullseye), Ubuntu 22.04 (jammy) and newer are sufficient, but
you can also install the latest with ``pip install pre-commit``. Once you've
installed it, run ``pre-commit install`` in this git repository to install the
pre-commit hooks.

Tox environments and labels
###########################

We group tox environments with the following labels:

* ``format``: Runs all code formatters with auto-fixing
* ``type``: Runs all type checkers
* ``lint``: Runs all linters (including type checkers)
* ``unit-tests``: Runs unit tests in Python versions on supported LTS's + latest
* ``integration-tests``: Same as above but for integration tests
* ``tests``: The union of ``unit-tests`` and ``integration-tests``

For each of these, you can see which environments will be run with
``tox list``. For example:

    tox list -m lint

You can also see all the environments by simply running ``tox list``

Running ``tox run -m format`` and ``tox run -m lint`` before committing code is
recommended.

GitHub Actions
##############

GitHub Actions is used for CI/CD. There are workflows for building
documentation, linting, releasing, and running unit and integration tests.
The workflows run on Linux, MacOS, and Windows. You can get ssh access
into a runner using action-tmate_. To get ssh access:

#. Go to Actions_
#. Choose the test suite (e.g. ``tests``)
#. Choose a branch
#. Press ``Run workflow`` and select ``Enable ssh access`` in the dropdown
#. Open the workflow's logs and use the ssh address provided by ``action-tmate``

`SSH access is limited`_ to the GitHub user who started the test suite, so you
need to add your public `SSH key on GitHub`_.

Contributing code
#################

Please follow these guidelines when committing code for this project:

* Use a topic with a colon to start the subject
* Separate subject from body with a blank line
* Limit the subject line to 50 characters
* Do not capitalize the subject line
* Do not end the subject line with a period
* Use the imperative mood in the subject line
* Wrap the body at 72 characters
* Use the body to explain what and why (instead of how)

.. _Actions: https://github.com/canonical/craft-providers/actions
.. _action-tmate: https://mxschmitt.github.io/action-tmate/
.. _Black: https://black.readthedocs.io
.. _`Canonical contributor licence agreement`: http://www.ubuntu.com/legal/contributors/
.. _deadsnakes: https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa
.. _`git submodules`: https://git-scm.com/book/en/v2/Git-Tools-Submodules#_cloning_submodules
.. _pre-commit: https://pre-commit.com/
.. _pyproject.toml: ./pyproject.toml
.. _Pyright: https://github.com/microsoft/pyright
.. _pytest: https://pytest.org
.. _ruff: https://github.com/astral-sh/ruff
.. _ShellCheck: https://www.shellcheck.net/
.. _`SSH access is limited`: https://github.com/marketplace/actions/debugging-with-tmate#use-registered-public-ssh-keys
.. _`SSH key on GitHub`: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account
.. _tox: https://tox.wiki
