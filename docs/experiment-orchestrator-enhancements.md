# Experiment Orchestrator Enhancements (Stats + ML + Thompson)

**Date:** 2026-01-30  
**Status:** ✅ Implemented  
**Scope:** Statistical analysis, ML pattern recognition, Thompson sampling

---

## Overview

The orchestrator now combines three signals to recommend the next experiment action:

1. **Uncertainty estimation** (win-rate Δ + CI + evidence strength)
2. **ML recommendations** (pattern mining over historical experiments)
3. **Thompson sampling** (explore vs. exploit)

Fallback rules apply when data is sparse.

---

## What’s Implemented

### 1) Uncertainty Estimation

- Compares top variants for win‑rate difference
- Detects diminishing returns
- Enables **stop / deploy winner** recommendations

### 2) ML Pattern Recognition

- Learns from historical experiments
- Suggests a new hypothesis variant with predicted lift + rationale
- Uses brand beliefs as additional context

**Note:** Training is lazy by default; the ML engine returns a safe fallback
when historical data is missing. Hooking a trainer is optional (see quick‑start).

### 3) Thompson Sampling

- Balances exploration vs. exploitation
- Produces `exploration_score` / `exploitation_score`
- Can recommend running an uncertain variant to gather evidence

---

## Output Fields (API)

Recommendations include:

- `action`, `reason`, `confidence`
- `statistical_analysis` (optional)
- `ml_prediction` (optional)
- `exploration_score`, `exploitation_score` (optional)

---

## UI Status

The Experiments page shows the **Next Test** card (action + rationale).
Advanced ML/Thompson fields are currently available via API and can be surfaced
in UI when desired.
