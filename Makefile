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

ROOT_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
ifeq ($(CI)_$(OS),true_Linux)
SHELL:=$(ROOT_DIR)tools/ci-shell.sh
endif

.PHONY: format
format: format-ruff format-codespell format-prettier  ## Run all automatic formatters

.PHONY: lint
lint: lint-ruff lint-ty lint-codespell lint-mypy lint-prettier lint-pyright lint-shellcheck lint-docs lint-twine  ## Run all linters

.PHONY: pack
pack: pack-pip  ## Build all packages

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
install-build-deps: install-lint-build-deps free-disk-space
ifeq ($(APT_PACKAGES),)
else ifeq ($(shell which apt-get),)
	$(warning Cannot install build dependencies without apt.)
	$(warning Please ensure the equivalents to these packages are installed: $(APT_PACKAGES))
else
	sudo $(APT) install $(APT_PACKAGES)
endif
ifeq ($(CI)_$(OS),true_Linux)  # Only do this in CI on Linux
	# Likewise, configure LXD in CI
	echo "::group::Configure LXD"
	sudo groupadd --force --system lxd
	sudo usermod --append --groups lxd $(USER)
	echo "::endgroup::"
	# Install multipass in CI
	echo "::group::Configure Multipass"
	sudo snap install multipass
	sudo groupadd --force --system kvm
	sudo usermod --append --groups kvm,adm $(USER)
	echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules
	sudo udevadm control --reload-rules
	sudo udevadm trigger
	# Wait for the socket to appear and make it accessible
	for i in $$(seq 1 30); do [ -S /var/snap/multipass/common/multipass_socket ] && break || sleep 1; done
	sudo chmod 666 /var/snap/multipass/common/multipass_socket || true
	echo "::endgroup::"
else ifeq ($(CI)_$(OS),true_Darwin)  # Only do this in CI on macOS
	brew install multipass
	multipass set local.driver=qemu
	(brew cleanup --prune=all > /dev/null 2>&1 &)
	# Disable spotlight because it tries to index the multipass images, crashing
	# macOS 14+ runners. Thapple.
	sudo mdutil -a -i off
endif

.PHONY: free-disk-space
free-disk-space:  ##- Free up disk space in CI
ifeq ($(CI),true)
	# This target is only ever intended to run in CI, and is a no-op otherwise.
	@echo "::group::Free disk space"
	@df -h
ifeq ($(OS),Linux)
	sudo rm -rf /usr/local/lib/android/
endif
ifeq ($(OS),Darwin)
	sudo rm -rf /usr/local/lib/android
	sudo rm -rf /usr/local/share/dotnet
	CURRENT_XCODE=$$(xcode-select -p | sed 's|/Contents/Developer||') && \
	echo "Keeping $$CURRENT_XCODE, removing others..." && \
	sudo find /Applications -name "Xcode_*.app" -maxdepth 1 -not -path "*$$CURRENT_XCODE*" -exec rm -rf {} +
endif
	@df -h
	@echo "::endgroup::"
endif

# If additional build dependencies need installing in order to build the linting env.
.PHONY: install-lint-build-deps
install-lint-build-deps: install-ty

.PHONY: lint-ty
lint-ty: install-ty
	ty check

.PHONY: install-ty
install-ty:
ifneq ($(shell which ty),)
else ifneq ($(shell which snap),)
	sudo snap install --beta astral-ty
	sudo snap alias astral-ty.ty ty
else ifneq ($(shell which uv),)
	uv tool install ty
endif
