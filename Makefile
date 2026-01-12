PYTHON ?= python

.PHONY: fmt lint test typecheck import-spells verify

fmt:
	$(PYTHON) -m black .

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest

typecheck:
	$(PYTHON) -m mypy src

import-spells:
	$(PYTHON) -m dnd_db.cli import-spells

verify:
	$(PYTHON) -m dnd_db.cli verify
