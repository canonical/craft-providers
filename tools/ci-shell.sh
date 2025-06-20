#!/bin/bash
# A fake shell for running tests in CI.
# This runs the shell in a new session, which means we can use the fact that
# we've entered the lxd group while installing build deps.
# See: https://github.com/actions/runner-images/issues/9932#issuecomment-2573170305
# Changing group as a non-root user in Github CI still asks for a password, so
# we hack around this by running the inner sudo as root.

# Remove "@" from the beginning of any internal lines since make doesn't think
# this script is a POSIX-style shell.
# https://www.gnu.org/software/make/manual/html_node/One-Shell.html
shell_cmd[0]="${SHELL}"
for i in "${@}"; do
shell_cmd+=("${i//
@/
}")
done

sudo --preserve-env --preserve-env=PATH -- \
  sudo --preserve-env --preserve-env=PATH --user "${USER}" --group lxd -- env -- \
    "${shell_cmd[@]}"
