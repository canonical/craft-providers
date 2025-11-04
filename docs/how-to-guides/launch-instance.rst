.. _how-to-launch:

Launch a VM or container
========================

In order to launch a virtual machine or container with Craft Providers, you must know:

1. Which provider to use.
2. What distribution and series name you want to launch.

The provider is an instance of any :py:class:`~craft_providers.provider.Provider`
subclass. Craft Providers provides
:py:class:`~craft_providers.lxd.lxd_provider.LXDProvider` and
:py:class:`~craft_providers.multipass.multipass_provider.MultipassProvider` classes
for this purpose.

.. code-block:: python

    from craft_providers.lxd.lxd_provider import LXDProvider

    provider = LXDProvider(project="my-project")

Each Provider class has a
:py:class:`~craft_providers.provider.Provider.launched_environment` context manager,
which provides an :py:class:`~craft_providers.executor.Executor` instance. It is
just a matter of passing some project details and the base to this provider. The
:py:func:`~craft_providers.get_base` function provides a convenient way to get a base
object from its distribution name and series.

.. code-block:: python

    import pathlib
    import craft_providers

    base = craft_providers.get_base(distribution="ubuntu", series="24.04")

    with provider.launched_environment(
        project_name="my-project",
        project_path=pathlib.Path(),
        base_configuration=base,
        instance_name="my-instance",
    ) as executor:
        instance_info = executor.execute_run(
            ["cat", "/etc/os-release"],
            capture_output=True,
            text=True,
        ).stdout

When the context of a launched environment is exited, Craft Providers will shut down
the provider according to the value of the ``shutdown_delay_mins`` parameter.
If no shutdown delay is specified, the provider will be shut down while exiting the
context manager.
