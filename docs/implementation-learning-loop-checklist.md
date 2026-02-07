# Learning Loop Implementation Checklist

Source architecture: `docs/architecture-learning-loop.md`  
Goal: ticket-ready execution plan for backend-first implementation.

---

## Milestone A: Foundational Belief Loop

## A1. Schema and migrations
- [ ] Add migration for `world_states`.
- [ ] Add migration for `belief_revisions`.
- [ ] Add migration for `decision_events`.
- [ ] Add indexes:
  - [ ] `world_states(client_id, brand_id, product_id, created_at)`
  - [ ] `belief_revisions(client_id, brand_id, product_id, hypothesis_key, created_at)`
  - [ ] `decision_events(client_id, brand_id, product_id, created_at)`
- [ ] Update ERD/docs if table definitions change.

## A2. Repository layer
- [ ] Add DB repo methods:
  - [ ] `create_world_state_snapshot(...)`
  - [ ] `list_world_states(...)`
  - [ ] `create_belief_revision(...)`
  - [ ] `list_belief_revisions(...)`
  - [ ] `create_decision_event(...)`
  - [ ] `list_decision_events(...)`

## A3. Service layer
- [ ] Implement `belief_update_service`:
  - [ ] Normalize evidence packet.
  - [ ] Compute weighted likelihood.
  - [ ] Compute posterior + confidence.
  - [ ] Persist `belief_revisions`.
- [ ] Implement `state_service` snapshot write/read.
- [ ] Implement minimal `policy_service` decision logger to `decision_events`.

## A4. API layer
- [ ] Add `POST /beliefs/update`.
- [ ] Add `GET /loop/state`.
- [ ] Add DTOs and validation schemas.

## A5. Integration hooks
- [ ] Trigger belief update after validation completion.
- [ ] Record policy action + uncertainty per loop step.

## A6. Tests
- [ ] Unit tests for posterior math edge cases.
- [ ] API tests for `/beliefs/update`.
- [ ] Integration test: validation event -> belief revision row created.
- [ ] Tenant isolation tests for belief read/write.

## A7. Acceptance gate (Milestone A)
- [ ] Every validation creates a belief revision.
- [ ] Belief revisions queryable per tenant scope.
- [ ] No cross-tenant reads.

---

## Milestone B: Memory Distillation and Retrieval

## B1. Schema and migrations
- [ ] Add migration for `memory_artifacts`.
- [ ] Add indexes:
  - [ ] `(client_id, brand_id, vertical, artifact_type)`
  - [ ] `(quality_score, support_count, created_at)`

## B2. Repository layer
- [ ] Add methods:
  - [ ] `create_memory_artifact(...)`
  - [ ] `update_memory_artifact_score(...)`
  - [ ] `list_memory_artifacts(...)`
  - [ ] `mark_memory_artifact_used(...)`

## B3. Service layer
- [ ] Implement `memory_service.distill(...)`:
  - [ ] quality scoring
  - [ ] support threshold gating
  - [ ] contradiction checks vs recent observed validations
- [ ] Implement `memory_service.retrieve(...)`:
  - [ ] priority order (product -> brand+vertical -> vertical global)
  - [ ] freshness window
  - [ ] minimum quality threshold

## B4. Generation pipeline integration
- [ ] Query battery generation consumes retrieved memory artifacts.
- [ ] Copy generation consumes retrieved memory artifacts.
- [ ] Persist provenance IDs with each generation event.

## B5. API layer
- [ ] Add `GET /memory/artifacts`.
- [ ] Add `POST /memory/distill`.

## B6. Tests
- [ ] Unit tests for quality/support thresholds.
- [ ] Unit tests for retrieval precedence order.
- [ ] Integration tests for provenance logging.
- [ ] Regression tests for tenant-scoped memory retrieval.

## B7. Acceptance gate (Milestone B)
- [ ] Low-quality artifacts never injected into generation.
- [ ] Retrieval always returns tenant-safe artifacts only.
- [ ] Generation logs memory provenance.

---

## Milestone C: Adaptive Policy + Calibration

## C1. Schema and migrations
- [ ] Add migration for `calibration_profiles`.
- [ ] Add indexes:
  - [ ] `(client_id, brand_id, provider)`
  - [ ] `(updated_at)`

## C2. Repository layer
- [ ] Add methods:
  - [ ] `get_calibration_profile(...)`
  - [ ] `upsert_calibration_profile(...)`
  - [ ] `list_calibration_profiles(...)`

## C3. Service layer
- [ ] Extend `policy_service`:
  - [ ] action scoring by uncertainty + expected gain
  - [ ] calibration-weighted decisioning
- [ ] Extend `belief_update_service`:
  - [ ] apply provider-specific calibration weights
  - [ ] drift-aware confidence adjustment

## C4. API layer
- [ ] Add `POST /loop/step`.
- [ ] Add `GET /calibration/profile`.

## C5. Scheduler/operations
- [ ] Add periodic calibration refresh job.
- [ ] Add periodic memory distillation job.
- [ ] Add observability counters for:
  - [ ] update frequency
  - [ ] drift trend
  - [ ] action distribution

## C6. Tests
- [ ] Unit tests for policy action ranking.
- [ ] Unit tests for calibration weight application.
- [ ] Integration tests for `/loop/step` output consistency.

## C7. Acceptance gate (Milestone C)
- [ ] Policy outputs are auditable and stable under repeat inputs.
- [ ] Observed validation influences decisions more than synthetic by default.
- [ ] Calibration profiles update without breaking tenant isolation.

---

## Cross-Cutting Tasks

## CCT1. Security and tenancy
- [ ] Enforce client scope checks on all new endpoints.
- [ ] Add RBAC hooks for future role-based access.

## CCT2. Observability
- [ ] Add structured logs for:
  - [ ] belief update input/output
  - [ ] memory retrieval provenance
  - [ ] policy decisions
- [ ] Add metrics for loop health:
  - [ ] acceptance rate
  - [ ] regeneration rate
  - [ ] observed-vs-synthetic agreement

## CCT3. Backward compatibility
- [ ] Keep optional fallbacks where needed.
- [ ] Provide migration notes for local/dev DB refresh.

## CCT4. Documentation
- [ ] Update `docs/app-workflows.md` with loop wiring.
- [ ] Update `README.md` with new endpoints and migration commands.
- [ ] Keep `docs/debug/incidents-fixed.md` and `docs/debug/open-risks.md` updated.

---

## Suggested Ticket Breakdown

## Epic 1: Belief Loop Core
- [ ] Ticket A1: DB migrations for state/belief/decision.
- [ ] Ticket A2: Repo + service + API for belief updates.
- [ ] Ticket A3: Hook validation -> belief update.

## Epic 2: Memory Engine
- [ ] Ticket B1: Memory artifact schema + repo.
- [ ] Ticket B2: Distillation service + thresholds.
- [ ] Ticket B3: Retrieval integration into query/copy generation.

## Epic 3: Adaptive Policy
- [ ] Ticket C1: Calibration profile schema + repo.
- [ ] Ticket C2: Policy step endpoint and decision scoring.
- [ ] Ticket C3: Scheduled distillation/calibration jobs.

---

## Pre-E2E Readiness Checklist

- [ ] DB migrations apply cleanly from empty DB and existing DB.
- [ ] New endpoints covered by API tests.
- [ ] Frontend contracts aligned for any new API used.
- [ ] Lint/tests pass in CI profile.
- [ ] Tenant isolation manually verified across at least 2 clients.

