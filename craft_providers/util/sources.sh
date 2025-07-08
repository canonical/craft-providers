#! /bin/bash

# Updates sources to old-releases.ubuntu.com for Ubuntu releases that are past their EOL date.

set -e


launchpad_info="https://git.launchpad.net/ubuntu/+source/distro-info-data/plain/ubuntu.csv"
system_info="/usr/share/distro-info/ubuntu.csv"
craft_info="/tmp/craft-ubuntu.csv"
os_release="/etc/os-release"


# Creates /tmp/craft-ubuntu.csv from the distro-info package or from launchpad
function get_distro_info(){
  # prefer ubuntu.csv from the distro-info package
  if [[ -f "$system_info" ]]; then
    echo "Getting EOL info from $system_info."
    ln --symbolic --force "$system_info" "$craft_info"
    return 0
  fi

  # if not available, retrieve it from launchpad
  echo "Getting EOL info from $launchpad_info"
  retry curl "$launchpad_info" --output "$craft_info"
}


# check if a release is past it's EOL date
function is_eol(){
  eol=$(grep -e ",$codename," "$craft_info" | awk -F ',' '{print $NF}')

  if [[ -z "$eol" ]]; then
    echo "Couldn't find distro info for $codename."
    exit 1
  fi

  echo "EOL date for $codename is $eol."

  if [[ $(date --iso-8601) > "${eol}" ]]; then
    echo "$codename is EOL."
    return 0
  else
    echo "$codename isn't EOL."
    return 1
  fi
}


# check if a release is available on old-releases.ubuntu.com
function is_on_old_releases(){
  if curl -I "https://old-releases.ubuntu.com/ubuntu/dists/$codename/" | grep -q 200; then
    echo "$codename is available on old-releases.ubuntu.com."
    return 0
  else
    echo "$codename isn't available on old-releases.ubuntu.com."
    return 1
  fi
}


# update existing source entries
function replace_sources(){
  echo "Updating EOL sources."
  for file in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources; do
    echo "Updating '${file}'."
    sed -i -e "s/security.ubuntu.com/old-releases.ubuntu.com/" -e "s/archive.ubuntu.com/old-releases.ubuntu.com/" "${file}"
  done
}


# retry a failing command 5 times, with a 15 second delay between attempts
function retry() {
  local max_attempts=5
  local delay=15
  local attempt=1

  while true; do
    # shellcheck disable=SC2015
    "$@" && break || {
      if (( attempt == max_attempts )); then
        echo "Command failed after $max_attempts attempts." >&2
        return 1
      else
        echo "Command failed (attempt $attempt/$max_attempts) Retrying in $delay seconds..." >&2
        sleep $delay
        ((attempt++))
      fi
    }
  done
}


codename=$(grep ^VERSION_CODENAME= $os_release | cut -d= -f2)
get_distro_info

if is_eol && is_on_old_releases; then
  replace_sources
fi
