# Experiment Orchestrator Architecture (Stats + ML + Thompson)

**Status:** ✅ Implemented  
**Scope:** Statistical analysis + ML patterning + Thompson sampling with rule-based fallbacks

---

## Overview

The orchestrator is a **decision engine** that recommends the next best action
for an experiment. It combines:

- **Statistical comparisons** (effect size + confidence)
- **ML pattern recognition** (learned from historical experiments)
- **Thompson sampling** (explore vs. exploit)
- **Rule-based fallbacks** (when data is sparse)

This keeps the lab loop explainable while still benefiting from ML signals.

---

## Decision Flow (Current)

```
START: suggest_next_test(experiment_id, client_id, user_id)
  |
  |-- Load experiment + variants + metrics + beliefs
  |
  |-- If no variants → Recommend: "Create baseline"
  |
  |-- If only 1 variant → Recommend: "Create hypothesis variant"
  |
  |-- If any variant untested → Recommend: "Run untested variant"
  |
  |-- Statistical comparison (top 2 variants)
  |     └─ If clear winner → Recommend: "Stop / Deploy winner"
  |
  |-- ML recommendation (if historical data exists)
  |     └─ Suggest new hypothesis variant
  |
  |-- Thompson sampling
  |     └─ Explore uncertain variant vs. exploit best
  |
  |-- Fallback → "Run weakest variant" (increase evidence)
```

---

## Outputs

Each recommendation includes:

- **action**: `run_variant` / `create_variant` / `create_baseline` / `stop`
- **reason**: human-readable rationale
- **confidence**: 0–1
- **payload**: suggested variant template (if applicable)
- **ml_prediction** (optional)
- **exploration_score / exploitation_score** (optional)

---

## Lab Loop Binding

The orchestrator integrates with:

- **Experiment Runner** → executes suggested runs
- **Belief Update Agent** → stores belief summaries + evidence links
- **UI (Experiments page)** → renders “Next Test” card with action + reason

---

## Notes

- The ML engine uses historical experiment data when available.
- If the training pipeline is not wired or data is sparse, the orchestrator
  falls back to safe, explainable rules.

