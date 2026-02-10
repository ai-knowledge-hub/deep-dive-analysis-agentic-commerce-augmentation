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

Experiment protocol transparency APIs:
- `GET /experiments/{experiment_id}/execution-state`
- `GET /experiments/{experiment_id}/retrieval-snapshots`
- `GET /experiments/{experiment_id}/hypotheses`

---

## Validation Model

Validation now lives in the dedicated Validation flow/page and splits into:

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
uv sync
uv run uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd web
cp ../.env.example .env.local
pnpm install
pnpm dev
```

Open:
- App: `http://localhost:3000`
- Validation: `http://localhost:3000/validation`

---

## Local DB Setup (Recommended)

Use one DB file for migrations + seeds + backend runtime.

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

```bash
make lint
make arch-check
make test
make web-lint
```

Architecture checks are part of CI and enforce layer boundaries.

---

## Documentation

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
