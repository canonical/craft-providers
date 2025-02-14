PROJECT=craft_providers
UV_TEST_GROUPS := "--group=dev"
UV_DOCS_GROUPS := "--group=docs"
UV_LINT_GROUPS := "--group=lint" "--group=types"

# If you have dev dependencies that depend on your distro version, uncomment these:
# ifneq ($(wildcard /etc/os-release),)
# include /etc/os-release
# endif
# ifdef VERSION_CODENAME
# UV_TEST_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# UV_DOCS_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# UV_LINT_GROUPS += "--group=dev-$(VERSION_CODENAME)"
# endif

include common.mk

.PHONY: format
format: format-ruff format-codespell format-prettier  ## Run all automatic formatters

.PHONY: lint
lint: lint-ruff lint-codespell lint-mypy lint-prettier lint-pyright lint-shellcheck lint-docs lint-twine  ## Run all linters

.PHONY: pack
pack: pack-pip  ## Build all packages

.PHONY: publish
publish: publish-pypi  ## Publish packages

.PHONY: publish-pypi
publish-pypi: clean package-pip lint-twine  ##- Publish Python packages to pypi
	uv tool run twine upload dist/*

# Find dependencies that need installing
APT_PACKAGES :=

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
ifeq ($(wildcard /snap/hello-world),)
	sudo snap install hello-world
endif

# If additional build dependencies need installing in order to build the linting env.
.PHONY: install-lint-build-deps
install-lint-build-deps:
