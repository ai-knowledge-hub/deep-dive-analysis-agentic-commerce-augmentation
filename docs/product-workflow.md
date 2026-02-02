# Product Workflow: Automated Lab Loop + Protocol Readiness

**Purpose**: Describe the v1 user journey as an **automated lab loop** centered on
chat → evidence → simulation → experiments.

---

## Overview

The product has two **modes** in v1:

### Manual Mode (Guided by Chat)

```
CHAT → ALIGNMENT → EVIDENCE → SIMULATION → LESSONS → OPTIMIZE → RE‑TEST
   ↑                                                     │
   └─────────────────────────────────────────────────────┘
```

### Lab Mode (Automated Loop)

Lab mode turns experimentation into a repeatable loop:

```
WORLD STATE → HYPOTHESIS → BATTERY → RUN → ANALYZE → BELIEF → NEXT TEST
```

To make this repeatable, we attach a per‑product **query battery** and run structured experiments:

- **Hypothesis**: created by user or Lab Operator chat.
- **Auto battery**: Lab mode auto‑generates batteries from hypothesis + product.
- **Edit battery**: enable/disable queries, adjust weights, review coverage metrics.
- **Variants**: control + hypothesis variant (auto‑created in Lab mode).
- **Run battery** against each variant to compare win‑rate and score lift.
- **Belief update**: results generate a belief with evidence links.
- **Next test**: orchestrator recommends the next run or variant.

---

## Lab Operator (Chat)

The chat doubles as a **Lab Operator** for experiments:

- Ask “Why did Variant B win?” → summary + belief evidence
- Ask “Run next test” → orchestrator recommendation + run confirmation
- Ask “What if we change pricing?” → hypothesis template

Quick commands:

```
/lab next
/lab why
/lab belief
/lab what if {json}
```

---

## Simulation Sandbox

### Core Loop

1. **Scenario Setup**: inferred intent + your product + competitors
2. **Run Simulation**: LLM‑style intent inference + alignment scoring
3. **Why You Lost**: missing framing, context fit, outcome language (signals from skill)
4. **Optimize**: suggested copy rewrite + tone confirmation
5. **Re‑test**: verify lift

**Note:** Signal deltas and missing concepts are generated via the
**Signal Extraction skill** stored in the DB and editable in Admin.

### API Endpoints

```
POST /simulation/run
  Input: { query, products[] }
  Output: { run_id, result: { intent, scores, winner_id, gap_analysis, protocol_readiness, tone } }

POST /simulation/optimize
  Input: { run_id, product_id, tone? }
  Output: { optimized: { before, after }, gap }

POST /simulation/retest
  Input: { run_id, optimized_products[] }
  Output: { result: { scores, winner_id } }
```

---

## Protocol Readiness (Layer 2)

We evaluate **ACP** and **UCP** readiness for each product/brand:

- **UCP**: business profile presence, capability intersection, missing fields
- **ACP**: feed freshness + required fields for discovery

Output is surfaced during Simulation runs as a readiness score + issue list.

---

## Alignment + Evidence (Manual Flow)

### Alignment Page
- Shows inferred intent + clarifications.
- Shows research results with alignment explanations.
- Includes “Is our product present?” check → CTA to Simulation.

### Evidence Page
- **Evidence** tab: open‑web results ranked by alignment score.
- **Explanation** tab: score distribution, “why they win”, signal deltas, 3‑path model.
- **Next actions** tab: recommended next test + counterfactual lift → CTA to Simulation.

---

## Query Battery + Experiments (v1)

### Battery Lifecycle

1. **Create**: from product panel or experiments page
2. **Generate**: auto (Lab) or manual (Manual) query battery
3. **Curate**: enable/disable queries, adjust weights
4. **Run**: compare variants with structured experiments

### Experiments Loop

```
HYPOTHESIS → RUN BATTERY → COMPARE VARIANTS → BELIEF UPDATE → NEXT TEST
```

Metrics tracked:
- Win‑rate
- Avg score
- Coverage / redundancy

---

## Future: Catalog Automation (Deferred)

Automated catalog ingestion, batch analysis, and deployment workflows are
intentionally deferred in v1. When re‑introduced, they will live in a separate
integration layer and be documented in the roadmap.

---

*Document Version: 2026-01-22*  
*Status: Active*
