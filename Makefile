PROJECT=craft_providers
# Define when more than the main package tree requires coverage
# like is the case for snapcraft (snapcraft and snapcraft_legacy):
# COVERAGE_SOURCE="starcraft"
UV_TEST_GROUPS := "--group=dev"
UV_DOCS_GROUPS := "--group=docs"
UV_LINT_GROUPS := "--group=lint" "--group=types"
UV_TICS_GROUPS := "--group=tics"

# If you have dev dependencies that depend on your distro version, uncomment these:
# ifneq ($(wildcard /etc/os-release),)
# include /etc/os-release
# endif
# ifdef VERSION_CODENAME
# UV_TEST_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# UV_DOCS_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# UV_LINT_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# UV_TICS_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# endif

include common.mk

.PHONY: format
format: format-ruff format-codespell format-prettier  ## Run all automatic formatters

.PHONY: lint
lint: lint-ruff lint-codespell lint-mypy lint-prettier lint-pyright lint-shellcheck lint-docs lint-twine  ## Run all linters

.PHONY: pack
pack: pack-pip  ## Build all packages

.PHONY: pack-snap
pack-snap: snap/snapcraft.yaml  ##- Build snap package
ifeq ($(shell which snapcraft),)
	sudo snap install --classic snapcraft
endif
	snapcraft pack

# Find dependencies that need installing
APT_PACKAGES :=
ifeq ($(wildcard /usr/include/libxml2/libxml/xpath.h),)
APT_PACKAGES += libxml2-dev
endif
ifeq ($(wildcard /usr/include/libxslt/xslt.h),)
APT_PACKAGES += libxslt1-dev
endif
ifeq ($(wildcard /usr/share/doc/python3-venv/copyright),)
APT_PACKAGES += python3-venv
endif

# Used for installing build dependencies in CI.
.PHONY: install-build-deps
install-build-deps: install-lint-build-deps
ifeq ($(APT_PACKAGES),)
else ifeq ($(shell which apt-get),)
	$(warning Cannot install build dependencies without apt.)
	$(warning Please ensure the equivalents to these packages are installed: $(APT_PACKAGES))
else
	sudo $(APT) install $(APT_PACKAGES)
endif
ifeq ($(CI)_$(OS),1_Linux)  # Stuff to do specifically on Linux CI runners.
	# In CI, delete the android SDK if it's installed. It's kinda huge!
	echo "::group::Clean up disk"
	sudo rm -rf /usr/local/lib/android/
	# Likewise, configure LXD in CI
	echo "::group::Configure LXD"
	sudo groupadd --force --system lxd
	sudo usermod --append --groups lxd $USER
	sudo snap install lxd --channel=latest/candidate
	sudo snap start lxd
	sudo lxd waitready --timeout=30
	sudo lxd init --auto
	# iptables calls from https://github.com/canonical/setup-lxd/blob/main/action.yml
	sudo iptables -I DOCKER-USER -i lxdbr0 -j ACCEPT
	sudo iptables -I DOCKER-USER -o lxdbr0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
	echo "::endgroup::"
endif


# If additional build dependencies need installing in order to build the linting env.
.PHONY: install-lint-build-deps
install-lint-build-deps:
