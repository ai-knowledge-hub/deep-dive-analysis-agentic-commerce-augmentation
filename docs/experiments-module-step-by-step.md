# Experiments Module — Step-by-Step (Validation-First)

This document explains how the Experiments module works **now**. It reflects the current “screening + validation” approach: lab results are directional signals, and real‑world validation is required before pattern insights are unlocked.

---

## 1) What the Experiments module is (and is not)

**What it is:** a lab system that screens copy variants against a query battery, then **tracks validation accuracy** over time.  
**What it is not:** a guaranteed predictor of production ranking.

Experiments produce **lab signals** (win rates, scores, judge consensus) and require **validation logs** before unlocking pattern insights.

---

## 2) Core objects and how they relate

- **Query Battery**: curated/generated set of intent queries.
- **Experiment**: ties a product + battery + hypothesis (+ competitor policy).
- **Variant**: a version of the product (often copy variants).
- **Experiment Run**: one simulation per query per variant.
- **Experiment Metric**: aggregated stats from runs (win rates, averages).
- **Validation**: a manual record of what actually appeared in a live system.
- **Calibration**: brand‑level rollup of validation accuracy.

---

## 3) Step‑by‑step flow

### Step 1 — Build a Query Battery
Use the **Query Battery Builder** to define or generate queries. Only **enabled** queries are used during experiments.

### Step 2 — Create an Experiment
Define:
- **Product** to test
- **Battery** of queries
- **Hypothesis** (optional)
- **Competitor policy** (optional)

The experiment starts in **draft** and can be scheduled later.

### Step 3 — Add Variants
Add a **control** and one or more **variants** (payload can override name/description/metadata).

### Step 4 — Run the Experiment (per variant)
For each enabled query, the system:
1. Builds the **variant product** (name/description/metadata overrides).
2. Runs a **simulation** (with auto‑competitors if enabled).
3. Collects:
   - `winner_id` and `scores` (semantic)
   - `winner_id_keyword` and `scores_keyword` (keyword)
   - `protocol_readiness` (if present in simulation output)
4. Optionally runs **pairwise judges** against the top competitor (if `JUDGE_PROVIDERS` is set).
5. Stores an **experiment run** record for that query.

### Step 5 — Aggregate Metrics
After all queries finish, metrics are computed and saved:
- `total_runs`
- `wins`, `win_rate`
- `wins_keyword`, `win_rate_keyword`
- `wins_robust`, `win_rate_robust`  
  *(robust = wins under both semantic + keyword winners)*
- `avg_score`, `avg_score_keyword`
- `avg_protocol_readiness_score`
- `judge_consensus_win_rate` (if multi‑judge enabled)
- `judge_provider_count`

### Step 6 — Belief Update (if brand is attached)
If the experiment has a `brand_id`, the system records a **brand belief** with:
- the hypothesis,
- lab metrics,
- per‑query run evidence,
- variant metadata.

These beliefs are **soft‑gated** until validation thresholds are met.

### Step 7 — Next‑Test Recommendation
The **Next Test** engine can suggest follow‑up variants based on recent results and (where available) ML predictions.

### Step 8 — Log Validation Results (Manual)
Use the **Validation Progress** form to log live observations:
- platform (ChatGPT/Gemini/Perplexity/etc.)
- query tested
- products shown (free‑form list)
- observed winner variant (optional)
- observed position (optional)
- notes

Accuracy is computed when an **observed winner variant** is provided:
- `is_correct = true` if observed winner == lab winner
- `is_correct = false` if not

### Step 9 — Unlock Pattern Insights
Pattern insights (brand beliefs) remain locked until:
- **≥ 10 verified runs**, and
- **≥ 75% accuracy**

Progress is displayed on the Experiments page.

### Step 10 — Calibration Rollup
Every validation updates a **brand‑level calibration record**:
- verified runs
- accuracy
- total/correct counts

This is surfaced in the UI as **Brand accuracy** and through the prediction‑accuracy API.

---

## 4) Where the metrics come from

**Per query (simulation result):**
- `winner_id`, `scores`
- `winner_id_keyword`, `scores_keyword`
- `protocol_readiness` (if emitted)
- optional multi‑judge pairwise consensus

**Aggregated metrics:** stored on each experiment run as described in Step 5.

---

## 5) Experiment validation rules (soft gate)

- **Lab runs** always execute.
- **Pattern Insights** unlock only with **10+ verified** and **≥75% accuracy**.
- UI clearly labels results as **Lab Signal** until unlocked.

---

## 6) Configuration knobs

- **`JUDGE_PROVIDERS`** (env): comma‑separated list of model providers to enable multi‑judge consensus.  
  If empty, no pairwise judging is executed and consensus metrics are `null`.

---

## 7) Key API endpoints (current)

**Experiments**
- `POST /experiments` — create experiment
- `POST /experiments/{id}/variants` — add variant
- `POST /experiments/{id}/run` — run a variant
- `GET /experiments/{id}/runs` — list query runs
- `GET /experiments/{id}/metrics` — list metrics
- `GET /experiments/{id}/recommendations` — list next‑test recs

**Validation**
- `POST /experiments/{id}/validations` — log a validation record
- `GET /experiments/{id}/validation-summary` — experiment summary
- `GET /brands/{id}/prediction-accuracy` — brand accuracy rollup

**Analytics**
- `POST /analytics/events` — ingest external events (e.g., GA4)

---

## 8) UI touchpoints (now)

- **Experiments page** shows:
  - lab disclaimer banner
  - latest metrics
  - validation progress + unlock status
  - locked Pattern Insights until validation thresholds
  - per‑experiment Next Test recommendations

---

## 9) What to tell users (current narrative)

> “Experiments provide **lab signals** for LLM‑friendliness.  
> Validation logs are required to confirm real‑world performance.”

---

## 10) Quick checklist to verify end‑to‑end behavior

1. Create experiment → add variants → run variant.
2. Metrics appear (win rates + robust win rate + avg score).
3. Pattern Insights locked until validations exist.
4. Log validation → accuracy and progress update.
5. After 10+ verified and ≥75% accuracy → Pattern Insights unlock.
