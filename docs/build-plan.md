# Build Plan: Intentionality Optimization Layer

**Status:** Pivot in progress  
**Goal:** Demo-ready brand‑discovery engine for LLM commerce

This plan aligns the codebase to the new architecture in `docs/architecture.md`.

---

## Status Overview

| Module | Status | Primary Gap |
|--------|--------|-------------|
| `intent/` | Partial | Single-intent only, limited intent signals |
| `intentionality/` | Functional | Needs richer LLM enrichment + batch pipeline |
| `alignment/` | Partial | Alignment summary in place; per-product scores still thin |
| `commerce/` | Functional | Intentionality enrichment in plan only (not adapter pipeline) |
| `memory/` | Partial | Still carries legacy naming + fields; needs intent-aware summaries |
| `conversation/` | Partial | Demo flow still uses legacy framing + values agent |
| `mcp/` | Partial | Tooling not aligned to discovery workflow |
| `api/` | Functional | Alignment endpoints now exist; schemas present |
| `web/` | Functional | Intent display + discoverability delta are live |

---

## Current Migration Findings (Code Scan → Plan Map)

### In Place
- Intentionality profiling module exists with LLM prompt + profile builder (`modules/intentionality/*`).
- Inferred intent model supports multi-goal + signals and is wired through API/UI (`modules/intent/*`, `api/routes/*`, `web/*`).
- Alignment summary + per-product alignment scores + reasoning are live (`modules/alignment/goal_alignment.py`, `api/routes/products.py`, `web/components/products/ProductReasoning.tsx`).
- Discovery endpoints live: `/intent/infer`, `/products/align`, `/products/profile`, `/products/enrich` (`api/routes/*`).
- UI shows inferred intent + discoverability delta (`web/components/intent/IntentDisplay.tsx`, `web/components/products/IntentionalityProfileCard.tsx`).
- UCP adapter stub exists (`modules/commerce/adapters/ucp/loader.py`).
- Legacy empowerment artifacts removed from schema/data/tools/UI (`shared/db/schema.sql`, `db/schema.sql`, `llm/tools.py`, `data/*.json`, `web/components/empowerment/ValuesPanel.tsx`).

### Still Partial
- Intentionality enrichment still missing in Shopify + Google Merchant adapter paths and batch pipeline (`modules/commerce/adapters/*`).
- Conversation flow still uses legacy clarification + “autonomy” phrasing (`modules/conversation/*`, `modules/values/*`).
- Embedding persistence + retrieval helpers are still missing (DB + repos + tests).
- Deterministic intent-output parsing tests still missing.
- Product model still carries `capabilities_enabled` + `intent_scores` directly (optional cleanup if you want strict IntentionalityProfile-only).

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
- [ ] Show catalog + research streams side-by-side with alignment scores
- [x] Disable catalog stream for `CATALOG_SOURCE=mock`

### Phase 3 — Protocol & Catalog Integration
- [x] Add UCP adapter stub + loader registration
- [ ] Enrich Shopify + Google Merchant adapters with intentionality profiles
- [ ] Batch enrichment pipeline + report output

### Phase 4 — Evaluation & Benchmarking
- [ ] Multi‑LLM evaluation harness (Gemini/OpenAI/Claude)
- [ ] Alignment score vs actual recommendation comparison
- [ ] “Discoverability lift” metric tracker

### Phase 5 — Hackathon Packaging
- [ ] 60–90s demo script + storyboard
- [ ] 3 before/after product examples
- [ ] Showcase protocol‑agnostic positioning (UCP/ACP)

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

- Intentionality profiling module exists and is integrated.
- Alignment scores + explanations appear in API + UI.
- Discovery‑focused endpoints operational.
- World‑B framing removed from README, UI, and API responses.
- Demo story shows before/after discoverability impact.
