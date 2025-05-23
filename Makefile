# This Makefile exists for compatibility with the Starflow TICS workflow.
# https://github.com/canonical/starflow/blob/main/.github/workflows/tics.yaml

.PHONY: setup-tics
setup-tics:
ifneq ($(shell which uv),)
else ifneq ($(shell which snap),)
	sudo snap install --classic astral-uv
else ifneq ($(shell which brew),)
	brew install uv
else ifeq ($(OS),Windows_NT)
	pwsh -c "irm https://astral.sh/uv/install.ps1 | iex"
else
	curl -LsSf https://astral.sh/uv/install.sh | sh
endif
	uv tool install tox


.PHONY: test-coverage
test-coverage:
	tox -f tics
