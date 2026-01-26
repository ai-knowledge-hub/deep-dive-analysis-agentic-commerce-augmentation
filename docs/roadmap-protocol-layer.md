# Roadmap: Protocol Layer Simulation + Verification

**Purpose:** Close the gap between inference-based discovery and protocol-based commerce (ACP/UCP).

This roadmap translates the Phase 6–9 additions in `docs/build-plan.md` into concrete milestones.

---

## Phase 1 — Protocol Simulation (P0/P1)

**Goal:** Simulate ACP/UCP discovery in parallel with current inference loop.

### Deliverables
- Mock ACP product feed endpoint (JSON → ranked results).
- Mock UCP discovery endpoint (query + filters → structured results).
- Intent → protocol query translator.
- Protocol preview UI: “what the agent sees” from feed/manifest.

### Success signals
- One scenario shows different outcomes between web‑inference and protocol‑feed paths.
- Gap analysis includes protocol field misses (capabilities, availability, enable_checkout).

---

## Phase 2 — Real Verification (P0/P1)

**Goal:** Compare simulated winners vs real outcomes.

### Deliverables
- One live LLM verification route (ChatGPT/Perplexity/Gemini).
- Stored verification outcomes per simulation run.
- Accuracy summary: predicted winner vs actual.

### Success signals
- `prediction_accuracy` tracked across runs.
- “Confidence” badge updates based on verification history.

---

## Phase 3 — Brand Voice + Authenticity (P1)

**Goal:** Preserve brand identity and avoid misleading claims.

### Deliverables
- Brand DNA model (tone + vocab + value positioning).
- Voice adherence score per rewrite.
- Authenticity checks for capability claims.

### Success signals
- Optimizations provide >1 brand‑safe variant.
- Rewrites flagged when claims aren’t supported by specs.

---

## Phase 4 — Competitive Intelligence (P1)

**Goal:** Automated competitive context.

### Deliverables
- Competitor auto‑discovery from evidence + intent overlap.
- Share‑of‑voice tracking per intent cluster.
- “Why they win” extracted patterns dashboard.

### Success signals
- Each scenario includes top competitors without manual input.

---

## Phase 5 — Meta‑Learning & Gap Intelligence (P1/P2)

**Goal:** Learn from runs to improve inference + surface market gaps.

### Deliverables
- Cross‑simulation pattern detection.
- Intent archetype library.
- Catalog gap analysis (“missing intent cluster X”).

### Success signals
- At least 3 recurring intent archetypes surfaced in UI.

---

## Dependencies

- Multi‑tenant scoping (client/brand/product) is already in place.
- Simulation sandbox API + UI operational.
- Evidence/intentionality modules reusable for protocol simulation.

---

## Owner’s Checklist

- [ ] ACP feed mock + mapping
- [ ] UCP discovery mock + mapping
- [ ] Verification route (1 platform)
- [ ] Calibration scorecard
- [ ] Brand DNA extraction
- [ ] Authenticity guardrails
- [ ] Competitor auto‑discovery
- [ ] Intent archetype library
