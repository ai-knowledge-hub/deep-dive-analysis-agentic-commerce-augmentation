# Agentic Commerce Control Plane

**A supervised agent workspace for improving commerce discoverability: set the goal, review the recommendation, approve the action, and monitor the outcome.**

---

## What This Repository Is

This project is a multi-tenant control plane for commerce teams that want agents to improve how products are represented, discovered, validated, and monitored without forcing operators to drive every technical workflow manually.

The default user model is intentionally simple:

```text
Goal -> Agent suggestion -> Human review -> Approved action -> Outcome
```

Operators should not need to understand simulations, calibration, memory artifacts, harnesses, or policy internals before they can do useful work. Those mechanisms remain available for explanation, audit, and administration, but the primary product experience is built around attention, review, approval, and outcomes.

The core moat is the **governed feedback loop**: agents do the routine optimization work, humans stay in control of risky decisions, and observed outcomes improve future recommendations.

Current product direction:
- **Agent-first execution fabric**: principal-aware runs for humans, internal agents, and external agents; policy profiles; tool/skill lineage; registry-pinned actions; runtime receipt validation.
  See `docs/agentic-layer.md`.
- **Human control plane**: Inbox, Runs, Interventions, and Insights are the primary UX; Lab remains available as an advanced bench.
  See `docs/operator-experience.md`.
- **Usability simplification gate**: primary product surfaces use operator language first and hide internal mechanisms behind explanation, audit, admin, or lab affordances.
  See `docs/usability-simplification-gate.md`.
- **Next build track**: external-agent job APIs, harness profiles, protocol/fallback execution adapters, and deeper control-plane UX simplification.
  See the `Next Development Tracks` section in `docs/agentification-checkpoint.md`.

---

## Product Positioning

This app is a **supervised agent optimization** platform.

- **Set direction:** choose the product or commercial goal that needs improvement.
- **Review suggestions:** inspect what the agent recommends and why.
- **Approve action:** approve, reject, retry, pause, or recover risky work.
- **Monitor outcome:** see what changed and whether the system should keep going.
- **Open the machinery when needed:** advanced users can inspect validation, evidence, policy, registry, and runtime details.

It does **not** claim guaranteed production ranking outcomes from lab scores alone.

---

## Operator Loop

The daily product loop is:

1. Start in **Inbox** to see what needs attention.
2. Open **Runs** to understand what the agent is doing.
3. Use **Interventions** when a decision, approval, retry, or recovery is required.
4. Review **Insights** to see what changed and what the system recommends next.
5. Use **Lab** only when deeper manual investigation is needed.

## Internal Learning Loop

1. Run simulation/experiments to generate candidate improvements.
2. Validate with synthetic and/or observed signals.
3. Update scoped beliefs (`client_id`, `brand_id`, `product_id`) via Bayesian-style weighting.
4. Distill high-quality memory artifacts.
5. Use those artifacts in future query generation and copy optimization.
6. Recalibrate policy weights from drift between synthetic vs observed outcomes.
7. Convert posterior into decision action (`promote_variant`, `iterate_variant`, `reject_hypothesis`).

These are implementation mechanisms. Product surfaces should introduce them only as progressive disclosure under explanation, provenance, audit, or advanced-lab views.

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
  - `application/services/agent_runtime/`
    - `capabilities/` for capability execution and helpers
    - `commands/` for command preflight, orchestration, recovery, and decisions
    - `registry/` for tool/capability catalog and registry contracts
    - `runtime/` for execution service and runtime audit event construction
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
  - chat-issued steering commands with immutable `operator_command_*` receipts,
  - command preflight with blockers, warnings, risk, side effects, and rollback guidance,
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
    - `event_type=command` for `operator_command_*` receipts
    - `status=all|proposed|approved|executing|executed|failed|rejected`
    - `capability_name`
    - `since`, `until`
    - `before`, `after`
    - `event_id`, `around` (center timeline around a specific event)
- `POST /agent-runs/{run_id}/start`
- `POST /agent-runs/{run_id}/pause`
- `POST /agent-runs/{run_id}/cancel`
- `POST /agent-runs/{run_id}/step`
- `POST /agent-runs/{run_id}/commands`
  - chat/operator command endpoint for approve, reject, retry, start, pause, cancel, step
  - step and high-risk commands are confirmed through command preflight before execution
  - `retry` creates a new proposed retry action with incremented `retry_count`; it does not mutate the failed action back to approved
  - retry supports same-action, last-safe-checkpoint, and recovery-action strategies
  - recovery-action retry and `change_plan` can target a specific allowed capability
  - `change_plan` creates a proposed recovery action instead of silently mutating plans
  - proposed recovery actions persist side-effect metadata and rollback guidance for later approval/review
  - recovery proposals can include compensating-action recommendations for high-risk or external side effects
  - Interventions preflights and confirms audited compensating proposals directly from recommendations
  - command outcomes guide operators to relevant metrics, variants, validation jobs, revisions, hypotheses, snapshots, and failures
  - records non-mutating explain and focus intents as command receipts
- `POST /agent-runs/{run_id}/commands/preflight`
  - previews command risk, blockers, warnings, side effects, and rollback guidance before submission
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
- interval scheduler: `make agent-runtime-scheduler` (or `python -m scripts.ops.run_agent_runtime_scheduler --interval-seconds 30`)

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
- Control plane: `http://localhost:3000`
- Runs: `http://localhost:3000/runs`
- Lab bench: `http://localhost:3000/lab`

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
- `REGISTRY_APPROVAL_SIGNING_SECRET` (HMAC signing key for registry ownership approval receipts; falls back to `AGENT_PRINCIPAL_SIGNING_SECRET` outside production)

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
make bloat-check
make script-entrypoint-check
make test
make web-lint
make web-complexity-check
```

Architecture checks are part of CI and enforce layer boundaries, command-route boundaries, import-cycle detection, coupling/dependency-depth thresholds, and per-function complexity caps. Bloat checks block file-size growth in known hotspots. The frontend complexity check applies the same idea to TS/TSX imports, cycles, page coupling, relative import depth, and component/function complexity.

---

## Current Build Checkpoint

Completed foundation:
- Agent runtime persistence, policy profiles, skills/tools registry, registry release/audit trail, command preflight, retries, structured recovery proposals, compensating recommendations, and control-plane surfaces.
- Backend cleanup has split the agent runtime into `capabilities/`, `commands/`, `registry/`, and `runtime/` subpackages.
- Command routes are thin HTTP adapters; command orchestration lives in `application/services/agent_runtime/commands/service.py`.
- Harness profiles now define default run mode, policy posture, fallback/retry/memory strategy, and stopping conditions; run creation applies default harnesses from agent profiles, rejects mismatched autonomy posture, and recovery commands use harness retry/fallback defaults.
- Primary operator surfaces now use the flattened control-plane visual language; the current user guide lives in `docs/operator-experience.md`.

Remaining build tracks:
- External-agent job APIs with idempotency, retry-safe responses, scoped credentials, and signed execution receipts.
- Persistent tenant-specific harness/agent-profile defaults plus Interventions visibility for active harness posture.
- Real ACP/UCP/browser/CLI fallback execution adapters with narrow permissions and policy review for external side effects.
- Control-plane UX simplification so Inbox/Runs are primary, Lab is advanced, duplicate dashboards shrink, and risky work flows through Interventions.
- Continued source hygiene on large frontend pages and remaining hotspots, guarded by bloat and architecture checks.

---

## Documentation

Start with `docs/README.md` for the canonical documentation index and status map.

Current planning references:

- `docs/agentification-checkpoint.md`
- `docs/agent-first-modular-architecture-v1.md`
- `docs/agent-capability-map.md`
- `docs/external-agent-job-contracts.md`
- `docs/codebase-cleanup-and-modularisation-plan.md`
- `docs/agentic-layer.md`
- `docs/operator-experience.md`
- `docs/chat-led-operator-console-spec.md`
- `docs/ui-control-plane-simplification-plan.md`
- `docs/ui-style-direction.md`

Historical or candidate-historical docs are still retained, but should not be treated
as the current implementation plan without checking the checkpoint first.

---

## License

Apache 2.0
