VENV := .venv
PYTHON := $(VENV)/bin/python

.PHONY: help
help:
	@echo "make venv   - create the virtualenv and install dependencies"
	@echo "make run    - run the dashboard on http://127.0.0.1:5000"
	@echo "make test   - run the test suite"

$(VENV):
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: venv
venv: $(VENV)

.PHONY: run
run: $(VENV)
	$(PYTHON) app.py

.PHONY: test
test: $(VENV)
	$(PYTHON) -m pytest
	$(PYTHON) -m doctest versions.py
