#
# Copyright 2021-2023 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import datetime

project = "Craft Providers"
author = "Canonical Group Ltd"

copyright = "2021-%s, %s" % (datetime.date.today().year, author)

# region Configuration for canonical-sphinx
ogp_site_url = "https://canonical-craft-providers.readthedocs-hosted.com/"
ogp_site_name = project
ogp_image = "https://assets.ubuntu.com/v1/253da317-image-document-ubuntudocs.svg"

html_context = {
    "product_page": "github.com/canonical/craft-providers",
    "github_url": "https://github.com/canonical/craft-providers",
}

extensions = [
    "canonical_sphinx",
    "sphinxext.rediraffe",
]
# end-region

# Ignore the venv created by the linting Makefile
exclude_patterns = [
    "venv",

    # These axes were empty, so hide their scaffolding for now
    "tutorials",
]

# Links to ignore when checking links
linkcheck_ignore = [
    # GNU's site is a bit unreliable
    "https://www.gnu.org/.*",
    # https://github.com/rust-lang/crates.io/issues/788
    "https://crates.io/",
    # Ignore releases, since we'll include the next release before it exists.
    "https://github.com/canonical/[a-z]*craft[a-z-]*/releases/.*",
    # returns a 403 from GitHub CI
    "https://rsync.samba.org",
]


extensions.extend(
    [
        "sphinx.ext.autodoc",
    ]
)

# Client-side page redirects.
rediraffe_redirects = "redirects.txt"
