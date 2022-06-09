*********
Changelog
*********

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
