UV_AVAILABLE := $(shell command -v uv >/dev/null 2>&1 && echo yes || echo no)
ifeq ($(UV_AVAILABLE),yes)
PYTHON := uv run python
PIP := uv pip install
else
PYTHON := python3
PIP := pip install
endif

.PHONY: install
install:
	$(PIP) -r requirements.txt

.PHONY: test
test:
	$(PYTHON) -m pytest

.PHONY: run-backend
run-backend:
	uvicorn api.main:app --reload --port 8000

.PHONY: run-frontend
run-frontend:
	cd web && pnpm dev

.PHONY: lint
lint:
	$(PYTHON) -m ruff check .

.PHONY: format
format:
	$(PYTHON) -m ruff format .

.PHONY: run-local
run-local:
	LLM_PROVIDER=openrouter CATALOG_SOURCE=mock DATABASE_PATH=./tmp/local.db uvicorn api.main:app --reload --port 8000

.PHONY: run-dev
run-dev:
	LLM_PROVIDER=gemini uvicorn api.main:app --reload --port 8000

.PHONY: db-init
db-init:
	$(PYTHON) -m shared.db.connection

.PHONY: db-reset
db-reset:
	rm -f $${DATABASE_PATH:-./tmp/local.db}
	$(PYTHON) -m shared.db.connection

.PHONY: db-path
db-path:
	@python -c "from shared.db.connection import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH)"
