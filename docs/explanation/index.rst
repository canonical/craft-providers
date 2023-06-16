.. _explanation:

Explanation
***********

.. toctree::
   :maxdepth: 1

Failure to properly execute commands that depend on network access
==================================================================

A common problem that can occur when running the setup or warmup of an instance
is a failure associated with different processes (e.g. ``apt``) not being able
to access the network properly.

While this can happen because of a myriad of situations (network outage in the
host, a malfunctioning proxy, etc), there is a very common case where Docker
changes the ``iptables`` of the host in a particular way that conflicts with LXD
instances.

If you're getting network errors in an LXD instance and have Docker installed,
please refer to `this section`_ in the Linux Containers documentation for more
information and ways to solve the situation.

.. _`this section`: https://linuxcontainers.org/lxd/docs/master/howto/network_bridge_firewalld/#prevent-connectivity-issues-with-lxd-and-docker
