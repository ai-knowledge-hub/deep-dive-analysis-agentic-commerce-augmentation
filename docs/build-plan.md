# Build Plan: AI Discoverability Simulation Sandbox

**Status:** Pivot in progress
**Goal:** Demo-ready simulation sandbox where brands can test products, see who wins, understand why, and optimize until they win.

**The user problem we solve:**
> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

**The core loop:**
```
SET UP SCENARIO → SIMULATE → SEE RESULTS → OPTIMIZE → RE-TEST
      ↑                                                  │
      └──────────────────────────────────────────────────┘
```

This plan aligns the codebase to the simulation sandbox architecture in `docs/architecture.md`.

---

## Status Overview

| Module | Status | Simulation Sandbox Gap |
|--------|--------|------------------------|
| `intent/` | Partial | Inference works; needs competitive scenario support |
| `intentionality/` | Functional | Profiling works; needs gap analysis output |
| `alignment/` | Functional | Scoring works; needs "why you lost" explanation |
| `commerce/` | Functional | Adapters work; needs dynamic product input |
| `api/` | Functional | Discovery endpoints live; needs simulation endpoints |
| `web/` | Functional | Intent + alignment UI live; needs simulation sandbox UI |

---

## Current State

### In Place
- Intentionality profiling module with LLM enrichment (`modules/intentionality/*`)
- Intent inference with multi-goal support (`modules/intent/*`)
- Alignment scoring with per-product explanations (`modules/alignment/*`)
- Discovery endpoints: `/intent/infer`, `/products/align`, `/products/profile`, `/products/enrich`
- Before/after discoverability comparison UI
- Clerk auth scaffolded

### Missing for Simulation Sandbox
- **Scenario setup**: Let user input query + their product + competitors
- **Competitive simulation**: Score multiple products, pick winner
- **Gap analysis**: "Why you lost" explanation
- **Optimization suggestions**: Specific changes to make
- **Re-test loop**: Apply changes and immediately re-score
- **Simulation sandbox UI**: The core user experience

---

## Phase 1 — Core Discovery Engine (P0)

**Goal:** Produce intent → alignment → recommendation pipeline with explanations.

### 1.1 Intent Inference Engine
- Expand `modules/intent/` to output `InferredIntent`, `IntentSignals`, `confidence`.
- Support multi‑goal inference (primary + secondary goals).
- Add tests for deterministic intent inference output parsing.

### 1.2 Intentionality Profiling (NEW)
- Create `modules/intentionality/`:
  - `domain.py` (IntentionalityProfile)
  - `profiling.py` (spec → capability/outcome transform)
  - `prompts.py` (LLM prompt for enrichment)
- Integrate into commerce pipeline (RawOffer → IntentionalityProfile → Product).

### 1.3 Alignment Scoring
- Replace empowerment scoring with `AlignmentScore`.
- Score products against inferred intent using embeddings + signals.
- Add alignment explanation text for UI demo.

### 1.4 Embeddings + Storage
- Persist goal/product embeddings in SQLite.
- Add retrieval helpers for alignment scoring.
- Add end‑to‑end tests: goal → embedding → DB → alignment.

---

## Phase 2 — API + Demo (P0)

**Goal:** Show the discovery story end‑to‑end in the UI.

### 2.1 API Endpoints
- Add:
  - `POST /intent/infer`
  - `POST /products/align`
  - `POST /products/profile`
  - `POST /products/enrich`
- Remove legacy response fields (empowerment/guardrails/World‑B wording).

### 2.2 Demo UI
- Replace World‑B UI with intent‑alignment demo flow:
  - Query → inferred intent → aligned products → explanations
- Add “discoverability delta” visualization (before/after enrichment).
- Add dual-stream discovery display (catalog + research) with alignment scores.
- Disable catalog stream for `CATALOG_SOURCE=mock` to avoid misleading recommendations.

---

## Phase 2–5 Execution Checklist

### Phase 2 — API + Demo
- [x] Add `/intent/infer`, `/products/align`, `/products/profile`, `/products/enrich`
- [x] Add Pydantic request/response schemas for discovery endpoints
- [x] Show intent label + confidence in UI
- [x] Show alignment score alongside intentionality profile
- [x] Wire “discoverability delta” panel (before/after comparison)
- [x] Surface per-product alignment explanations in UI cards
- [x] Show catalog + research streams side-by-side with alignment scores
- [x] Disable catalog stream for `CATALOG_SOURCE=mock`
---
### Phase 2.5 — Evidence-First Demo Layer (Done)
- [x] Add evidence analysis endpoint (`POST /evidence/analyze`)
- [x] Add representation optimization endpoint (`POST /representation/optimize`)
- [x] Add verification endpoint (`POST /recommendation/verify`)
- [x] Create demo evidence sets (3–5 real products)

### Phase 3 — Simulation Sandbox (P0 - HACKATHON CRITICAL)

**Goal:** The core user experience—test, see who wins, understand why, optimize, re-test.

- [ ] Add simulation scenario endpoint (`POST /simulation/run`)
  - Input: query + user product + competitors
  - Output: intent, scores, winner, gap analysis
- [ ] Add optimization suggestion endpoint (`POST /simulation/optimize`)
  - Input: scenario_id, product_id
  - Output: before/after with predicted score delta
- [ ] Add re-test endpoint (`POST /simulation/retest`)
  - Input: scenario_id, optimized description
  - Output: new score, is_now_recommended, lift
- [ ] Build gap analysis logic ("why you lost")
  - Missing capabilities
  - Hidden strengths
  - Specific suggestions
- [ ] Build simulation sandbox UI
  - Scenario setup form
  - Results dashboard with competitive view
  - Gap analysis panel
  - Optimization preview
  - Re-test button with instant feedback

### Phase 4 — Verification & Benchmarking
- [ ] Multi‑LLM verification harness (Gemini required for hackathon)
- [ ] Alignment score vs actual recommendation comparison
- [ ] "Discoverability lift" metric tracker

### Phase 5 — Hackathon Packaging
- [ ] 60-second demo script showing simulation loop
- [ ] 3 compelling before/after examples with clear lift
- [ ] Pitch: "See what the LLM sees. Fix what's broken. Test until you win."

---

## Phase 3 — Protocol & Catalog Integration (P1)

**Goal:** Prove protocol‑agnostic discovery.

### 3.1 Adapters
- Implement UCP adapter (discovery + item normalization).
- Harden Shopify + Google Merchant adapters for intentionality enrichment.

### 3.2 Intentionality Batch Enrichment
- Run catalog enrichment pipeline offline.
- Output “intent legibility report” per catalog.

---

## Phase 4 — Evaluation & Benchmarking (P1)

**Goal:** Prove that alignment predicts real LLM recommendations.

- Add multi‑LLM evaluation harness (Gemini, OpenAI, Claude).
- Compare alignment score vs actual recommendation outcomes.
- Track “discoverability lift” metric across A/B variants.

---

## Phase 5 — Hackathon Packaging (P0)

**Goal:** Demo‑ready pitch and visuals.

- Short narrative demo script (60–90 sec).
- Showcase 3 “before/after” product examples.
- Highlight protocol‑agnostic compatibility (UCP/ACP).

---

## Completion Criteria

**The demo must show the complete simulation loop:**

1. ✅ User sets up scenario (query + product + competitors)
2. ✅ System shows who wins and why
3. ✅ User sees "why I lost" gap analysis
4. ✅ User applies suggested optimization
5. ✅ User re-tests and sees improvement

**Technical criteria:**
- [ ] Simulation endpoints operational (`/simulation/run`, `/simulation/optimize`, `/simulation/retest`)
- [ ] Gap analysis logic produces actionable "why you lost" output
- [ ] Simulation sandbox UI complete
- [ ] 3 compelling demo scenarios ready
- [ ] 60-second demo script polished

**The pitch must land:**
> "See what the LLM sees. Fix what's broken. Test until you win."
