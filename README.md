# Agentic Commerce Learning Loop (Bayesian-Style)

**Optimize product discoverability for LLM shopping flows with a closed learning loop: simulate -> validate -> update beliefs -> distill memory -> optimize again.**

---

## What This Repository Is

This project is a multi-tenant agentic commerce system for:
- intent-aware product discoverability optimization,
- experiment/simulation-based screening,
- real-world validation capture,
- Bayesian-style belief updates,
- memory distillation and reuse.

The core moat is not a single score. It is the **feedback loop** that continuously updates decisions using observed evidence.

Current extension:
- **Agent operator mode (v0)**: governed backend orchestration with run/action persistence, runtime step controls, centralized capability registry, and policy enforcement.
  See `docs/agentic-layer.md`.
- **Agent-first pivot checkpoint**: the platform direction is now a governed agent execution fabric with a human control plane, not only a human-led lab.
  See `docs/agentification-checkpoint.md`.

---

## Product Positioning

This app is a **screening + validation + learning** platform.

- **Screening:** synthetic LLM judge signals (fast iteration).
- **Validation:** observed reality signals plus provider-integrated synthetic checks.
- **Learning:** belief revision + memory distillation + calibration profiles.

It does **not** claim guaranteed production ranking outcomes from lab scores alone.

---

## Core Learning Loop

1. Run simulation/experiments to generate candidate improvements.
2. Validate with synthetic and/or observed signals.
3. Update scoped beliefs (`client_id`, `brand_id`, `product_id`) via Bayesian-style weighting.
4. Distill high-quality memory artifacts.
5. Use those artifacts in future query generation and copy optimization.
6. Recalibrate policy weights from drift between synthetic vs observed outcomes.
7. Convert posterior into decision action (`promote_variant`, `iterate_variant`, `reject_hypothesis`).

Loop APIs:
- `GET /loop/state`
- `POST /loop/step`
- `POST /beliefs/update`
- `GET /calibration/profile`
- `GET /memory/artifacts`
- `POST /memory/distill`

Operational endpoints:
- `POST /admin/ops/loop-maintenance`
- `GET /admin/ops/loop-maintenance/history`

---

## Architecture (Current)

- `domain/` -> pure business logic/types.
- `application/services/` -> orchestrators grouped by capability:
  - `application/services/admin/`
  - `application/services/conversation/`
  - `application/services/evidence/`
  - `application/services/experiment/`
  - `application/services/loop/`
  - `application/services/query_battery/`
  - `application/services/simulation/`
  - `application/services/validation_service.py`
- `infrastructure/` -> DB + LLM adapters + protocol adapters.
- `api/` -> FastAPI routes (composition root at `api/composition.py`).
- `web/` -> Next.js app.
- `shared/` -> schema, config, common utilities.

Layer rule enforced by architecture checks:
- Application layer must not import infrastructure directly.

---

## Key Capabilities

- Intent inference + alignment scoring.
- Evidence analysis and protocol readiness (UCP/ACP).
- Simulation sandbox (`run -> optimize -> retest`).
- Query battery generation (top-down / bottom-up / hybrid).
- Canonical intent spec and controlled onboarding.
- Experiment orchestration with variants/runs/metrics.
- Retrieval-backed frozen protocol snapshots (`snapshot_version`) for fair variant comparison.
- Baseline-first gating for candidate runs in retrieval-backed mode.
- Hypothesis persistence and linkage (`hypothesis_id`) across variants and runs.
- Versioned decision policy inputs/outputs persisted per metrics row (`decision_policy_version`, `decision_inputs`, `decision_outputs`).
- Variant generation paths for experiments:
  - manual variant authoring,
  - simulation revision prefill,
  - closed-loop evidence generation (experiment + simulation + validation),
  - cold-start copy generation (bottom-up / top-down / both).
- Validation system with two signals:
  - Synthetic validation (LLM judge signal: in-app BYOK, provider run, manual fallback).
  - Observed reality validation (manual observed outcomes).
- Belief revisions, decision events, calibration profiles.
- Memory artifacts with quality/support gating and provenance tracking.
- Agent operator mode:
  - plan-first run creation (`plan_only` default),
  - approved action execution in `auto_execute_safe`,
  - runtime safety with run lock + heartbeat refresh,
  - centralized capability specs + policy checks,
  - machine-facing tools/skills registry exposed through `GET /agent-runs/registry`,
  - principal-aware run creation for humans, internal agents, and external agents,
  - skill/tool/effect lineage stamped onto planned actions and runtime events,
  - operator UI in `Agent runs` with approvals, timeline deep-links, and action explainability,
  - immutable run event history (`agent_events`) for audit/replay.

Experiment protocol transparency APIs:
- `GET /experiments/{experiment_id}/execution-state`
- `GET /experiments/{experiment_id}/retrieval-snapshots`
- `GET /experiments/{experiment_id}/hypotheses`

Agent operator APIs:
- `GET /agent-runs/registry`
  - read-only skills/tools/capabilities registry
  - exposes policy profile summaries for operator and agent clients
- `POST /agent-runs`
- `GET /agent-runs`
- `GET /agent-runs/{run_id}`
- `GET /agent-runs/{run_id}/events`
  - run-level event feed with keyset pagination and deep-link recovery
  - supports:
    - `event_type=all|failed|policy|executed`
    - `status=all|proposed|approved|executing|executed|failed|rejected`
    - `capability_name`
    - `since`, `until`
    - `before`, `after`
    - `event_id`, `around` (center timeline around a specific event)
- `POST /agent-runs/{run_id}/start`
- `POST /agent-runs/{run_id}/pause`
- `POST /agent-runs/{run_id}/cancel`
- `POST /agent-runs/{run_id}/step`
- `POST /agent-runs/actions/{action_id}/decision`
- `POST /agent-runs/tick` (bounded autonomous worker tick)

Agent Runs operator UX (current):
- compact left-rail + main workspace layout
- next recommended action panel
- inline guardrail reasons on blocked approvals
- timeline presets (`All activity`, `Policy failures (24h)`, `Variant execution (7d)`, `Validation focus (7d)`)
- timeline deep-link state in URL (`run_id`, filters, `event_id`)
- per-event deep-link copy with feedback and automatic deep-link recovery when event is outside current page window

Agent runtime worker/scheduler:
- one-off tick: `make agent-runtime-tick`
- interval scheduler: `make agent-runtime-scheduler` (or `python -m scripts.run_agent_runtime_scheduler --interval-seconds 30`)

---

## Validation Model

Validation lives in the dedicated Validation flow/page and splits into:

1. **Synthetic validation signal**
- Uses configured provider/model (BYOK).
- Fast consistency and copy-vs-copy checks.
- Supports execution modes:
  - `in_app_byok` (fully implemented)
  - `provider_openai_mcp` (fully implemented)
  - `provider_gemini_function` (UI/API contract present, backend execution pending)
  - `manual_fallback` (structured paste-back)

2. **Observed reality signal**
- Manual observed capture of what actually surfaced.
- Tracks validation progress and agreement with lab winners.

This separation keeps experiment UX focused on design/run/analyze while validation remains centralized.

---

## Quick Start

### Backend

```bash
cp .env.example .env.local
uv sync --extra dev
uv run uvicorn api.main:app --reload --port 8000
```

Note: `make lint` and `make format` require dev dependencies (`uv sync --extra dev`) because `ruff` is installed via the `dev` extra.

### Frontend

```bash
cd web
cp ../.env.example .env.local
pnpm install
pnpm dev
```

Frontend tests:

```bash
cd web
pnpm install
pnpm test
```

If `pnpm test` fails with `vitest: command not found`, run `pnpm install` again in `web/` to pull the new test dependencies.

Open:
- App: `http://localhost:3000`
- Validation: `http://localhost:3000/validation`

---

## Local DB Setup (Recommended)

Use one DB file for migrations + seeds + backend runtime.

Canonical DB bootstrap/migration sources:
- schema: `shared/db/schema.sql`
- migrations: `shared/db/migrations/*.sql`

```bash
rm -f ./tmp/local.db
DATABASE_PATH=./tmp/local.db make db-init
DATABASE_PATH=./tmp/local.db make seed-demo
DATABASE_PATH=./tmp/local.db make seed-canonical
DATABASE_PATH=./tmp/local.db make seed-demo-acme
DATABASE_PATH=./tmp/local.db make db-validate-migrate
DATABASE_PATH=./tmp/local.db make db-migrate
DATABASE_PATH=./tmp/local.db uv run uvicorn api.main:app --reload --port 8000
```

Useful helpers:

```bash
make db-path
make db-reset
make loop-maintenance
make agent-runtime-tick
make agent-runtime-scheduler
```

---

## Model Gateway (BYOK)

Admin -> Operational controls -> Model gateway:
- Set per-provider keys and models.
- Separate chat/generation and validation model settings.
- Activate provider centrally.

Default model presets:
- OpenRouter: `openai/gpt-oss-120b`
- OpenAI: `gpt-5.2-2025-12-11`
- Claude (Anthropic): `claude-sonnet-4-5-20250929`
- Gemini: `gemini-3-flash-preview`

Health endpoint:
- `GET /health/llm`

---

## Provider Validation Integrations

Provider-run synthetic validation is feature-flagged.

Required env vars:
- `ENABLE_PROVIDER_VALIDATION_INTEGRATIONS=true`
- `BACKEND_PUBLIC_URL` (public backend base used to build callback URL)
- `VALIDATION_CALLBACK_SIGNING_SECRET` (HMAC signing key for callback verification)

Optional env vars:
- `VALIDATION_CALLBACK_TTL_SECONDS` (default `900`)
- `OPENAI_MCP_LAUNCH_URL` (default `https://chatgpt.com/`)
- `GEMINI_FUNCTION_LAUNCH_URL` (default `https://gemini.google.com/`)

Current status:
- OpenAI ChatGPT MCP launch/callback flow: implemented.
- Gemini function-call launch mode: API contract is present, execution currently returns `501 Not Implemented`.

---

## Operations and Scheduling

Loop maintenance can run:
- manually from Admin (`Run loop maintenance`),
- via CLI (`make loop-maintenance`),
- on schedule (template workflow):
  - `.github/workflows/loop-maintenance-template.yml`

---

## Testing and Quality Gates

Install dev tools first (includes `ruff`):

```bash
uv sync --extra dev
```

If you see `No module named ruff` when running `make lint` or `make format`, run `uv sync --extra dev` again in the repo root.

```bash
make lint
make format
make arch-check
make test
make web-lint
```

Architecture checks are part of CI and enforce layer boundaries.

---

## Documentation

- `docs/agentification-checkpoint.md`
- `docs/agent-first-modular-architecture-v1.md`
- `docs/agent-first-migration-slice-rfc.md`
- `docs/agentic-layer.md`
- `docs/chat-led-operator-console-spec.md`
- `docs/ui-control-plane-simplification-plan.md`
- `docs/app-architecture.md`
- `docs/app-workflows.md`
- `docs/experiment-flow-detailed.md`
- `docs/architecture-learning-loop.md`
- `docs/user-guide-complete.md`
- `docs/external-integrations.md`
- `docs/deployment.md`
- `docs/debug/incidents-fixed.md`
- `docs/debug/open-risks.md`

---

## License

Apache 2.0
