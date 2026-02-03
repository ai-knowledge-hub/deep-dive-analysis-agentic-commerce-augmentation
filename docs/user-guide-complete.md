# User Guide (Current Features)

**Version:** 1.1  
**Date:** 2026-02-03  
**Audience:** Brand marketing teams, ecommerce teams, and analysts

This guide reflects **only what exists in the current codebase**. Planned items are labeled.

---

## 1) What This App Does (Today)

The app helps you make product descriptions **more legible to AI agents** by:
- inferring intent,
- scoring alignment,
- explaining gaps,
- testing improvements in simulation,
- screening variants in experiments,
- and validating results with manual logs.

It does **not** guarantee production rankings. Results are **lab signals**.

---

## 2) Primary Pages (UI)

### Chat (Conversation)
Start with a user query. The app infers intent, asks clarifying questions, and stores a session.

### Alignment
Shows inferred intent + alignment scores for candidate products.

### Evidence
Explains why winners rank and what signals are missing.

### Simulation
Run a scenario, view gap analysis, optimize copy, and retest.

### Experiments
Build query batteries, create variants, run experiments, and view metrics.
Validation progress and unlock status are shown here.

---

## 3) Core Workflows (Short)

For full end‑to‑end flow, see `docs/app-workflows.md`.

### A) Manual Flow
Chat → Alignment → Evidence → Simulation → Retest → Lessons

### B) Lab Flow
Query Battery → Experiment → Run Variants → Metrics → Beliefs → Next Test

### C) Validation Flow
Log validation results → Accuracy updates → Unlock Pattern Insights

---

## 4) Experiments (What’s Shipped)

**You can:**
- Create batteries and variants.
- Run experiments and see win rates.
- See robust win rate (wins under both semantic + keyword judges).
- Optionally enable multi‑judge consensus via `JUDGE_PROVIDERS`.
- Log validations and track prediction accuracy.

**You cannot (yet):**
- Automatically verify with live LLM platforms.
- Automatically ingest GA4 data.

---

## 5) Simulation (What’s Shipped)

**You can:**
- Run a scenario with competitors.
- See gap analysis + protocol readiness hints.
- Optimize a product description.
- Retest and see lift.
- Store and list lessons.

**Planned (not built):**
- Distill lessons into reusable heuristics across domains.

---

## 6) Validation (What’s Shipped)

**Built now**
- Manual validation logging per experiment.
- Brand‑level accuracy rollups.

**Planned**
- Automated GA4 ingestion.
- Live LLM verification harness.

---

## 7) Admin + Skills

Admin users can edit skills used by signal extraction and optimization.
All edits are stored with history for auditability.

---

## 8) Deployment Notes

Current deployments are split:
- FastAPI backend on a Python runtime.
- Next.js frontend on Vercel.

Planned: full Vercel deployment using the Python runtime (requires serverless adaptation).

---

## 9) Troubleshooting

- If results are missing, ensure a **client_id** is set.
- If experiments show no metrics, run at least one variant.
- If Pattern Insights are locked, log validation results.

