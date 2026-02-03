# App Workflows (Current + Planned)

This document consolidates **all workflows** and shows how they connect.  
Only **existing functionality** is described as current. Anything not built is labeled **Planned**.

---

## 1) End‑to‑End Map (How Workflows Connect)

```
Chat / Conversation
   └─ Intent + Goals
         ├─ Alignment
         │    └─ Evidence
         │         └─ Simulation
         │              ├─ Optimize + Retest
         │              └─ Lessons (stored)
         └─ Experiments
              ├─ Query Battery
              ├─ Variants
              ├─ Runs + Metrics
              ├─ Beliefs (soft‑gated)
              └─ Next‑Test Recommendations

Validation (manual + analytics events)
   └─ Prediction Accuracy + Unlock Status
```

---

## 2) Conversation → Alignment → Evidence (Manual Flow)

**Purpose:** Understand intent and explain why products win or lose.

**Steps:**
1. User submits a query in Chat.
2. Intent inference + goal clarification runs.
3. Alignment page shows inferred intent + scores.
4. Evidence page explains why winners rank and highlights gaps.

**Current outputs:**
- Intent + clarified goals.
- Alignment scores + explanations.
- Evidence signals and “why they win.”

---

## 3) Simulation Workflow (Manual Lab)

**Purpose:** Test a scenario and optimize copy before changes go live.

**Steps:**
1. Run a simulation with a query and product(s).
2. System produces intent, scores, gaps, and protocol readiness.
3. User can optimize copy (guided by missing signals).
4. Retest optimized copy and compare lift.
5. Lessons are stored for that simulation run.

**Current outputs:**
- Gap analysis + suggested improvements.
- Optimized copy (optional).
- Retest results and lift summary.
- Stored **simulation lessons**.

---

## 4) Experiments Workflow (Lab Mode)

**Purpose:** Screen variants across a query battery and track lab signals.

**Steps:**
1. Build a **Query Battery** (generate + curate queries).
2. Create an **Experiment** (product + battery + hypothesis).
3. Add **Variants** (control + copy variants).
4. Run the experiment per variant.
5. Aggregate metrics (win rates, robust win rate, scores, judge consensus).
6. Generate **Beliefs** for the brand (soft‑gated).
7. Use **Next‑Test** recommendations to continue iteration.

**Current outputs:**
- Win rates + robust win rate.
- Optional multi‑judge consensus (if `JUDGE_PROVIDERS` is set).
- Brand beliefs (locked until validation thresholds are met).

---

## 5) Validation Workflow (External Reality Check)

**Purpose:** Validate lab predictions against external observations.

### Current validation sources
1. **Manual validation logs** (operator enters observed results).
2. **Analytics events ingestion** (`/analytics/events`) for external signals.

### What we measure today
- **Verified runs**: validations with a known observed winner.
- **Accuracy**: percent of lab winners that match observed winners.
- **Unlock status**: pattern insights unlock at **10+ verified** and **≥75% accuracy**.

### Planned (not built)
- Automatic GA4 ingestion + mapping to experiments.
- Automated live‑LLM verification harness.

---

## 6) Self‑Learning / Distillation Workflow

**Purpose:** Reuse learnings to improve future inference.

### Current (built)
- **Simulation lessons** are stored per run and retrievable.
- **Brand beliefs** are generated from experiment results.

### Planned (not built)
- Distill lessons into reusable heuristics.
- Categorize by domain/vertical.
- Feed distilled lessons into intent inference and query battery generation.

---

## 7) Protocol Readiness Workflow

**Purpose:** Surface non‑copy readiness issues (UCP/ACP).

**Current**
- Readiness scores are generated during simulation runs.
- Issues are surfaced as part of “why you lost” analysis.

**Planned (not built)**
- Full protocol validation and transaction flows.

---

## 8) Deployment Workflow

### Current deployment path
1. Run **FastAPI** backend (local or cloud runtime).
2. Run **Next.js** frontend (local or Vercel).
3. Configure environment variables for LLM provider + Clerk.

**Supported today**
- Backend hosted on any Python‑compatible platform (e.g., Railway, Render, VPS).
- Frontend hosted on Vercel.

### Planned (not built)
- **Full Vercel deployment** using the Python runtime for FastAPI.
  - Requires serverless adaptation and SQLite replacement or external DB.

---

## 9) Admin + Skill Editing Workflow

**Purpose:** Adjust skill prompts used by signal extraction and optimization.

**Steps:**
1. Open Admin → Skills.
2. Edit skill content.
3. Changes are stored in `skills` with a history trail in `skills_history`.

---

## 10) Quick Validation Checklist

1. Run a simulation → store lessons.
2. Run an experiment → metrics appear.
3. Log validation → accuracy updates.
4. Pattern insights remain locked until thresholds.
5. Multi‑judge metrics appear only when `JUDGE_PROVIDERS` is set.
