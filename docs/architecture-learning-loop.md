# Learning Loop Backend Architecture

## Goal
Make the app’s core promise explicit in backend design: a self-learning loop that improves product discoverability by updating beliefs from evidence and reusing high-quality memory in future runs.

This architecture treats simulation/experiments as evidence generators and validation as the calibration anchor, not as an oracle.

---

## Scope and Principles

1. **Screening vs reality**
- Synthetic judge results are useful for fast screening.
- Observed validation (real platform outcomes) has higher weight in belief updates.

2. **State first**
- Each loop runs against a scoped world state:
  - `(client_id, brand_id, product_id, vertical)`.

3. **Traceable updates**
- Every recommendation and belief change must be auditable.

4. **Memory quality gates**
- Only high-confidence, high-support patterns are reusable.

---

## Logical Backend Structure

### 1) State Layer
Source of truth for current knowledge and readiness.

- Service: `state_service`
- Responsibilities:
  - Load active world state per scope.
  - Version and snapshot state transitions.

### 2) Inference Layer
Infers user/market context under uncertainty.

- Service: `inference_service`
- Responsibilities:
  - Intent + goal inference.
  - Audience-in-context archetype inference.
  - Uncertainty scoring.

### 3) Policy Layer
Decides next action based on expected gain.

- Service: `policy_service`
- Actions:
  - `optimize_copy`
  - `expand_battery`
  - `validate`
  - `clarify`
  - `update_belief_only`

### 4) Experimentation Layer
Synthetic evidence generation.

- Existing services:
  - `simulation_service`
  - `experiment_service`

### 5) Validation Layer
Reality-grounding and provider checks.

- Existing/extended service: `validation_service`
- Inputs:
  - Synthetic LLM judge signal.
  - Observed reality signal (manual/external).

### 6) Belief Update Layer
Applies weighted posterior updates.

- New service: `belief_update_service`
- Responsibilities:
  - Merge evidence packet.
  - Apply weighted Bayesian-style update.
  - Persist belief revision history.

### 7) Memory Layer
Distills and serves reusable priors.

- New service: `memory_service`
- Responsibilities:
  - Distill lessons to artifacts.
  - Score artifacts by quality/support/recency.
  - Retrieve memory for query/copy generation.

### 8) Governance Layer
Ensures isolation and role-safe operations.

- Existing tenancy controls + upcoming RBAC enforcement.

---

## Memory Horizons

### Short-term memory (session horizon)
- Backed by: session state and active run context.
- Use: immediate turn-to-turn continuity.

### Medium-term memory (run horizon)
- Backed by: simulation/experiment/validation events.
- Use: compare candidate strategies in current cycle.

### Long-term memory (distilled horizon)
- Backed by: promoted artifacts and belief revisions by vertical/archetype.
- Use: priors for new batteries/copy for similar contexts.

---

## Data Model Additions (Recommended)

## `world_states`
- `id TEXT PK`
- `client_id TEXT NOT NULL`
- `brand_id TEXT`
- `product_id TEXT`
- `vertical TEXT`
- `state_json TEXT NOT NULL`
- `version INTEGER NOT NULL`
- `created_at TEXT`

Purpose: immutable snapshots of scope state.

## `belief_revisions`
- `id TEXT PK`
- `client_id TEXT NOT NULL`
- `brand_id TEXT`
- `product_id TEXT`
- `hypothesis_key TEXT NOT NULL`
- `prior REAL NOT NULL`
- `likelihood REAL NOT NULL`
- `posterior REAL NOT NULL`
- `confidence REAL NOT NULL`
- `evidence_ref_json TEXT`
- `created_at TEXT`

Purpose: auditable belief evolution.

## `memory_artifacts`
- `id TEXT PK`
- `client_id TEXT NOT NULL`
- `brand_id TEXT`
- `vertical TEXT`
- `artifact_type TEXT NOT NULL`  
  (`query_pattern|copy_pattern|audience_pattern`)
- `payload_json TEXT NOT NULL`
- `quality_score REAL DEFAULT 0`
- `support_count INTEGER DEFAULT 0`
- `last_used_at TEXT`
- `created_at TEXT`

Purpose: reusable distilled knowledge.

## `decision_events`
- `id TEXT PK`
- `client_id TEXT NOT NULL`
- `brand_id TEXT`
- `product_id TEXT`
- `policy_action TEXT NOT NULL`
- `uncertainty REAL`
- `expected_gain REAL`
- `selected_reason TEXT`
- `created_at TEXT`

Purpose: explainable control decisions.

## `calibration_profiles`
- `id TEXT PK`
- `client_id TEXT NOT NULL`
- `brand_id TEXT`
- `provider TEXT NOT NULL`
- `metric_weights_json TEXT`
- `drift_score REAL`
- `updated_at TEXT`

Purpose: provider/brand-level correction over time.

---

## Update Logic (Operational)

For each loop execution:

1. **Build evidence packet**
- `E_syn` from simulation + experiment metrics.
- `E_obs` from observed validations.
- `E_cal` from calibration profile.

2. **Reliability weighting**
- Compute `w_syn`, `w_obs`, `w_cal`.
- Default policy: `w_obs > w_syn`.

3. **Belief update**
- `posterior ∝ prior × likelihood(E_syn, E_obs, E_cal)`.
- Confidence adjusted by:
  - support size,
  - source agreement,
  - recency.

4. **Persist**
- Save to `belief_revisions`.
- Save decision trace to `decision_events`.

5. **Distill memory**
- Promote only if:
  - `quality_score >= threshold`
  - `support_count >= threshold`
  - no contradiction with recent observed signals.

---

## Retrieval Contract for Query/Copy Generation

When generating batteries or copy candidates:

1. Resolve scope and retrieve in order:
- product-scoped artifacts,
- brand+vertical artifacts,
- global vertical artifacts.

2. Apply quality filters:
- minimum quality,
- freshness window,
- contradiction check.

3. Inject only normalized artifacts:
- no raw/low-quality snippets.

4. Log provenance:
- record artifact IDs used for each generation event.

---

## API Contract Additions (Recommended)

### `GET /loop/state`
Params: `client_id`, `brand_id`, `product_id`

Returns: current scope state + latest belief summary + uncertainty.

### `POST /loop/step`
Body: scope + optional user context.

Runs: infer -> policy -> recommended next action.

### `POST /beliefs/update`
Body: normalized evidence packet.

Returns: updated posterior + confidence + revision id.

### `GET /memory/artifacts`
Params: `vertical`, `artifact_type`, scope ids.

Returns: ranked reusable artifacts.

### `POST /memory/distill`
Body: candidate artifact + support evidence references.

Returns: accepted/rejected + reason.

### `GET /calibration/profile`
Params: `brand_id`, `provider`

Returns: active correction weights and drift score.

---

## End-to-End Loop Sequence

1. User/session context enters inference.
2. Policy selects action:
- optimize copy / expand battery / validate / clarify.
3. Simulation/experiments generate synthetic evidence.
4. Validation adds observed or external evidence.
5. Belief update computes posterior and confidence.
6. Memory distillation promotes reusable patterns.
7. Next run consumes updated beliefs + memory artifacts.

---

## Implementation Milestones

## Milestone A (Foundational)
- Add `world_states`, `belief_revisions`, `decision_events`.
- Implement `belief_update_service`.
- Trigger belief updates from validation completion.

## Milestone B (Memory)
- Add `memory_artifacts`.
- Implement distillation + retrieval contract.
- Integrate retrieval into query battery and copy generation.

## Milestone C (Adaptive Control)
- Add `calibration_profiles`.
- Implement `policy_service` action selection.
- Expose `/loop/step` endpoint.

---

## Acceptance Criteria

1. Every validation event yields a belief revision record.
2. Query/copy generation logs memory artifact provenance.
3. Observed validation has stronger impact than synthetic by default.
4. Policy decisions are auditable via `decision_events`.
5. No cross-tenant memory leakage in retrieval.

---

## Release Review Checks (for this architecture)

1. Belief drift check:
- Verify posterior moves in expected direction after observed validation.

2. Memory quality check:
- Ensure low-support artifacts are not reused.

3. Tenant isolation check:
- Validate retrieval returns only scope-eligible artifacts.

4. Calibration check:
- Verify provider drift modifies decision weighting without overriding observed truth.

