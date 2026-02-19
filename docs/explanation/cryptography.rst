.. _explanation_cryptographic-technology:

Cryptographic technology in Craft Providers
===========================================

Craft Providers uses cryptographic technologies to communicate with processes
running on the host system. It does not directly implement its own
cryptography, but it does depend on external libraries to do so.

Communication with local processes
----------------------------------

Craft Providers uses the `Requests
<https://requests.readthedocs.io/en/latest/>`_ library to communicate over Unix
sockets with the local `snap daemon (snapd)
<https://snapcraft.io/docs/installing-snapd>`_. These requests are used to
fetch information about required software. If the software is missing, Craft
Providers will install it through snapd. This is done by querying the `snapd
API <https://snapcraft.io/docs/snapd-api>`_ with URLs built dynamically and
sanitized by `urllib <https://docs.python.org/3/library/urllib.html>`_.
