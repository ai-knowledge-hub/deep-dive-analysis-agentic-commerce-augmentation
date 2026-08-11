ifneq ($(wildcard ./venv/bin/python),)
PYTHON := ./venv/bin/python
PIP := ./venv/bin/pip
RUFF := ./venv/bin/ruff
else ifneq ($(wildcard ./.venv/bin/python),)
PYTHON := ./.venv/bin/python
PIP := ./.venv/bin/pip
RUFF := ./.venv/bin/ruff
else
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
endif

.PHONY: install
install:
	$(PIP) install -r requirements.txt

.PHONY: test
test:
	$(PYTHON) -m pytest

.PHONY: run-backend
run-backend:
	uvicorn api.main:app --reload --port 8000

.PHONY: run-frontend
run-frontend:
	cd web && pnpm dev

.PHONY: web-lint
web-lint:
	cd web && pnpm lint

.PHONY: web-complexity-check
web-complexity-check:
	cd web && pnpm complexity-check

.PHONY: web-ui-language-check
web-ui-language-check:
	cd web && pnpm ui-language-check

.PHONY: web-test
web-test:
	cd web && pnpm test

.PHONY: web-typecheck
web-typecheck:
	cd web && pnpm typecheck

.PHONY: web-build
web-build:
	cd web && pnpm build

.PHONY: web-verify
web-verify:
	cd web && pnpm verify

.PHONY: lint
lint:
	@if [ -n "$(RUFF)" ] && [ -x "$(RUFF)" ]; then \
		$(RUFF) check . --force-exclude; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check . --force-exclude; \
	else \
		echo "ruff is not installed. Run: uv sync --extra dev (or pip install -r requirements.txt)"; \
		exit 1; \
	fi

.PHONY: arch-check
arch-check:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.checks.arch_check; \
	else \
		$(PYTHON) -m scripts.checks.arch_check; \
	fi

.PHONY: bloat-check
bloat-check:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.checks.bloat_check; \
	else \
		$(PYTHON) -m scripts.checks.bloat_check; \
	fi

.PHONY: script-entrypoint-check
script-entrypoint-check:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.checks.script_entrypoints_check; \
	else \
		$(PYTHON) -m scripts.checks.script_entrypoints_check; \
	fi

.PHONY: safety-traceability-check
safety-traceability-check:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.checks.safety_traceability_check; \
	else \
		$(PYTHON) -m scripts.checks.safety_traceability_check; \
	fi

.PHONY: format
format:
	@if [ -n "$(RUFF)" ] && [ -x "$(RUFF)" ]; then \
		$(RUFF) format . --force-exclude; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff format . --force-exclude; \
	else \
		echo "ruff is not installed. Run: uv sync --extra dev (or pip install -r requirements.txt)"; \
		exit 1; \
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
		./.venv/bin/python -m scripts.seed.seed_demo_competitors; \
	else \
		$(PYTHON) -m scripts.seed.seed_demo_competitors; \
	fi

.PHONY: seed-canonical
seed-canonical:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.seed.seed_canonical_intent_specs; \
	else \
		$(PYTHON) -m scripts.seed.seed_canonical_intent_specs; \
	fi

.PHONY: seed-demo-acme
seed-demo-acme:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.seed.seed_demo_acme; \
	else \
		$(PYTHON) -m scripts.seed.seed_demo_acme; \
	fi

.PHONY: loop-maintenance
loop-maintenance:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.ops.run_learning_loop_maintenance; \
	else \
		$(PYTHON) -m scripts.ops.run_learning_loop_maintenance; \
	fi

.PHONY: agent-runtime-tick
agent-runtime-tick:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.ops.run_agent_runtime_worker; \
	else \
		$(PYTHON) -m scripts.ops.run_agent_runtime_worker; \
	fi

.PHONY: agent-runtime-scheduler
agent-runtime-scheduler:
	@if [ -x ./.venv/bin/python ]; then \
		./.venv/bin/python -m scripts.ops.run_agent_runtime_scheduler; \
	else \
		$(PYTHON) -m scripts.ops.run_agent_runtime_scheduler; \
	fi
