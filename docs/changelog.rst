*********
Changelog
*********

See the `Releases page`_ on Github for a complete list of commits that are
included in each version.

1.14.1 (2023-07-24)
-------------------
- Prevent race when two processes try to create the same project
  at the same time

1.14.0 (2023-06-28)
-------------------
- Update Lunar image for Multipass to stable image
- Install common packages and clean up package cache on bases
- Push files to any location in Multipass instances
- CI, linting, and testing overhaul
- Add diataxis front page for documentation
- Improve ``push_file_io`` for LXD instances
- Improve ``retry-until-timeout`` logic
- Refactor base classes
- Improve operability with Python 3.12

1.13.0 (2023-05-31)
-------------------
- Push files to any location in Multipass instances
- Refactor base setup and warmup
- Replace timeout for entire base setup with granular per-step timeouts
- Add option to not install default packages during base setup
- Install build-essentials and python3 in CentOS and AlmaLinux
- Update PATH for CentOS

1.12.0 (2023-05-18)
-------------------
- Add AlmaLinux 9 base
- Add stricter typing for base names
- Refactor CI workflow
- Refactor Multipass ``push_file_io``
- Pin dependency urllib3<2

1.11.0 (2023-04-19)
-------------------
- Move Snap pydantic model from ``bases.buildd`` to ``actions.snap_installer``
- Rename ``bases.buildd`` module to ``bases.ubuntu``
- Determine base alias from base configuration in
  ``provider.launched_environment()``
- Add new functions ``get_base_alias()`` and ``get_base_from_alias()``
- Add CentOS 7 base
- Add default for ``launched_environment()`` parameter ``allow_unstable=False``
- Trim suffixes from snap names when installing snaps.

1.10.0 (2023-03-31)
-------------------
- Add support for kinetic, lunar, and devel images with Multipass
- Remove unused import suppressions in init files
- Update github actions

1.9.0 (2023-03-20)
------------------
- Set cloud.cfg to not reset apt's source list for buildd bases
- Store LXD instance's full name in the config's description
- Add ``allow_unstable`` parameter to ``Provider.launched_environment()``

1.8.1 (2023-03-10)
------------------
- Add new base alias ``BuilddBaseAlias.DEVEL``
- Expire unstable base instances every 14 days
- Refactor tests such that all base aliases are tested by default

1.8.0 (2023-03-01)
------------------
- Track if instances are properly setup when launching. If the instance did not
  fully complete setup and auto-clean is enabled, the instance will be cleaned
  and recreated.
- Add new field ``setup`` to instance configuration to track set up status
- Update base compatibility tag from ``base-v0`` to ``base-v1``
- Add new BuilddBaseAliases for Lunar and Kinetic
- Add support for interim Ubuntu releases for LXD
- Add support for custom LXD image remotes. LXD remotes can now add any
  remote server to retrieve images from using the ``RemoteImage`` class.
- Add deprecation warning for LXD function ``configure_buildd_image_remote()``.
  Usage of this function should be replaced with RemoteImage's ``add_remote()``.
- Rename BuilddBase function ``setup_instance_config()`` to
  ``update_compatibility_tag()``
- Update brew for macos CI tests
- Update readthedocs link in readme
- Capture subproccess error details when snap removal fails
- Add default for ``_run_lxc()`` parameter ``check=True``
- Refactor lxd unit and integration tests
- Enable more pylint checks
- Use new ``use_base_instance`` parameter when launching LXD instances from
  LXDProvider

1.7.2 (2023-02-06)
------------------
- Check LXD id map before starting an existing instance.
  If the id map does not match, the instance will be auto cleaned
  or an error will be raised.
- Add ``lxc.config_get()`` method to retrieve config values

1.7.1 (2023-01-23)
------------------
- Set LXD id maps after launching or copying an instance
- Raise BaseConfigurationError for snap refresh failures

1.7.0 (2023-01-11)
------------------
- LXD instances launch from a cached base instance rather than a base image.
  This reduces disk usage and launch time.
- For the LXD launch function ``launched_environment``, the parameter
  ``use_snapshots`` has been replaced by ``use_base_instance``.
  ``use_snapshots`` still works but logs a deprecation notice.
- Expire and recreate base instances older than 3 months (90 days)
- Add ``lxc.copy()`` method to copy instances
- Check for network connectivity after network-related commands fail
- Add documentation for network connectivity issues inside instances
- Enable testing for Ubuntu 22.04 images
- Update ``MultipassInstance.push_file_io()`` to work regardless of the
  host's working directory

1.6.2 (2022-12-08)
------------------
- Disable automatic snap refreshes inside instances.

1.6.1 (2022-10-31)
------------------
- Store temporary files in the home directory
- Fix typos

1.6.0 (2022-10-06)
------------------
- Add is_running method to base Executor class
- Add new classes Provider, LXDProvider, and MultipassProvider

Note: The new Provider classes are used to encapsulate LXD and Multipass,
      from installing the provider to creating and managing instances. The code
      was leveraged from the craft applications (snapcraft, charmcraft,
      rockcraft, lpcraft), which implemented similar variations of these
      Provider classes. These classes are not stable and are likely to change.
      They will be stable and recommended for use in the release of
      craft-providers 2.0.

1.5.1 (2022-09-29)
------------------
- When injecting a snap, assert the snap's publisher's account
- Avoid race condition when multiple processes add a LXD remote at the same time

1.5.0 (2022-09-23)
------------------
- Add mount method to Executor base class
- LXDInstance's mount method signature has changed - The optional parameter
  ``device_name`` has been deprecated. It now matches MultipassInstance's
  signature of ``mount(host_source, target)``
- Signed snaps injected into a provider are asserted
- Existing .snap files are not removed before overwriting with a new .snap file

1.4.2 (2022-09-09)
------------------
- Set snapd http-proxy and https-proxy
- Pass on snapd no-CDN configuration

1.4.1 (2022-08-30)
------------------
- Fix bug in BuilddBase where hostnames longer than 64 characters may
  not having trailing hyphens removed.
- Allow overriding of compatibility tag in Bases

1.4.0 (2022-08-22)
------------------
- Use LXD-compatible instance names
- Add optional list of snaps to install in bases
- Add optional list of system packages to install in bases
- Add new temporarily_pull_file function to Executor base class
- Add exists and delete function to Executor base class
- Declare more instance paths as PurePath
- Ensure BuilddBase hostname is valid
- Move .pylintrc to pyproject.toml
- Enforce line-too-long
- Fix for unit tests on non-linux platforms

Note: The provided name for a LXD executor object is converted to comply with
      LXD naming conventions for instances. This may cause a compatibility issue
      for applications that assume the LXD instance name will be identical to
      the Executor name.

      If a provided name already complies with LXD naming conventions, it is
      not modified.

1.3.1 (2022-06-09)
------------------

- Add stdin parameter for LXC commands (default: null)

1.3.0 (2022-05-21)
------------------

- Refactor snap injection logic
- Always check multipass command execution results
- Update tests and documentation

1.2.0 (2022-04-07)
------------------

- Refactor instance configuration
- Disable automatic apt actions in instance setup
- Warm-start existing instances instead of rerunning full setup
- Don't reinstall snaps already installed on target

1.1.1 (2022-03-30)
------------------

- Fix LXD user permission verification

1.1.0 (2022-03-16)
------------------

- Add buildd base alias for Jammy

1.0.5 (2022-03-09)
------------------

- Fix uid mapping in lxd host mounts

1.0.4 (2022-03-02)
------------------

- Export public API names
- Declare instance paths as PurePath
- Address linter issues
- Update documentation

.. _Releases page: https://github.com/canonical/craft-providers/releases
