# App Architecture (Current State + Planned Extensions)

Status: current
Last verified: 2026-09-05
Baseline: `origin/main@96a1c23` (includes PR #120)

This document reflects what is currently implemented and marks future items as **Planned (not built)**.

---

## 1) System Overview

The app is built as a **Bayesian-style learning loop**:

1. Generate candidate improvements (simulation/experiments).
2. Validate with synthetic and observed signals.
3. Update beliefs with weighted evidence.
4. Distill reusable memory artifacts.
5. Reuse memory in future query/copy generation.
6. Recalibrate against synthetic-vs-observed drift.

```
Next.js UI
  ├─ Chat / Alignment / Evidence
  ├─ Simulation
  ├─ Experiments
  ├─ Validation
  ├─ Agent Runs (operator workspace)
  └─ Admin (onboarding + operations)
            │
            ▼
FastAPI Routes
  ├─ conversation / evidence / simulation / experiments / batteries
  ├─ validation / beliefs / loop / calibration / memory
  ├─ agent-runs (create/list/detail/control/decision)
  └─ admin / analytics / tenants
            │
            ▼
Application Services
  ├─ conversation/
  ├─ evidence/
  ├─ simulation/
  ├─ experiment/
  ├─ query_battery/
  ├─ loop/
  ├─ agent_runtime/
  ├─ admin/
  └─ validation_service.py
            │
            ▼
Infrastructure
  ├─ SQLite repositories (`infrastructure/db/*`)
  ├─ LLM provider adapters (BYOK)
  ├─ protocol adapters (UCP/ACP readiness)
  └─ skill + config persistence
```

---

## 2) Frontend Structure (Current)

- `web/app/page.tsx`: chat workflow entry.
- `web/app/alignment/page.tsx`: intent-product alignment.
- `web/app/evidence/page.tsx`: evidence diagnostics.
- `web/app/simulation/page.tsx`: run/optimize/retest workflow.
- `web/app/experiments/page.tsx`: batteries, variants, runs, metrics.
- `web/app/validation/page.tsx`: centralized synthetic + observed validation.
- `web/app/agent-runs/page.tsx`: agent operator workspace (queue approvals + execution controls + explainability).
- `web/app/admin/page.tsx`: onboarding workspace + model gateway + operations.

Admin onboarding is section-based (collapsible panels):
- Client profile
- Brand setup
- Product catalog
- Canonical intent spec
- Review

---

## 3) Backend Modules (Current)

### Route layer
- `api/routes/experiments.py`
- `api/routes/batteries.py`
- `api/routes/simulation.py`
- `api/routes/validation.py`
- `api/routes/agent_runs.py`
- `api/routes/agent_approvals.py`
- `api/routes/beliefs.py`
- `api/routes/loop.py`
- `api/routes/admin.py`

### Service layer
- `application/services/conversation/*`
- `application/services/evidence/*`
- `application/services/simulation/*`
- `application/services/experiment/*`
- `application/services/query_battery/*`
- `application/services/loop/*`
- `application/services/agent_runtime/*`
- `application/services/admin/*`
- `application/services/validation_service.py`

### Architecture guardrail
- `make arch-check` enforces that application services do not import infrastructure directly.

### DB adapter layout (current)
- DB adapters are grouped by domain under `infrastructure/db/`:
  - `core/` (connection, json, tenancy)
  - `agent/`
  - `experiment/`
  - `validation/`
  - `loop/`
  - `catalog/`
  - `session/`
  - `search/`
- Flat adapter modules under `infrastructure/db/*.py` (except package initializer
  files named **__init__.py**) were removed.

---

## 4) Data Model Snapshot (Current)

Core entities in active use:
- tenancy: clients, brands, products, client_users
- conversation: sessions, turns, goals, episodes
- simulation: simulation_runs, simulation_lessons
- experiments: experiments, experiment_variants, experiment_runs, experiment_metrics
- validation: validation_jobs, validation_results, experiment_validations, experiment_calibrations
- learning loop: world_states, belief_revisions, decision_events, memory_artifacts, calibration_profiles, loop_maintenance_runs
- intelligence: brand_beliefs, audience_archetypes, analytics_events
- operations: skills, skills_history, llm_provider_configs
- agent runtime: agent_runs, agent_actions, agent_events, approval_records,
  approval_commands, approval_events, approval_effect_executions, and
  governed_effect_receipts

Canonical spec fields are stored in:
- `products.metadata.canonical_intent_spec`

Autofill traceability metadata:
- `canonical_intent_spec_raw`
- `canonical_intent_spec_normalized`
- `canonical_intent_mapping`

---

## 5) Query Battery Architecture (Current)

Modes:
- `top_down`
- `bottom_up`
- `hybrid`

Pipeline:
1. Build context capsule.
2. Generate deterministic candidates by mode.
3. Optional LLM expansion.
4. Deduplicate and validate.
5. Optional retry with stricter filtering.
6. Persist accepted queries and expose reject reasons.

Quality gates:
- banned term filtering (brand/product/spec leakage controls)
- category confidence gate for bottom-up/hybrid
- over-specific and invalid-pattern rejection
- generation eval instrumentation to `analytics_events`

Current bottom-up rule:
- If category confidence is low, generation is blocked and user is redirected to set canonical category in Admin.

---

## 6) Validation + Belief + Memory Loop (Current)

Validation has two explicit signals:

1. **Synthetic validation signal**
- provider/model based (BYOK)
- fast screening consistency checks

2. **Observed reality signal**
- manual observed logging of what actually surfaced
- used for agreement/accuracy and drift tracking

Belief and memory flow:
- validation evidence can trigger belief revisions
- policy decisions are logged with uncertainty metadata
- high-quality/high-support artifacts are distilled into memory
- memory retrieval is scoped and quality-gated

Loop maintenance:
- calibration refresh + memory distillation job
- manual trigger in Admin or scheduled workflow
- run history persisted

---

## 7) Agentic Module Architecture (Current)

The agentic module is implemented as an orchestration layer over the same experiment protocol used by manual workflows.

### Scope and boundaries
- UI workspace: `web/app/agent-runs/page.tsx`
- API boundary: `api/routes/agent_runs.py`
- Runtime boundary: `application/services/agent_runtime/runtime/service.py`
- Worker boundary: `application/services/agent_runtime/worker.py`
- Event mapping boundary: `application/services/agent_runtime/events.py`
- Capability execution boundary: `application/services/agent_runtime/capabilities/executor.py`
- Capability contract registry: `application/services/agent_runtime/registry/contracts.py`
- Policy checks: `application/services/agent_runtime/policy.py`
- Approval decisions and canonical payloads:
  `application/services/agent_runtime/approval_ledger.py`
- Exact admission, effect-start, completion, and reconciliation:
  `application/services/agent_runtime/approval_authorization.py`
- Public durable-evidence recovery:
  `application/services/agent_runtime/effect_recovery.py`

### Runtime behavior
- `run_mode=plan_only` is default (no side-effect execution).
- `run_mode=auto_execute_safe` allows approved actions to be executed via `step`.
- Single-lane safety:
  - per-run lease lock (`lock_token`, `lock_expires_at`)
  - heartbeat refresh (`last_heartbeat_at`)
  - atomic action claim (`approved -> executing -> executed|failed`)
- Bounded autonomous execution:
  - worker tick endpoint `POST /agent-runs/tick`
  - CLI runner `scripts/ops/run_agent_runtime_worker.py`
  - Make target `make agent-runtime-tick`
  - scheduler loop `scripts/ops/run_agent_runtime_scheduler.py` / `make agent-runtime-scheduler`

### Capability and policy model
- Capabilities are explicit names with a shared contract:
  - required inputs
  - default inputs
  - side effects (documentation-level effect surface)
  - optional next-state mapping
- Policy and exact authority are enforced at admission and again immediately
  before a governed effect:
  - capability allow-list
  - required inputs present
  - action budget (`max_actions`)
  - variant-run budget (`max_variant_runs`)
  - cost budget (`max_cost_usd`)

### Data model
- `agent_runs` stores scope, objective, capability allow-list, versions, budgets, approval policy, state/status, and lock/heartbeat metadata.
- `agent_actions` stores ordered action queue entries with status, rationale, confidence, inputs/outputs hashes, and artifact anchors.
- `agent_events` stores lifecycle events for audit/replay
  (`proposed/approved/rejected/executing/executed/failed` plus run-control
  events). Normal application repositories append rather than update these
  rows, but the database does not prevent update or deletion and run deletion
  cascades to its events. Database-enforced tamper-evident, append-only audit
  remains planned under `SEC-18`.
- approval decision rows preserve the immutable approved binding, canonical
  executable payload, deciding authority, expiry, revocation, and fulfillment.
- approval effect execution rows preserve single-use effect identity and an
  immutable effect-start snapshot. A post-start acknowledgement failure becomes
  `uncertain`, not a retryable success or silent failure.
- governed effect receipts bind committed lab promotions to the exact approval,
  tenant, experiment, variant, and source metric. Those relationships are
  re-read under the final write transaction.

### Recovery and projection integrity

- `reconcile_effect` is a bearer-authorized, tenant-scoped operator command.
- Recovery discovers durable provider or governed-effect evidence and never
  re-executes the external effect.
- Late evidence is checked against the immutable effect-start snapshot rather
  than mutable run projections.
- Run projection restoration uses compare-and-swap/retry when concurrent
  replanning changes the action set.
- Retry and change-plan allocate sequence and retry identity under the write
  lock; terminal runs remain closed.

### UX integration points
- Sidebar includes **Agent runs** as a first-class module.
- Experiments includes an **Agent operator mode** panel:
  - latest run status for selected experiment
  - direct CTAs to open/start in Agent runs.
- Agent Runs includes:
  - run selection rail + operator workspace
  - execution controls
  - next recommended action panel
  - approvals/audit queue
  - inline guardrail block reasons
  - selected-action explainability panel (summary, side effects, linked artifacts)
  - budget telemetry cards with warn/danger states
  - detailed artifact diff drawer + copy diff mode
  - execution timeline with presets, filters, deep-links, and deep-link recovery.

### Agent run events API
- `GET /agent-runs/{run_id}/events`
- Query params:
  - `event_type=all|failed|policy|executed|command`
  - `status=all|proposed|approved|executing|executed|failed|rejected`
  - `capability_name`
  - `since`, `until`
  - `before`, `after` (keyset pagination cursors)
  - `event_id`, `around` (return a centered event window for deep-link recovery)
  - `limit`
- Event shape includes:
  - action sequence/status/capability/timestamp
  - policy flag and note
  - anchors (`experiment_id`, `variant_id`, `validation_job_id`, `hypothesis_id`, `snapshot_version`, `metric_id`)
- Source of truth:
  - events are read from persisted `agent_events` rows (not derived on-the-fly from `agent_actions`).

---

## 8) Planned (Not Built Yet)

- richer normalization pipeline (spell/synonym/unit + ontology confidence scoring)
- stronger classifier-based category inference
- native GA4 connector (current analytics ingestion is generic API-based)
- confidence-scored simulation lesson promotion beyond current safeguards
- full backend serverless hardening for Vercel Python runtime
- **Agent operator mode expansion**:
  - capability/policy version registry hardening and richer audit telemetry
  - multi-agent role model (planner/variant/validation/policy) using shared capabilities
  - reference: `docs/agentic-layer.md`
