#!/usr/bin/env bash

# Updates sources to old-releases.ubuntu.com for Ubuntu releases that are past their EOL date.

set -e

for file in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources; do
  if [[ -f "$file" ]]; then
    echo "Updating '${file}'."
    sed -i \
       -e "s|security.ubuntu.com|old-releases.ubuntu.com|g" \
       -e "s|archive.ubuntu.com|old-releases.ubuntu.com|g" \
       -e "s|ports.ubuntu.com/ubuntu-ports|old-releases.ubuntu.com/ubuntu|g" \
       "${file}"
  else
    echo "'${file}' doesn't exist, skipping."
fi
done
