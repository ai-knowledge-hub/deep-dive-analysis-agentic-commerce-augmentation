# Build The Agentic Layer (Approach, Rationale, Roadmap)

This document describes the **agent operator mode**: a governed orchestration layer that can run the lab protocol end-to-end (or partially) under explicit constraints.

Status: **Partially implemented (v0 Runtime Core complete; end-to-end autonomy still in progress)**.
Implemented now:
- Agent run and action persistence (`agent_runs`, `agent_actions`)
- Immutable event persistence (`agent_events`) for runtime + operator lifecycle events
- Plan-first run creation + approval workflow
- Runtime step execution service with short lease locking and heartbeat refresh
- Route-level runtime controls (`start`, `pause`, `cancel`, `step`)
- Operator UX in `/agent-runs` with queue approvals and action explainability
- Run-level event feed API and timeline deep-links in Agent Runs
- Experiment entry integration (`Experiments` -> `Agent operator mode` panel)
- Autonomous tick worker service (`AgentRuntimeWorkerService`) for bounded batch execution
- Autonomous scheduler service (`AgentRuntimeSchedulerService`) for interval-based continuous orchestration
- Principal-aware run creation for `human`, `internal_agent`, and `external_agent`
- Static skills/tools registry exposed at `GET /agent-runs/registry`
- New planned actions/events carry `skill_id`, `tool_id`, `effect_class`, principal metadata, and trace id
- Runs and Interventions UI visibility into selected-run skills, tools, policy profile, principal, and trace id
- Operator chat steering endpoint with audited `operator_command_*` receipts
- Command preflight endpoint with risk level, blockers, warnings, side effects, and rollback guidance

---

## 1) Two specific points

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

Build as a **separate orchestration layer** that drives the existing lab protocol.

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

## 3) Architectural Additions

### 3.1 AgentRuntime (backend boundary)

Implemented in v0: `AgentRuntimeService` inside backend (not frontend-driven).

It runs **agent sessions** as jobs:
- `agent_run` has: state machine stage, objective, allowed capabilities, scope (tenant/product/experiment), and pinned capability versions.
- It produces `agent_actions` (proposed + executed), with a stable event-like format.

This prevents “UI-driven autonomy” and keeps the system auditable and reproducible.

v0 Runtime Core behavior:
- `plan_only` remains default and blocks execution.
- `auto_execute_safe` enables stepping approved actions.
- Per-run short lease lock prevents concurrent execution (`lock_token`, `lock_expires_at`).
- Heartbeat is refreshed during execution (`last_heartbeat_at`).
- Action claim is atomic (`approved -> executing -> executed|failed`).
- Route handlers delegate to runtime service instead of duplicating execution logic.
- Runtime and operator transitions emit immutable events (`action_proposed`, `action_approved`, `action_rejected`, `action_executing`, `action_executed`, `action_failed`, `run_started`, `run_paused`, `run_canceled`).
- UI exposes action rationale, side effects summary, and linked artifacts for selected actions.
- UI includes:
  - left-rail + main workspace operator layout
  - budget telemetry cards with warning/danger states
  - next recommended action panel
  - proactive risky-approval disable (action/variant/cost budgets)
  - inline guardrail explainability on blocked approvals
  - detailed artifact diff drawer (including copy diff mode with hide-unchanged toggle)
  - execution timeline with presets, server-side filters, and deep-links.
  - timeline pagination (`before/after`), load-older UX, and live polling.
  - deep-link recovery when `event_id` is outside the current page window.
- Worker tick (`POST /agent-runs/tick`) processes runnable `auto_execute_safe` runs in bounded loops.

Worker/ops entry points:
- API: `POST /agent-runs/tick`
- API: `GET /agent-runs/{run_id}/events`
  - query params:
    - `event_type=all|failed|policy|executed|command`
    - `status=all|proposed|approved|executing|executed|failed|rejected`
    - `capability_name`
    - `since`, `until`
    - `before`, `after`
    - `event_id`, `around`
- API: `POST /agent-runs/{run_id}/commands`
  - records `operator_command_*` receipts from the chat control plane
  - delegates approve/reject/start/pause/cancel/step to existing action/runtime controls
  - handles retry by creating a new proposed retry action with incremented `retry_count`
  - handles `change_plan` by creating a proposed recovery action for operator review
  - supports non-mutating explain/focus receipts for chat-led steering
- API: `POST /agent-runs/{run_id}/commands/preflight`
  - returns whether a command is allowed before execution
  - includes risk level, required confirmation, blockers, warnings, side effects, and rollback guidance
- CLI: `python -m scripts.run_agent_runtime_worker`
- Make target: `make agent-runtime-tick`
- Scheduler CLI: `python -m scripts.run_agent_runtime_scheduler --interval-seconds 30`
- Scheduler Make target: `make agent-runtime-scheduler`

### 3.2 Capability Registry (the key abstraction)

Implemented in v0:
- centralized capability specs in `application/services/agent_runtime/registry.py`
- per-capability defaults, required inputs, side effects, and state transition mapping
- runtime + execution entrypoints validate against the same registry contract
- machine-facing `tool_id` values mapped from legacy `capability_name`
- initial static skill specs in `application/services/agent_runtime/agent_first.py`
- deterministic tool-to-skill lineage for planned actions and runtime events
- read API: `GET /agent-runs/registry`

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

### 3.2.1 Capability Inventory and Status

| Capability | Purpose | Current Status |
|---|---|---|
| `freeze_retrieval_protocol` | Create/reuse frozen retrieval snapshot set for the experiment battery | **Implemented (executable)** |
| `run_control_baseline` | Run control variant in retrieval-backed mode on frozen snapshot | **Implemented (executable)** |
| `seed_hypotheses` | Persist baseline-derived hypotheses from missing winner signals | **Implemented (executable)** |
| `generate_variants` | Generate and persist candidate variants from loop evidence/cold-start | **Implemented (executable)** |
| `run_variant` | Execute one candidate variant on frozen snapshot | **Implemented (executable)** |
| `request_synthetic_validation` | Create/start synthetic validation jobs | **Implemented (executable)** |
| `update_posterior_and_decisions` | Recompute posterior and decision outputs from evidence | **Implemented (executable)** |
| `review_validation_readiness` | Evaluate observed/synthetic coverage and readiness gates | **Implemented (executable)** |
| `recommend_next_action` | Emit ranked next-step recommendations under constraints | **Implemented (executable)** |
| `promote_variant_lab` | Promote variant for lab progression | **Implemented (executable)** |
| `promote_variant_prod` | Promote variant for production/publish path | **Implemented (executable, approval-gated)** |
| `publish_copy_revision` | Publish selected revision to product copy | **Implemented (executable, approval-gated)** |

Notes:
- `action only` means the planner seeds it as a proposed action, but execution is not wired yet.
- v0 default remains `run_mode=plan_only`; execution requires switching to `auto_execute_safe`.

### 3.2.2 Executable Capability Guides (v0)

#### `freeze_retrieval_protocol`
- What it does:
  - Creates or reuses a frozen retrieval snapshot set for all enabled battery queries.
  - Pins `snapshot_version` so variant comparisons are fair across the same retrieval context.
- How to use:
  1. Create an agent run for an experiment with this capability allowed.
  2. Approve `freeze_retrieval_protocol`.
  3. Run `step` in `auto_execute_safe` mode.
- Where it fits in flow:
  - `battery_ready -> retrieval_snapshots_ready`.

#### `run_control_baseline`
- What it does:
  - Resolves the control variant and runs it in retrieval-backed mode against the frozen snapshot.
  - Produces baseline metric row for gating candidate variants.
- How to use:
  1. Ensure `freeze_retrieval_protocol` has executed.
  2. Approve `run_control_baseline`.
  3. Run `step` in `auto_execute_safe` mode.
- Where it fits in flow:
  - `retrieval_snapshots_ready -> baseline_scored`.

#### `seed_hypotheses`
- What it does:
  - Reads control baseline runs for the active snapshot and persists hypotheses from repeated missing winner signals.
  - Uses existing baseline gap-analysis logic (same semantics as manual flow).
- How to use:
  1. Ensure control baseline has executed for target snapshot.
  2. Approve `seed_hypotheses`.
  3. Run `step` in `auto_execute_safe` mode.
- Where it fits in flow:
  - `baseline_scored -> hypotheses_ready`.

#### `generate_variants`
- What it does:
  - Calls the variant generator (`loop_evidence` or `cold_start`) and persists top candidates as experiment variants.
  - Stores provenance (`generation_mode`, `generation_strategy`, rationale/confidence, capability source).
  - Carries through `hypothesis_id` linkage when candidate payload includes it.
- How to use:
  1. Ensure hypotheses are available for the target snapshot (recommended).
  2. Approve `generate_variants`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Review persisted variants in Experiments before running them.
- Where it fits in flow:
  - `hypotheses_ready -> variants_ready`.

#### `run_variant`
- What it does:
  - Executes a candidate variant in retrieval-backed mode against the active frozen snapshot.
  - Supports either an explicit `variant_id` or selection rule (v0: latest non-control candidate).
  - Persists run and metric artifacts, including decision outputs when available.
- How to use:
  1. Ensure baseline gate is satisfied for current snapshot.
  2. Approve `run_variant`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Inspect metrics/posterior/decision action in Experiments and Agent action outputs.
- Where it fits in flow:
  - `variants_ready -> experiment_run_completed`.

#### `request_synthetic_validation`
- What it does:
  - Builds experiment validation payload (experiment + runs + metrics + variants).
  - Creates a synthetic validation job (`entity_type=experiment_run`).
  - Can optionally auto-run immediately for `in_app_byok` mode.
- How to use:
  1. Ensure at least one candidate run exists (recommended).
  2. Approve `request_synthetic_validation`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Review returned `job_id`, `winner_id`, and `score` (if auto-run).
- Where it fits in flow:
  - `experiment_run_completed -> validation_completed` (synthetic side).

#### `review_validation_readiness`
- What it does:
  - Evaluates whether a variant is ready for lab-only promotion or production-tier promotion.
  - Computes readiness from:
    - observed coverage (`coverage_obs`) and verified observed runs
    - synthetic validation result availability
    - configurable thresholds (`prod_min_coverage`, `min_verified_runs`, `min_synthetic_results`)
  - Returns explicit gate status (`observed_ready`, `synthetic_ready`) and a readiness state.
- How to use:
  1. Ensure the variant has at least one experiment run and at least one validation signal (recommended).
  2. Approve `review_validation_readiness`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Use returned `readiness_state` and `gates` to decide whether to move to posterior update/promotion.
- Where it fits in flow:
  - `validation_completed -> readiness review before posterior/promotion`.

#### `update_posterior_and_decisions`
- What it does:
  - Reads latest retrieval-backed metric for a candidate variant.
  - Recomputes posterior + decision outputs using current validation evidence and decision policy.
  - Persists a new metric row as a decision refresh artifact (linked to source metric id).
- How to use:
  1. Ensure variant has at least one retrieval-backed metric row.
  2. Approve `update_posterior_and_decisions`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Use returned `new_metric_id`, `posterior`, and `decision_action` for downstream policy decisions.
- Where it fits in flow:
  - `validation_completed -> posterior_updated`.

#### `recommend_next_action`
- What it does:
  - Uses the existing experiment orchestrator recommendation logic to propose the next constrained action (`run_variant`, `create_variant`, `stop`, etc.).
  - Persists the recommendation in experiment recommendations history.
  - Returns lightweight context for decision traceability (`latest_metric` decision fields + validation job counts).
- How to use:
  1. Ensure at least one run/metric exists for the experiment (recommended).
  2. Approve `recommend_next_action`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Review returned `recommendation.action`, `reason`, and confidence before approving follow-up actions.
- Where it fits in flow:
  - `posterior_updated -> next cycle planning`.

#### `promote_variant_lab`
- What it does:
  - Promotes a candidate variant for lab progression (not production publish).
  - Enforces policy checks before promotion:
    - variant must be non-control
    - latest decision metric must exist
    - `decision_action=promote_variant` when `require_promote_decision=true`
    - rejects if decision tier is already `prod` (must use prod path later)
  - Persists auditable records:
    - `analytics_events` (`event_type=variant_promoted_lab`)
    - `decision_events` (`policy_action=promote_variant_lab`)
- How to use:
  1. Ensure posterior update has run for the target variant.
  2. Approve `promote_variant_lab`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Use returned `analytics_event_id`/`decision_event_id` for traceability.
- Where it fits in flow:
  - `posterior_updated -> lab promotion decision`.

#### `promote_variant_prod`
- What it does:
  - Promotes a candidate variant to production tier only when observed-readiness gates are satisfied.
  - Enforces stricter checks than lab promotion:
    - non-control variant
    - observed readiness must pass (`coverage_obs` + verified observed runs)
    - optional policy gate `decision_action=promote_variant` (`require_promote_decision=true`)
  - Persists auditable records:
    - `analytics_events` (`event_type=variant_promoted_prod`)
    - `decision_events` (`policy_action=promote_variant_prod`)
- How to use:
  1. Execute `review_validation_readiness` and ensure `observed_ready=true`.
  2. Approve `promote_variant_prod`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Use returned event ids for governance logs and downstream publish workflows.
- Where it fits in flow:
  - `posterior_updated -> prod promotion decision (approval-gated)`.

#### `publish_copy_revision`
- What it does:
  - Publishes a copy revision to the underlying product description after prod promotion.
  - Enforces governance by default:
    - requires non-control variant
    - requires prior `variant_promoted_prod` event (`require_prod_promotion=true`)
  - Resolves a revision in order:
    - explicit `revision_id`
    - existing draft experiment revision linked to `source_variant_id`
    - auto-create revision from variant payload description
  - Applies publish effects:
    - updates product description
    - marks revision as `published`
    - writes audit events (`copy_revision_published`, `publish_copy_revision`)
- How to use:
  1. Ensure `promote_variant_prod` has executed for the target variant.
  2. Approve `publish_copy_revision`.
  3. Run `step` in `auto_execute_safe` mode.
  4. Verify returned `revision_id` and updated product description metadata.
- Where it fits in flow:
  - `prod promotion -> operational publish`.

### 3.3 Policy-as-code (enforcement stays system-side)

Implemented in v0:
- centralized `PolicyEnforcer` in `application/services/agent_runtime/policy.py`
- checks executed before capability execution:
  - capability allow-list per run
  - required input presence
  - action budget (`max_actions`)
  - variant-run budget (`max_variant_runs`)
- runtime now fails actions/runs with explicit policy errors when checks fail

Formalize enforcement checks used by both humans and agents:
- frozen snapshot required for retrieval-backed scoring
- baseline-first gating
- spend / run / query budget caps per cycle
- cost budget cap (`max_cost_usd`) before execution
- stop conditions (drift too high, validation disagreement, low support size)
- approval gates (optional):
  - promotion to “prod tier”
  - publishing copy revisions

### 3.4 Audit Log (`agent_actions` + `agent_events`)

Actions remain the mutable execution queue; events are immutable lifecycle records for replay/audit:
- `agent_id`, `agent_run_id`
- `capability_name`, `capability_version`
- `inputs_hash`, `outputs_hash`
- scope fields: `client_id`, `brand_id`, `product_id`, `experiment_id`
- protocol anchors: `snapshot_version`, `hypothesis_id`, `variant_id`
- `rationale`, `confidence`
- status: `proposed | approved | executed | rejected | failed`

Event stream is exposed via:
- `GET /agent-runs/{run_id}/events`
- filters:
  - `event_type=all|failed|policy|executed|command`
  - `status=all|proposed|approved|executing|executed|failed|rejected`
  - `capability_name`
  - `since`, `until`
  - `before`, `after`
  - `event_id`, `around`

Operator steering is exposed via:
- `POST /agent-runs/{run_id}/commands`
- `POST /agent-runs/{run_id}/commands/preflight`
- mutating commands: `approve`, `reject`, `retry`, `start`, `pause`, `cancel`, `step`
- non-mutating command receipts: `explain`, `focus`
- structured recovery command: `change_plan`
- command receipts are stored as immutable `operator_command_*` events with principal, action, tool, skill, effect, trace, and message context where available
- high-risk command preflight requires explicit confirmation in the operator chat before submission
- step commands require explicit confirmation before execution
- retry always requires explicit confirmation and emits `action_retry_proposed` for a new proposed action; the original failed action remains failed
- retry supports `same_action`, `last_safe_checkpoint`, and `create_recovery_action` strategies
- change-plan emits `action_recovery_proposed`; Interventions surfaces command-originated retry/recovery work
- operator chat summarizes command outcomes with resulting run/action state after execution
- command outcome summaries include artifact inspection guidance for metrics, variants, validation jobs, copy revisions, hypotheses, snapshots, and failures

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

### 4.4 LLM vs Deterministic Execution (Control Plane)

The agentic layer is intentionally hybrid:

- **LLM-backed capabilities** (non-deterministic output generation):
  - `generate_variants` (copy generation from loop evidence or cold-start context)
  - future expansion: adaptive planning/policy recommendation modules

- **Deterministic control-plane capabilities** (policy-enforced orchestration):
  - `freeze_retrieval_protocol`
  - `run_control_baseline`
  - `seed_hypotheses`
  - `run_variant`
  - approval/status transitions, budgets, and guardrails

Why this split:
- LLMs provide flexibility for creative hypothesis/copy generation.
- Deterministic execution keeps protocol guarantees (baseline-first, snapshot freeze, reproducibility).

In short:
- The agent can propose and reason.
- The platform decides what is allowed to execute and records exactly what happened.

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
