# This Makefile exists for compatibility with the Starflow TICS workflow.
# https://github.com/canonical/starflow/blob/main/.github/workflows/tics.yaml

.PHONY: setup-tics
setup-tics:
	python -m pip install --user tox

.PHONY: test-coverage
test-coverage:
	tox -f tics
