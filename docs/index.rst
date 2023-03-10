Welcome to Craft Providers' documentation!
===========================================

Craft Providers is a Python package for managing software builds in containers
on behalf of tools using the Craft Parts framework.

Craft Providers aims to provide Python interfaces for instantiating build
environments, configuring base images and executing builds for a variety of
target environments.

The aim of this package is to provide a uniform, extensible set of interfaces
that other tools and packages can use to build software without needing to
know the particular details of each build environment or system.

This package is most useful for implementers of tools using the Craft Parts
framework that need to provide support for additional build environments.

.. toctree::
   :caption: Public APIs:

   executors

   bases

.. toctree::
   :caption: Internal APIs:

.. toctree::
   :caption: Reference:

   craft_providers

.. toctree:: 
   :caption: Explanations:
    
   explanations


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
