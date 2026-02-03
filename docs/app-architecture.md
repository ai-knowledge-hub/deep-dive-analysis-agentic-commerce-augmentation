# App Architecture (Current + Planned)

This document describes the **current** architecture of the app and clearly labels
anything that is **planned but not built**.

---

## 1) High-Level System View

```
User (Next.js UI)
  ├─ Chat (Conversation)
  ├─ Alignment / Evidence
  ├─ Simulation
  ├─ Experiments
  └─ Admin (Skills, Clients, Brands)
          │
          ▼
FastAPI API Layer
  ├─ Conversation / Alignment / Evidence routes
  ├─ Simulation routes
  ├─ Experiment routes + Validation routes
  ├─ Brand / Product routes
  └─ Admin routes
          │
          ▼
Application Services
  ├─ Intent inference + goal clarification
  ├─ Alignment scoring + evidence analysis
  ├─ Simulation runner + optimizer + retest
  ├─ Experiment runner + orchestrator
  ├─ Validation logging + calibration rollups
  └─ Protocol readiness checks (UCP/ACP)
          │
          ▼
Infrastructure Layer
  ├─ LLM clients (Gemini/OpenRouter)
  ├─ SQLite database
  ├─ Protocol adapters (UCP/ACP readiness)
  └─ Skill prompt storage
```

---

## 2) Runtime Components

### Frontend (Next.js)
- Pages for **Chat**, **Alignment**, **Evidence**, **Simulation**, **Experiments**.
- Admin views for **skills** and **tenant selection** (via admin mode).

### Backend (FastAPI)
Key routes are grouped by module:
- Conversation + alignment + evidence
- Simulation (run, optimize, retest, lessons)
- Experiments (batteries, variants, runs, metrics, recommendations)
- Validation (manual logs + accuracy summaries)
- Analytics events ingestion (external events)
- Admin and tenant management

### LLM Providers
- **Gemini** and **OpenRouter** are supported providers.
- Optional **multi‑judge** evaluation via `JUDGE_PROVIDERS` (comma‑separated providers).

### Database
SQLite is the default persistence layer in current deployments.

---

## 3) Core Domains (Current)

### Conversation + Intent
**Purpose:** Understand user intent and contextual constraints.
- Intent inference and goal clarification.
- Stored as conversation sessions.

### Alignment
**Purpose:** Score how well products align with inferred intent.
- Uses a transparent, signal‑based approach.
- Hard category gate prevents category mismatches.

### Evidence
**Purpose:** Explain why winners appear and what signals matter.
- Evidence analysis complements alignment with open‑web context.

### Simulation
**Purpose:** Test scenarios, identify gaps, optimize copy, retest.
- Produces **lessons** that are stored per run.
- Protocol readiness (UCP/ACP) is surfaced during simulation results.

### Experiments
**Purpose:** Run query batteries against variants and track lab signals.
- Aggregated metrics include win rates, robust win rate, scores, and optional judge consensus.
- Beliefs are generated when a brand is attached.

### Validation + Calibration
**Purpose:** Log real‑world observations and track prediction accuracy.
- Manual validation logs.
- Brand‑level calibration rollups (verified runs + accuracy).

---

## 4) Data Model Snapshot (Current)

Key entities stored in SQLite include:
- **Clients, Brands, Products**
- **Conversation Sessions**
- **Simulation Runs + Simulation Lessons**
- **Query Batteries + Battery Queries**
- **Experiments, Variants, Runs, Metrics**
- **Brand Beliefs**
- **Experiment Validations + Calibration Rollups**
- **Analytics Events** (external event ingestion)
- **Skills + Skill History** (editable prompts)

---

## 5) System Boundaries and Contracts

### Inputs
- User queries (chat, simulation, experiments).
- Product catalog data (client/brand/product tables).
- Optional external events (`/analytics/events`).
- Manual validation logs (`/experiments/{id}/validations`).

### Outputs
- Alignment scores + explanations.
- Evidence signals and gap analysis.
- Simulation improvements and lessons.
- Experiment metrics and recommendations.
- Validation accuracy and unlock status.

---

## 6) Validation Sources (Current)

**Built now**
- **Manual validation logs** (operator‑entered).
- **Analytics events ingestion** endpoint for external signals.

**Planned (not built)**
- Direct GA4 ingestion pipeline and mapping.
- Automated live‑LLM verification harness.

---

## 7) Self‑Learning / Distillation (Current vs Planned)

**Built now**
- **Simulation lessons** are stored and retrievable per client.
- **Brand beliefs** are generated from experiment results.

**Planned (not built)**
- Distillation of lessons across simulations into reusable heuristics.
- Categorization by domain/vertical for reuse in intent inference.
- Automatic feedback loop that updates prompts/scoring based on validated outcomes.

---

## 8) Protocol Readiness (Current)

The system computes **protocol readiness** for UCP/ACP as part of simulation output.
This surfaces missing fields or readiness issues but does **not** execute transactions.

**Planned (not built)**
- Full protocol compliance validation + transaction flows.

---

## 9) Observability + Audit (Current)

**Built now**
- Replay logging for simulation runs.
- Skill history audit trail.

**Planned (not built)**
- Enterprise‑grade audit trails, RBAC, and compliance tooling.

