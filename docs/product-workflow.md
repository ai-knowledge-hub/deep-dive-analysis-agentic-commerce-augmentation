# Product Workflow: Automated Lab Loop + Protocol Readiness

**Purpose**: Describe the v1 user journey as an **automated lab loop** centered on
simulation, query batteries, and protocol readiness (ACP/UCP).

---

## Overview

The product has two **modes** in v1:

### Manual Mode (Simulation Sandbox)

```
SET UP SCENARIO → SIMULATE → SEE RESULTS → LESSONS → CONFIRM TONE → OPTIMIZE → RE‑TEST
      ↑                                                  │
      └──────────────────────────────────────────────────┘
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

## Simulation Sandbox

### Core Loop

1. **Scenario Setup**: query + your product + competitors
2. **Run Simulation**: LLM‑style intent inference + alignment scoring
3. **Why You Lost**: missing framing, context fit, outcome language
4. **Protocol Readiness**: UCP/ACP readiness issues (profiles + feed freshness)
5. **Optimize**: suggested copy rewrite + tone confirmation
6. **Re‑test**: verify lift

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

Output is surfaced as a readiness score + a list of issues and fixes.

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
