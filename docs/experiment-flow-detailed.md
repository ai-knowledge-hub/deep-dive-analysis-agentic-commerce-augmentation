# Experiment Flow (Detailed)

This document defines the implemented experiment protocol for copy optimization in the lab.

## 1) Objective and Unit

Objective:
- optimize product copy for discoverability and intent-fit.

Unit of analysis:
- `(query, snapshot_version, copy_variant)`.

Important:
- this is a lab decision-support system, not a guaranteed production ranking predictor.

## 2) Protocol Stages (Implemented)

1. `battery_ready`
2. `retrieval_snapshots_ready`
3. `baseline_scored`
4. `hypotheses_ready`
5. `variants_ready`
6. `experiment_run_completed`
7. `validation_completed`
8. `posterior_updated`

These are exposed in execution state and surfaced in Experiments UX.

## 3) Frozen Retrieval Protocol

For retrieval-backed experiments:
- the system creates a frozen retrieval snapshot set for enabled battery queries,
- stores it as `snapshot_version = N`,
- reuses that same snapshot set across variant runs.

This avoids time drift and ensures fair comparison across variants.

If enabled query IDs change, a new snapshot version is created.

## 4) Baseline Gate

In retrieval-backed mode:
- non-control variants cannot run until a control baseline is scored for the active `snapshot_version`.

This enforces a true baseline-first protocol.

## 5) Hypothesis Model

Hypotheses are first-class records:
- persisted per experiment and snapshot version,
- derived from baseline deltas (top missing winner signals) when needed,
- linked to variants via `hypothesis_id`,
- carried into run rows and UI.

Hypothesis statement structure is normalized as:
- `if`
- `then`
- `for`

## 6) Variant Generation Paths

Supported paths:
1. Manual authoring
2. Simulation prefill
3. Loop evidence generation
4. Cold-start generation (`bottom_up`, `top_down`, `both`)

Loop evidence generation uses reliability ordering:
- `validation > experiment > simulation`.

Generated variants can carry hypothesis linkage metadata.

## 7) Run and Metrics

Each run persists protocol context:
- `execution_mode`
- `retrieval_summary`
- `snapshot_version`
- `hypothesis_id` (if linked)

Metrics include standard run KPIs plus protocol fields:
- `snapshot_version`
- `posterior` (when updated)
- `decision_action`
- `decision_policy_version`
- `decision_inputs` (persisted for reproducibility)
- `decision_outputs` (persisted for reproducibility, includes weights and promotion tier)

## 8) Validation and Unified Evidence

Validation remains centralized in Validation module:
- synthetic signal
- observed signal

Experiment flow consumes validation summaries and uses them in closed-loop iteration.

## 9) Bayesian Update and Decision

For hypothesis-linked candidate runs, posterior updates are computed and persisted.

Decision action is derived from a **versioned decision policy** that combines:
- experiment outcomes (retrieval-backed deltas)
- synthetic validation outcomes (validation jobs/results)
- observed validation outcomes (manual observed logging)

The policy persists its full inputs/outputs into metrics for auditability and reproducibility.

Current policy shape (summary):
- evidence is normalized into `effect ∈ [-1, +1]` and `reliability ∈ [0, 1]`
- combined score uses reliability-adjusted contributions (`effect * sqrt(reliability)`)
- action thresholds are applied on a normalized likelihood `[0, 1]`:
  - `>= 0.75` -> `promote_variant`
  - `>= 0.45` -> `iterate_variant`
  - else -> `reject_hypothesis`
- promotion is tiered:
  - `lab` tier can proceed in loop
  - `prod` tier requires minimum observed coverage

Implementation note:
- `decision_policy_version`, `decision_inputs`, and `decision_outputs` are persisted per metrics row.

These actions are visible in metrics and support step-8 iteration.

## 10) Transparency Surfaces

API:
- `GET /experiments/{experiment_id}/execution-state`
- `GET /experiments/{experiment_id}/retrieval-snapshots`
- `GET /experiments/{experiment_id}/hypotheses`

UI:
- protocol snapshot status
- human-readable hypothesis labels
- expandable hypothesis details (`if/then/for`)
- posterior and decision action per tested variant

## 11) Practical Operating Pattern

For a new product:
1. Build and save battery queries.
2. Run control in retrieval-backed mode (creates and freezes snapshot set).
3. Inspect seeded hypotheses.
4. Generate/create candidate variants linked to hypotheses.
5. Run candidates on same snapshot version.
6. Validate synthetic + observed.
7. Use posterior decision action to promote, iterate, or reject.
