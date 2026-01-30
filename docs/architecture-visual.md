# Platform Architecture - Visual Guide

**Version:** 1.0
**Date:** 2026-01-29

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACES                                │
│                         (Next.js React App)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   Chat   │  │ Evidence │  │Simulation│  │Experiments│  │ Overview │  │
│  │    /     │  │/evidence │  │/simulation│  │/experiments│  │/overview │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │             │              │             │             │         │
└───────┼─────────────┼──────────────┼─────────────┼─────────────┼─────────┘
        │             │              │             │             │
        ▼             ▼              ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API LAYER                                     │
│                          (FastAPI Routes)                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │Conversation │  │  Evidence   │  │ Simulation  │  │ Experiments │   │
│  │    API      │  │     API     │  │     API     │  │     API     │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │            │
└─────────┼────────────────┼────────────────┼────────────────┼────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION SERVICES                              │
│                      (Business Logic Layer)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ Conversation    │  │  Evidence       │  │  Simulation     │         │
│  │  Service        │  │   Service       │  │   Service       │         │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │         │
│  │ │Intent Infer │ │  │ │Research     │ │  │ │Gap Analysis │ │         │
│  │ │Goal Clarify │ │  │ │Profile      │ │  │ │Optimize     │ │         │
│  │ │Product Search│ │  │ │Optimize     │ │  │ │Retest       │ │         │
│  │ │Alignment    │ │  │ │Verify Lift  │ │  │ │Save Lesson  │ │         │
│  │ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘ │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  Experiment     │  │   Alignment     │  │   Battery       │         │
│  │   Service       │  │    Service      │  │   Builder       │         │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │         │
│  │ │Create Exp   │ │  │ │Score Product│ │  │ │Generate     │ │         │
│  │ │Add Variants │ │  │ │vs Goals     │ │  │ │Scenarios    │ │         │
│  │ │Run Tests    │ │  │ │Explain      │ │  │ │Bottom-up    │ │         │
│  │ │Track Metrics│ │  │ │Reasoning    │ │  │ │Top-down     │ │         │
│  │ │ML Recommend │ │  │ └─────────────┘ │  │ └─────────────┘ │         │
│  │ └─────────────┘ │  └─────────────────┘  └─────────────────┘         │
│  └─────────────────┘                                                     │
│                                                                           │
└───────────────────────────┬───────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DOMAIN LAYER                                    │
│                     (Pure Business Logic)                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Intent    │  │Intentionality│  │ Alignment   │  │  Evidence   │   │
│  │   Rules     │  │  Profiling   │  │   Scoring   │  │    Types    │   │
│  │             │  │              │  │             │  │             │   │
│  │• Classify   │  │• Spec→Cap   │  │• Goal Match │  │• Product    │   │
│  │• Clarify    │  │• Cap→Outcome │  │• Confidence │  │• Capability │   │
│  │• Validate   │  │• Context Fit │  │• Reasoning  │  │• Outcome    │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                           │
└───────────────────────────┬───────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                                │
│                  (External Services & Adapters)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │    LLM      │  │  Database   │  │  Protocols  │  │   Search    │   │
│  │  Clients    │  │   (SQLite)  │  │             │  │   Engine    │   │
│  │             │  │             │  │             │  │             │   │
│  │• Gemini     │  │• Sessions   │  │• UCP        │  │• Vector DB  │   │
│  │• OpenRouter │  │• Products   │  │• ACP        │  │• Embeddings │   │
│  │• Claude     │  │• Experiments│  │• Validation │  │• Similarity │   │
│  │• Templates  │  │• Metrics    │  │             │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Chat Query

```
User Types Query: "TV for bright room"
        │
        ▼
┌─────────────────────────────────────────┐
│  1. INTENT INFERENCE                    │
│  ───────────────────                    │
│  Input:  "TV for bright room"           │
│  LLM:    Gemini classifies intent       │
│  Output: Goal = "reduce glare in        │
│          bright environment"            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  2. GOAL CLARIFICATION                  │
│  ──────────────────────                 │
│  Missing: Room size, budget             │
│  Ask:    "What room size?"              │
│  User:   "Medium, ~$1000"               │
│  Goals:  ["reduce glare",               │
│           "medium room",                │
│           "budget ~$1000"]              │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  3. PRODUCT SEARCH                      │
│  ──────────────────                     │
│  Search:  Brand catalog for TVs         │
│  Filter:  Price ≤ $1200                 │
│  Found:   5 candidate products          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  4. INTENTIONALITY PROFILING            │
│  ────────────────────────────           │
│  For each product:                      │
│  Spec:       "3000 nits brightness"     │
│  Capability: "high brightness"          │
│  Outcome:    "clear picture in daylight"│
│  Context:    "works in bright rooms"    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  5. ALIGNMENT SCORING                   │
│  ─────────────────────                  │
│  Product A: 0.71 (good match)           │
│  Product B: 0.42 (partial match)        │
│  Product C: 0.89 (excellent match) ✓    │
│  Product D: 0.33 (poor match)           │
│  Product E: 0.68 (good match)           │
│                                          │
│  Rank by score: C, A, E, B, D           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  6. REASONING GENERATION                │
│  ────────────────────────               │
│  For Product C (0.89):                  │
│  "This TV scores 89% because:           │
│   • 3000 nits brightness → reduces glare│
│   • Anti-reflective coating → works in  │
│     bright environments                 │
│   • 65-inch screen → suitable for       │
│     medium rooms"                       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  7. DISPLAY RESULTS                     │
│  ───────────────────                    │
│  User sees:                             │
│  ✓ Inferred goals                       │
│  ✓ Ranked products                      │
│  ✓ Alignment scores                     │
│  ✓ Reasoning                            │
│  ✓ Option to run evidence analysis      │
└─────────────────────────────────────────┘
```

---

## Data Flow: Simulation

```
User Defines Scenario: "Running shoes for marathon training"
        │
        ▼
┌─────────────────────────────────────────┐
│  1. SELECT PRODUCT                      │
│  ──────────────────                     │
│  User picks: "StrideFlex Trainer"      │
│  Current description:                   │
│  "Running shoes with responsive foam,   │
│   6mm drop, breathable mesh"            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  2. RUN SIMULATION                      │
│  ──────────────────                     │
│  Score product against scenario:        │
│  Alignment: 0.42 (low)                  │
│  Gaps identified ↓                      │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  3. GAP ANALYSIS                        │
│  ────────────────                       │
│  Missing capabilities:                  │
│  • "endurance support"                  │
│  • "joint protection"                   │
│  • "long-distance stability"            │
│                                          │
│  Missing outcome signals:               │
│  • "supports longer runs"               │
│  • "reduces injury risk"                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  4. OPTIMIZE DESCRIPTION                │
│  ────────────────────────               │
│  AI generates improved copy:            │
│  "Support longer runs with cushioning   │
│   that eases joint strain and a stable  │
│   platform for road training"           │
│                                          │
│  Changes:                               │
│  + Added outcome: "support longer runs" │
│  + Added capability: "eases joint strain"│
│  + Added context: "road training"       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  5. RETEST                              │
│  ──────                                 │
│  Score optimized version:               │
│  Before: 0.42                           │
│  After:  0.71                           │
│  Lift:   +69%                           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  6. SAVE LESSON                         │
│  ───────────────                        │
│  Lesson: "Outcome framing improves      │
│          marathon-intent queries by 69%"│
│  Evidence: { before: 0.42, after: 0.71 }│
│  Confidence: 0.85                       │
└─────────────────────────────────────────┘
```

---

## Data Flow: Experiment

```
User Creates Experiment: "Outcome Framing Test"
        │
        ▼
┌─────────────────────────────────────────┐
│  1. CREATE QUERY BATTERY                │
│  ────────────────────────               │
│  Name: "Marathon Shoes Tests"           │
│  Generated queries:                     │
│  • "running shoes for marathon training"│
│  • "marathon shoes for road running"    │
│  • "long-distance running sneakers"     │
│  • "endurance running footwear"         │
│  ...15 total queries                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  2. CREATE VARIANTS                     │
│  ───────────────────                    │
│  Control:                               │
│  "Running shoes with responsive foam"   │
│                                          │
│  Variant A (Outcome-Focused):           │
│  "Support longer runs with cushioning..." │
│                                          │
│  Variant B (Technical Detail):          │
│  "6mm drop foam with biomechanical..." │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  3. RUN EXPERIMENT                      │
│  ──────────────────                     │
│  For each query × each variant:         │
│  • Score alignment                      │
│  • Track wins                           │
│  • Calculate metrics                    │
│                                          │
│  Query 1 × Control:  0.42               │
│  Query 1 × Variant A: 0.71 ✓ (wins)    │
│  Query 1 × Variant B: 0.55              │
│  ...repeat for all 15 queries           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  4. CALCULATE METRICS                   │
│  ─────────────────────                  │
│  Control:    Win rate: 20% (3/15)       │
│              Avg score: 0.39            │
│                                          │
│  Variant A:  Win rate: 80% (12/15) ✓    │
│              Avg score: 0.68            │
│              Lift: +60%                 │
│                                          │
│  Variant B:  Win rate: 47% (7/15)       │
│              Avg score: 0.52            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  5. STATISTICAL ANALYSIS                │
│  ────────────────────────               │
│  Welch's t-test:                        │
│  • p-value: 0.03 (significant)          │
│  • Effect size: 0.61 (medium)           │
│  • 95% CI: [+40%, +80%]                 │
│                                          │
│  Conclusion: Variant A significantly    │
│  outperforms control                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  6. ML RECOMMENDATION                   │
│  ─────────────────────                  │
│  Based on 5 similar experiments:        │
│  • Next test: "Technical detail reduction"│
│  • Predicted lift: +12%                 │
│  • Confidence: 73%                      │
│  • Rationale: "Past experiments show    │
│    simplifying technical specs improves │
│    footwear discoverability"            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  7. SAVE BELIEF                         │
│  ───────────────                        │
│  Belief: "Outcome framing improves      │
│          marathon queries by 60%"       │
│  Evidence: { win_rate_lift: 0.60,      │
│              sample_size: 15 }          │
│  Confidence: 0.82                       │
└─────────────────────────────────────────┘
```

---

## Multi-Tenant Data Model

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENTS                              │
│                      (Organizations)                         │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│  │ Nike   │  │ Adidas │  │  Sony  │  │ Samsung│            │
│  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘            │
└──────┼───────────┼───────────┼───────────┼──────────────────┘
       │           │           │           │
       ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│                          BRANDS                              │
│                     (Product Lines)                          │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│  │Air Max │  │Ultraboost│ │ Bravia │  │  QLED  │            │
│  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘            │
└──────┼───────────┼───────────┼───────────┼──────────────────┘
       │           │           │           │
       ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│                        PRODUCTS                              │
│                   (Individual Items)                         │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│  │AM 270  │  │Boost 22│  │X90L 65"│  │Q80C 55"│            │
│  └────────┘  └────────┘  └────────┘  └────────┘            │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ASSOCIATED DATA                           │
│                                                               │
│  • Experiments  (which variants were tested)                 │
│  • Simulations  (what scenarios were run)                    │
│  • Beliefs      (what was learned about the brand)           │
│  • Sessions     (user conversations)                         │
│  • Metrics      (performance trends)                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Experiment Execution Flow

```
                    CREATE EXPERIMENT
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │     Define Query Battery             │
        │  • Scenario 1: "marathon shoes"      │
        │  • Scenario 2: "road running shoes"  │
        │  • Scenario 3: "endurance footwear"  │
        │  ...15 total scenarios               │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │      Create Variants                 │
        │  • Control (current copy)            │
        │  • Variant A (outcome-focused)       │
        │  • Variant B (technical detail)      │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │       RUN EXPERIMENT                 │
        │                                       │
        │  For each scenario × variant:        │
        │  ┌────────────────────────────────┐  │
        │  │  Scenario 1 × Control          │  │
        │  │  → Score: 0.42                 │  │
        │  └────────────────────────────────┘  │
        │  ┌────────────────────────────────┐  │
        │  │  Scenario 1 × Variant A        │  │
        │  │  → Score: 0.71 ✓               │  │
        │  └────────────────────────────────┘  │
        │  ┌────────────────────────────────┐  │
        │  │  Scenario 1 × Variant B        │  │
        │  │  → Score: 0.55                 │  │
        │  └────────────────────────────────┘  │
        │  ...repeat for all 15 scenarios      │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │    AGGREGATE METRICS                 │
        │                                       │
        │  Control:    Wins: 3/15 (20%)        │
        │              Avg:  0.39              │
        │                                       │
        │  Variant A:  Wins: 12/15 (80%) ✓     │
        │              Avg:  0.68              │
        │                                       │
        │  Variant B:  Wins: 7/15 (47%)        │
        │              Avg:  0.52              │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │   STATISTICAL ANALYSIS               │
        │                                       │
        │  Compare: Variant A vs Control       │
        │  • t-statistic: 2.45                 │
        │  • p-value: 0.03 (significant)       │
        │  • Effect size: 0.61 (medium)        │
        │  • 95% CI: [+40%, +80%]              │
        │                                       │
        │  ✓ Variant A significantly better    │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │      SAVE RESULTS                    │
        │                                       │
        │  • Store metrics in database         │
        │  • Generate belief                   │
        │  • Update experiment status          │
        │  • Notify user                       │
        └──────────────────────────────────────┘
```

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                      FRONTEND                            │
│  • Next.js 14 (React framework)                         │
│  • TypeScript (type safety)                             │
│  • Clerk (authentication)                               │
│  • styled-jsx (component styling)                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                      BACKEND                             │
│  • Python 3.10+                                         │
│  • FastAPI (API framework)                              │
│  • Pydantic (data validation)                           │
│  • SQLite (database)                                    │
│  • SQLModel (ORM)                                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    AI/ML SERVICES                        │
│  • Google Gemini (intent inference, alignment scoring)  │
│  • OpenRouter (fallback LLM)                            │
│  • Custom ML Engine (experiment recommendations)        │
│  • Vector embeddings (product/intent similarity)        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE                         │
│  • uv (Python package manager)                          │
│  • npm (Node package manager)                           │
│  • SQLite (local database)                              │
│  • Filesystem storage (temporary files)                 │
└─────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture (Future)

```
┌──────────────────────────────────────────────────────────┐
│                    LOAD BALANCER                          │
│                   (NGINX / CloudFlare)                    │
└────────────────────┬─────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌───────────────┐        ┌───────────────┐
│  Web Server 1 │        │  Web Server 2 │
│  (Next.js)    │        │  (Next.js)    │
└───────┬───────┘        └───────┬───────┘
        │                        │
        └────────────┬───────────┘
                     ▼
        ┌────────────────────────┐
        │     API Gateway        │
        │     (FastAPI)          │
        └────────┬───────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌──────────────┐  ┌──────────────┐
│  API Node 1  │  │  API Node 2  │
│  (FastAPI)   │  │  (FastAPI)   │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                ▼
    ┌───────────────────────┐
    │   PostgreSQL/MySQL    │
    │   (Production DB)     │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │    Redis Cache        │
    │  (Session/Embeddings) │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │   External Services   │
    │  • Gemini API         │
    │  • Vector Store       │
    │  • S3 Storage         │
    └───────────────────────┘
```

---

This visual guide complements the [Complete User Guide](./user-guide-complete.md) and provides a high-level understanding of how the platform's components interact.
