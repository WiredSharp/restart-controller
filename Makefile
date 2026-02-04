VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: lint test format venv install-dev

venv:
	python3 -m venv $(VENV)

install-dev: venv
	$(PIP) install -e ".[dev]"

lint:
	$(VENV)/bin/ruff check src/ tests/

test:
	$(VENV)/bin/pytest -v

format:
	$(VENV)/bin/ruff format src/ tests/
	$(VENV)/bin/ruff check --fix src/ tests/
