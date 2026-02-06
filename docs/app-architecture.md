# App Architecture (Current State + Planned Extensions)

This document reflects the **current implementation** and marks future work as **Planned (not built)**.

---

## 1) System Overview

```
Next.js UI
  ├─ Chat / Alignment / Evidence
  ├─ Simulation
  ├─ Experiments (Lab + Manual modes)
  └─ Admin (onboarding + skills)
            │
            ▼
FastAPI Routes
  ├─ conversation / alignment / evidence
  ├─ simulation
  ├─ experiments / batteries / validations
  ├─ analytics events
  └─ admin / tenants
            │
            ▼
Application Services
  ├─ intent + goal clarification
  ├─ alignment + evidence analysis
  ├─ simulation + optimization + retest
  ├─ query battery generation + validation
  ├─ experiments + metrics + recommendations
  └─ validation rollups + calibration summary
            │
            ▼
Infrastructure
  ├─ SQLite
  ├─ LLM providers (Gemini/OpenRouter)
  ├─ protocol readiness adapters
  └─ skill prompt storage + history
```

---

## 2) Frontend Structure (Current)

- `web/app/page.tsx`: Chat and manual workflow entry.
- `web/app/alignment/page.tsx`: Intent-product alignment.
- `web/app/evidence/page.tsx`: Evidence and signal diagnostics.
- `web/app/simulation/page.tsx`: Simulation run/optimize/retest.
- `web/app/experiments/page.tsx`: Battery + variants + experiment execution + validation status.
- `web/app/admin/page.tsx`: Onboarding workspace and operational controls.

### Admin onboarding workspace (current)
- Step-oriented collapsible flow:
  1. Client Profile
  2. Brand Setup
  3. Product Catalog
  4. Canonical Intent Spec
  5. Review
- Canonical spec editor now uses controlled ontology fields (category, sub-category, use-cases, archetypes, feature concepts, constraints, must-not-target).

---

## 3) Backend Modules (Current)

- `api/routes/experiments.py`: experiment runs, metrics, validation logs, summaries.
- `api/routes/batteries.py`: create battery + generate queries.
- `api/routes/admin.py`: clients/brands/products, platform profile, skill management.
- `api/routes/admin.py`: includes canonical spec autofill preview/apply from UCP/ACP/feed.
- `application/services/query_battery_builder.py`: top-down/bottom-up/hybrid generation, quality filtering, retry.
- `application/services/canonical_intent_spec_service.py`: source mapping, normalization, category inference, clarification prompt.
- `application/services/query_battery_llm_generator.py`: LLM prompt contract for query generation.
- `application/services/experiment_validation_service.py`: prediction accuracy and unlock thresholds.

---

## 4) Data Model Snapshot (Current)

Core tables/entities in active use:
- Clients / Brands / Products
- Conversation Sessions
- Query Batteries / Battery Queries
- Experiments / Variants / Runs / Metrics
- Experiment Validations / Calibration rollups
- Brand Beliefs
- Simulation Runs / Lessons
- Skills / Skills History
- Analytics Events

### Product canonical intent spec (stored in product metadata)
`products.metadata.canonical_intent_spec` currently stores:
- `category`
- `sub_category`
- `use_cases`
- `audience_archetypes`
- `feature_concepts`
- `core_constraints`
- `must_not_target`
- `objective_keywords`
- `banned_keywords`
- `source`, `updated_at`

Additional metadata saved by autofill flow:
- `canonical_intent_spec_raw`
- `canonical_intent_spec_normalized`
- `canonical_intent_mapping`

---

## 5) Query Battery Generation Architecture (Current)

### Supported modes
- `top_down`
- `bottom_up`
- `hybrid`

### Inputs
- Battery context
- Product metadata + canonical intent spec
- Optional seed queries/features/use-cases
- Optional LLM generation pass

### Quality controls in service
- Brand/product/features/use-cases banned-term filtering
- Over-specific token rejection (e.g., hard numeric spec tokens)
- Required category check (for bottom-up/hybrid)
- Retry pass with stricter bans when accepted volume is too low
- Structured report: accepted count, rejected count, rejected reasons

### Memory/archetype confidence gating
- Archetypes loaded from store are filtered by confidence threshold.
- Belief snippets are filtered by confidence threshold.
- Simulation lessons are currently excluded from prompt memory until confidence metadata exists.

### Eval instrumentation
- Query generation writes `query_generation_eval` events into `analytics_events`.
- Battery-level dashboards are available via:
  - `GET /batteries/{id}/eval-summary`
  - `GET /batteries/{id}/ontology-updates`

---

## 6) Validation & Calibration Architecture (Current)

Validation sources implemented:
1. Manual validation logs via experiments routes.
2. External analytics event ingestion endpoint (`/analytics/events`).
3. Validation jobs + results (Validation page, BYOK or external paste-back).

Calibration outputs available now:
- Verified runs
- Prediction accuracy
- Unlock eligibility for pattern insights

Unlock rule (soft gate):
- `verified_runs >= 10`
- `accuracy >= 0.75`

---

## 7) What Is Planned (Not Built Yet)

- Full normalization pipeline (spell/synonym/unit normalization + ontology confidence scoring).
- Category inference classifier with confidence-based “block and clarify” step.
- High-confidence simulation-lesson reuse (after confidence scoring is added).
- Native GA4 connector (today: generic analytics event ingestion only).
- Full serverless Vercel deployment of backend.
