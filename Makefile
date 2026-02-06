UV_AVAILABLE := $(shell command -v uv >/dev/null 2>&1 && echo yes || echo no)
ifeq ($(UV_AVAILABLE),yes)
UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
UV_RUN := UV_CACHE_DIR=$(UV_CACHE_DIR) uv run
UV_PIP := UV_CACHE_DIR=$(UV_CACHE_DIR) uv pip
PYTHON := $(UV_RUN) python
PIP := $(UV_PIP) install
else
PYTHON := python3
PIP := pip install
endif

.PHONY: install
install:
	$(PIP) -r requirements.txt

.PHONY: test
test:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m pytest; \
	else \
		$(PYTHON) -m pytest; \
	fi

.PHONY: run-backend
run-backend:
	uvicorn api.main:app --reload --port 8000

.PHONY: run-frontend
run-frontend:
	cd web && pnpm dev

.PHONY: web-lint
web-lint:
	cd web && pnpm lint

.PHONY: web-test
web-test:
	cd web && pnpm test

.PHONY: lint
lint:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m ruff check . --force-exclude; \
	else \
		$(PYTHON) -m ruff check . --force-exclude; \
	fi

.PHONY: arch-check
arch-check:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.arch_check; \
	else \
		$(PYTHON) -m scripts.arch_check; \
	fi

.PHONY: format
format:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m ruff format . --force-exclude; \
	else \
		$(PYTHON) -m ruff format . --force-exclude; \
	fi

.PHONY: run-local
run-local:
	LLM_PROVIDER=openrouter DATABASE_PATH=./tmp/local.db EMBEDDING_PREFER_LOCAL=true uvicorn api.main:app --reload --port 8000

.PHONY: run-dev
run-dev:
	LLM_PROVIDER=gemini uvicorn api.main:app --reload --port 8000

.PHONY: db-init
db-init:
	$(PYTHON) -m shared.db.connection

.PHONY: db-migrate
db-migrate:
	$(PYTHON) -m shared.db.connection

.PHONY: db-validate-migrate
db-validate-migrate:
	$(PYTHON) -m shared.db.connection

.PHONY: db-reset
db-reset:
	@DB_PATH="$$( $(PYTHON) -c "from shared.db.connection import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH)" )"; \
	ROOT="$$(pwd -P)"; \
	if [ "$${ENV:-}" = "prod" ] || [ "$${ENV:-}" = "production" ]; then \
		echo "Refusing to reset DB in production environment (ENV=$${ENV})."; \
		exit 1; \
	fi; \
	case "$$DB_PATH" in \
		"$$ROOT"/*) ;; \
		*) if [ "$${CONFIRM_DB_RESET:-}" != "1" ]; then \
			echo "DB path '$$DB_PATH' is outside repo. Re-run with CONFIRM_DB_RESET=1 to override."; \
			exit 1; \
		   fi ;; \
	esac; \
	rm -f "$$DB_PATH"; \
	$(PYTHON) -m shared.db.connection

.PHONY: db-path
db-path:
	@$(PYTHON) -c "from shared.db.connection import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH)"

.PHONY: seed-demo
seed-demo:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.seed_demo_competitors; \
	else \
		$(PYTHON) -m scripts.seed_demo_competitors; \
	fi

.PHONY: seed-canonical
seed-canonical:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.seed_canonical_intent_specs; \
	else \
		$(PYTHON) -m scripts.seed_canonical_intent_specs; \
	fi

.PHONY: seed-demo-acme
seed-demo-acme:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.seed_demo_acme; \
	else \
		$(PYTHON) -m scripts.seed_demo_acme; \
	fi
