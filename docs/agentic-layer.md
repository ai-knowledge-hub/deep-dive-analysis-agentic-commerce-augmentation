# Build The Agentic Layer (Approach, Rationale, Roadmap)

This document describes the planned **agent operator mode**: a governed orchestration layer that can run the lab protocol end-to-end (or partially) under explicit constraints.

Status: **Planned (not built end-to-end)**. Individual prerequisites already exist (frozen snapshots, baseline gating, hypotheses, decision policy inputs/outputs, audit primitives).

---

## 1) Does The Plan Make Sense?

Yes, with two clarifications:

1. **Agent autonomy must be plan autonomy, not execution autonomy.**
   - Agents propose and queue actions.
   - The system enforces protocol constraints and can require approval at defined gates.

2. **“Versioned capability packages” must include experiment semantics, not just code.**
   - Prompt templates and prompt versions
   - Scoring parameters
   - Validation weighting thresholds
   - Provider configs/modes (which change what “validation” means)

The goal is scientific reproducibility: the same inputs + same capability versions should produce comparable outputs across time.

---

## 2) Separate Layer vs Converting The Whole Lab

Build it as a **separate orchestration layer** that drives the existing lab protocol.

Reason:
- The current app is already a protocol engine + UI. Replacing it with agents would regress reliability and debuggability.
- Agents should be **consumers** of the protocol, not owners of it.

Target state:
- **Manual operator mode** and **Agent operator mode**
- Both hit the same:
  - capability registry
  - policy enforcer
  - audit log
  - DB artifacts (snapshots, hypotheses, runs, validations, belief revisions, decision events)

---

## 3) Architectural Additions (Concrete)

### 3.1 AgentRuntime (backend boundary)

Add an `AgentRuntime` service inside the backend (not frontend-driven).

It runs **agent sessions** as jobs:
- `agent_run` has: state machine stage, objective, allowed capabilities, scope (tenant/product/experiment), and pinned capability versions.
- It produces `agent_actions` (proposed + executed), with a stable event-like format.

This prevents “UI-driven autonomy” and keeps the system auditable and reproducible.

### 3.2 Capability Registry (the key abstraction)

Agents must not call raw endpoints. They request named capabilities:

Examples:
- `ensure_battery_ready`
- `freeze_retrieval_protocol` (create/freeze snapshot set)
- `run_control_baseline`
- `seed_hypotheses`
- `generate_variants`
- `run_variant`
- `request_synthetic_validation`
- `log_observed_validation` (still user-driven initially)
- `update_posterior_and_decisions`
- `recommend_next_action`

Each capability definition includes:
- input schema + output schema
- preconditions (policy-as-code checks)
- explicit side effects: which tables/artifacts it can write

### 3.3 Policy-as-code (enforcement stays system-side)

Formalize enforcement checks used by both humans and agents:
- frozen snapshot required for retrieval-backed scoring
- baseline-first gating
- spend / run / query budget caps per cycle
- stop conditions (drift too high, validation disagreement, low support size)
- approval gates (optional):
  - promotion to “prod tier”
  - publishing copy revisions

### 3.4 Audit Log (`agent_actions`)

Make actions event-like and queryable:
- `agent_id`, `agent_run_id`
- `capability_name`, `capability_version`
- `inputs_hash`, `outputs_hash`
- scope fields: `client_id`, `brand_id`, `product_id`, `experiment_id`
- protocol anchors: `snapshot_version`, `hypothesis_id`, `variant_id`
- `rationale`, `confidence`
- status: `proposed | approved | executed | rejected | failed`

### 3.5 Version Registry (scientific reproducibility)

Introduce a simple capability/policy version registry and stamp versions onto:
- experiment snapshot records
- experiment metrics rows
- validation jobs/results
- belief revisions / posterior updates

This makes longitudinal comparisons defensible when prompting/scoring changes.

---

## 4) Objective Function and Decision Policy (Current Direction)

### 4.1 Evidence Types (inputs)

For each variant `v` (vs control) on a frozen `snapshot_version`:
- `E_exp`: retrieval-backed experiment outcome signal (battery-wide deltas)
- `E_syn`: synthetic validation (in-app BYOK / provider run / manual fallback)
- `E_obs`: observed reality validation (currently manual and sparse)

Each evidence type yields:
- `effect ∈ [-1, +1]` (negative = worse than control)
- `reliability ∈ [0, 1]` (support size, consensus, recency, etc.)

### 4.2 Weighted combined score (single scalar)

We use a combined score for decisioning:

```
score(v) = w_exp * contrib(E_exp) + w_syn * contrib(E_syn) + w_obs * contrib(E_obs)
contrib(E) = effect(E) * sqrt(reliability(E))
```

Defaults (current, because observed is sparse/manual):
- `w_exp = 0.55`
- `w_syn = 0.35`
- `w_obs = 0.10`

Adaptive observed weight:
- `w_obs = clamp(0.10 + 0.25 * coverage_obs, 0.10, 0.35)`
- subtract extra from synthetic first to preserve experiment dominance

### 4.3 Decision tiers (automation without losing control)

Two promotion tiers:
- `PROMOTE_LAB`: can proceed in the lab loop
- `PROMOTE_PROD`: requires minimum observed coverage threshold

Example:
- `likelihood >= 0.75` -> promote
- `0.45 <= likelihood < 0.75` -> iterate
- else reject
- promotion tier = `prod` only when observed coverage passes threshold

Implementation note:
- The repository already persists `decision_policy_version`, `decision_inputs`, and `decision_outputs` per metrics row.

---

## 5) Transition Plan (Pragmatic)

### Phase 1: Lab Operator Agent (safe, minimal)
Agent can:
- ensure battery ready
- freeze snapshots
- run control baseline
- seed hypotheses
- generate variants
- run one candidate

No validation automation beyond requesting synthetic jobs.

### Phase 2: Validation Agent
Agent can:
- request synthetic validation automatically
- recommend “needs observed check” when synthetic-only is insufficient
Agent cannot:
- promote to prod tier without observed threshold satisfied

### Phase 3: Policy Agent
Agent can:
- read posterior + drift + agreement + support size
- emit promote/iterate/reject recommendations
Promotion/publish actions can remain approval-gated.

---

## 6) Scaling Later (Gateway + Multi-Agent)

If/when you scale to multiple concurrent agents:
- put `AgentRuntime` behind a single gateway process (job queue + worker pool)
- keep capabilities stable contracts
- allow multiple “role agents” to coordinate through the runtime (planner/variant/validation/policy)

Potential future coordination mechanisms:
- A2A protocols (for structured agent-to-agent messaging)
- AutoGen-style executive hierarchy

Key principle:
**Scaling changes the orchestrator, not the protocol engine.** The protocol engine stays the source of truth and enforcement.

