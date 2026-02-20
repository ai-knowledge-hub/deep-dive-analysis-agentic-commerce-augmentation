# App Architecture (Current State + Planned Extensions)

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
  └─ Admin (onboarding + operations)
            │
            ▼
FastAPI Routes
  ├─ conversation / evidence / simulation / experiments / batteries
  ├─ validation / beliefs / loop / calibration / memory
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
- Flat adapter modules under `infrastructure/db/*.py` (except `__init__.py`) were removed.

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

## 7) Planned (Not Built Yet)

- richer normalization pipeline (spell/synonym/unit + ontology confidence scoring)
- stronger classifier-based category inference
- native GA4 connector (current analytics ingestion is generic API-based)
- confidence-scored simulation lesson promotion beyond current safeguards
- full backend serverless hardening for Vercel Python runtime
- **Agent operator mode expansion** (governed orchestration layer is partially implemented):
  - completed: backend `AgentRuntime` controls + run/action persistence + step execution + lock/heartbeat safety
  - next: centralized capability registry + policy enforcer
  - next: capability/policy version registry hardening and richer audit explainability
  - next: multi-agent role model (planner/variant/validation/policy) using shared capabilities
  - reference: `docs/agentic-layer.md`
