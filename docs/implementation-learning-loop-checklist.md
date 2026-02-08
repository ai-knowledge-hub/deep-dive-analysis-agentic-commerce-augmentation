# Learning Loop Implementation Checklist

Source architecture: `docs/architecture-learning-loop.md`  
Goal: ticket-ready execution plan for backend-first implementation.

---

## Milestone A: Foundational Belief Loop

## A1. Schema and migrations
- [x] Add migration for `world_states`.
- [x] Add migration for `belief_revisions`.
- [x] Add migration for `decision_events`.
- [x] Add indexes:
  - [x] `world_states(client_id, brand_id, product_id, created_at)`
  - [x] `belief_revisions(client_id, brand_id, product_id, hypothesis_key, created_at)`
  - [x] `decision_events(client_id, brand_id, product_id, created_at)`
- [x] Update ERD/docs if table definitions change.

## A2. Repository layer
- [x] Add DB repo methods:
  - [x] `create_world_state_snapshot(...)`
  - [x] `list_world_states(...)`
  - [x] `create_belief_revision(...)`
  - [x] `list_belief_revisions(...)`
  - [x] `create_decision_event(...)`
  - [x] `list_decision_events(...)`

## A3. Service layer
- [x] Implement `belief_update_service`:
  - [x] Normalize evidence packet.
  - [x] Compute weighted likelihood.
  - [x] Compute posterior + confidence.
  - [x] Persist `belief_revisions`.
- [x] Implement `state_service` snapshot write/read.
- [x] Implement minimal `policy_service` decision logger to `decision_events`.

## A4. API layer
- [x] Add `POST /beliefs/update`.
- [x] Add `GET /loop/state`.
- [x] Add DTOs and validation schemas.

## A5. Integration hooks
- [x] Trigger belief update after validation completion.
- [x] Record policy action + uncertainty per loop step.

## A6. Tests
- [x] Unit tests for posterior math edge cases.
- [x] API tests for `/beliefs/update`.
- [x] Integration test: validation event -> belief revision row created.
- [x] Tenant isolation tests for belief read/write.

## A7. Acceptance gate (Milestone A)
- [x] Every validation creates a belief revision.
- [x] Belief revisions queryable per tenant scope.
- [x] No cross-tenant reads.

---

## Milestone B: Memory Distillation and Retrieval

## B1. Schema and migrations
- [x] Add migration for `memory_artifacts`.
- [x] Add indexes:
  - [x] `(client_id, brand_id, vertical, artifact_type)`
  - [x] `(quality_score, support_count, created_at)`

## B2. Repository layer
- [x] Add methods:
  - [x] `create_memory_artifact(...)`
  - [x] `update_memory_artifact_score(...)`
  - [x] `list_memory_artifacts(...)`
  - [x] `mark_memory_artifact_used(...)`

## B3. Service layer
- [x] Implement `memory_service.distill(...)`:
  - [x] quality scoring
  - [x] support threshold gating
  - [x] contradiction checks vs recent observed validations
- [x] Implement `memory_service.retrieve(...)`:
  - [x] priority order (product -> brand+vertical -> vertical global)
  - [x] freshness window
  - [x] minimum quality threshold

## B4. Generation pipeline integration
- [x] Query battery generation consumes retrieved memory artifacts.
- [x] Copy generation consumes retrieved memory artifacts.
- [x] Persist provenance IDs with each generation event.

## B5. API layer
- [x] Add `GET /memory/artifacts`.
- [x] Add `POST /memory/distill`.

## B6. Tests
- [x] Unit tests for quality/support thresholds.
- [x] Unit tests for retrieval precedence order.
- [x] Integration tests for provenance logging.
- [x] Regression tests for tenant-scoped memory retrieval.

## B7. Acceptance gate (Milestone B)
- [x] Low-quality artifacts never injected into generation.
- [x] Retrieval always returns tenant-safe artifacts only.
- [x] Generation logs memory provenance.

---

## Milestone C: Adaptive Policy + Calibration

## C1. Schema and migrations
- [x] Add migration for `calibration_profiles`.
- [x] Add indexes:
  - [x] `(client_id, brand_id, provider)`
  - [x] `(updated_at)`

## C2. Repository layer
- [x] Add methods:
  - [x] `get_calibration_profile(...)`
  - [x] `upsert_calibration_profile(...)`
  - [x] `list_calibration_profiles(...)`

## C3. Service layer
- [x] Extend `policy_service`:
  - [x] action scoring by uncertainty + expected gain
  - [x] calibration-weighted decisioning
- [x] Extend `belief_update_service`:
  - [x] apply provider-specific calibration weights
  - [x] drift-aware confidence adjustment

## C4. API layer
- [x] Add `POST /loop/step`.
- [x] Add `GET /calibration/profile`.

## C5. Scheduler/operations
- [x] Add periodic calibration refresh job.
- [x] Add periodic memory distillation job.
- [x] Add observability counters for:
  - [x] update frequency
  - [x] drift trend
  - [x] action distribution

## C6. Tests
- [x] Unit tests for policy action ranking.
- [x] Unit tests for calibration weight application.
- [x] Integration tests for `/loop/step` output consistency.

## C7. Acceptance gate (Milestone C)
- [x] Policy outputs are auditable and stable under repeat inputs.
- [x] Observed validation influences decisions more than synthetic by default.
- [x] Calibration profiles update without breaking tenant isolation.

---

## Cross-Cutting Tasks

## CCT1. Security and tenancy
- [x] Enforce client scope checks on all new endpoints.
- [x] Add RBAC hooks for future role-based access.

## CCT2. Observability
- [x] Add structured logs for:
  - [x] belief update input/output
  - [x] memory retrieval provenance
  - [x] policy decisions
- [x] Add metrics for loop health:
  - [x] acceptance rate
  - [x] regeneration rate
  - [x] observed-vs-synthetic agreement

## CCT3. Backward compatibility
- [x] Keep optional fallbacks where needed.
- [x] Provide migration notes for local/dev DB refresh.

## CCT4. Documentation
- [x] Update `docs/app-workflows.md` with loop wiring.
- [x] Update `README.md` with new endpoints and migration commands.
- [x] Keep `docs/debug/incidents-fixed.md` and `docs/debug/open-risks.md` updated.

---

## Suggested Ticket Breakdown

## Epic 1: Belief Loop Core
- [x] Ticket A1: DB migrations for state/belief/decision.
- [x] Ticket A2: Repo + service + API for belief updates.
- [x] Ticket A3: Hook validation -> belief update.

## Epic 2: Memory Engine
- [x] Ticket B1: Memory artifact schema + repo.
- [x] Ticket B2: Distillation service + thresholds.
- [x] Ticket B3: Retrieval integration into query/copy generation.

## Epic 3: Adaptive Policy
- [x] Ticket C1: Calibration profile schema + repo.
- [x] Ticket C2: Policy step endpoint and decision scoring.
- [x] Ticket C3: Scheduled distillation/calibration jobs.

---

## Pre-E2E Readiness Checklist

- [x] DB migrations apply cleanly from empty DB and existing DB.
- [x] New endpoints covered by API tests.
- [x] Frontend contracts aligned for any new API used.
- [ ] Lint/tests pass in CI profile.
- [ ] Tenant isolation manually verified across at least 2 clients.
