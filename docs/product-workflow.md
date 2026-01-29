# Product Workflow: Simulation Sandbox + Catalog Optimization

**Purpose**: Detailed specification of the user journey from initial testing through full catalog optimization.

---

## Overview

The product has two modes, serving different stages of the user journey:

### Mode 1: Simulation Sandbox (Hackathon Demo)

The core experience: test products against queries, see who wins, understand why, optimize, re-test.

```
SET UP SCENARIO → SIMULATE → SEE RESULTS → LESSONS → CONFIRM TONE → OPTIMIZE → RE-TEST
      ↑                                                  │
      └──────────────────────────────────────────────────┘
```

This is the **closed feedback loop** that solves the user's core pain point: "I don't know why my product isn't showing up in AI results."

### Query Battery + Experiments (v1)

To make the loop repeatable, we attach a per‑product **query battery** and run structured experiments:

- **Create battery** from product panels (chat or alignment) → generate queries (bottom‑up/top‑down/hybrid).
- **Edit battery**: enable/disable queries, adjust weights, review coverage metrics.
- **Create experiment**: hypothesis + competitor policy + variants (A/B/C).
- **Run battery** against each variant to compare win‑rate and score lift.

### Mode 2: Full Catalog Workflow (Production)

After proving value with the sandbox, brands connect their full catalogs:

```
CONNECT → ANALYZE → OPTIMIZE → DEPLOY → VERIFY
```

This document specifies both modes in detail.

---

## The Simulation Sandbox (Hackathon Focus)

### Purpose

Let users test their products against user queries and see what an LLM shopping agent would recommend—and why.

### The Core Loop

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: SET UP SCENARIO                                     │
│                                                              │
│  Query: [I need a TV for my bright living room         ]    │
│                                                              │
│  Your Product:                                               │
│  [Samsung QN90B - 65-inch 4K QLED, 3000 nits           ]    │
│                                                              │
│  Competitors (optional):                                     │
│  [LG C3 - Bright room viewing, anti-glare              ]    │
│  [Sony A80K - 4K OLED with anti-reflective coating     ]    │
│                                                              │
│  [Run Simulation]                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: SIMULATION RESULTS                                  │
│                                                              │
│  Inferred User Intent:                                       │
│  Primary: "Enjoyable viewing despite ambient light"          │
│  Needs: ["glare reduction", "brightness", "daytime usability"]│
│                                                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │ LG C3           │ │ Samsung QN90B   │ │ Sony A80K       ││
│  │ Score: 0.78     │ │ Score: 0.52     │ │ Score: 0.61     ││
│  │ ✅ RECOMMENDED  │ │ ❌ NOT PICKED   │ │ ❌ NOT PICKED   ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
│                                                              │
│  WHY YOU LOST:                                               │
│  • Missing: outcome framing ("Combat glare")                 │
│  • Missing: context fit ("bright living room")               │
│  • Present but hidden: 3000 nits (the actual differentiator) │
│                                                              │
│  PROTOCOL READINESS (UCP/ACP):                               │
│  • UCP readiness: 72/100                                     │
│  • Missing: UCP checkout capability                          │
│  • Missing: REST endpoint in business profile                │
│  • ACP feed stale: update within 15 minutes                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: LESSONS                                             │
│                                                              │
│  Lesson: "Highlight anti-glare explicitly for bright rooms"  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: CONFIRM TONE                                        │
│                                                              │
│  Suggested tone: "confident, concise, technical"             │
│  [Use suggestion] [Edit] [Clear]                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: OPTIMIZE                                            │
│                                                              │
│  Suggested Improvement:                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Before: "65-inch 4K QLED, 3000 nits brightness"         ││
│  │                                                          ││
│  │ After:  "Combat glare in bright rooms. Clear picture    ││
│  │          without closing blinds. 65-inch 4K, 3000 nits."││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Apply & Re-Test]                     [Edit Suggestion]     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: RE-TEST RESULTS                                     │
│                                                              │
│  Samsung QN90B: 0.52 → 0.85                                  │
│  ✅ NOW RECOMMENDED                                          │
│                                                              │
│  Lift: +63% alignment score                                  │
│                                                              │
│  [Save Changes]  [Export Description]  [Try Another Query]   │
└─────────────────────────────────────────────────────────────┘
```

### Data Models

```python
@dataclass
class SimulationScenario:
    scenario_id: str
    query: str  # User query to simulate
    user_product: ProductInput  # The brand's product
    competitors: List[ProductInput]  # Optional competitor products
    created_at: datetime

@dataclass
class ProductInput:
    name: str
    description: str
    url: str | None  # Optional: fetch from web

@dataclass
class SimulationResult:
    scenario_id: str
    inferred_intent: InferredIntent
    product_scores: List[ProductScore]
    winner: str  # product_id of recommended product
    gap_analysis: GapAnalysis  # Why user's product lost (if it did)
    protocol_readiness: List[Dict[str, Any]]  # UCP/ACP readiness issues
    tone: Dict[str, Any]  # Suggested brand tone summary
    lessons: List[str]  # Winner vs loser takeaways

@dataclass
class ProductScore:
    product_id: str
    name: str
    score: float
    matched_capabilities: List[str]
    missing_capabilities: List[str]
    is_recommended: bool

@dataclass
class GapAnalysis:
    missing_elements: List[str]  # What's missing from user's product
    hidden_strengths: List[str]  # Present but not highlighted
    optimization_suggestions: List[str]  # Specific changes to make
```

### API Endpoints

**Multi-tenant requirement:** Every request includes `client_id`. Simulation calls may include `brand_id`/`product_id`.

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

POST /simulation/tone
  Input: { run_id, tone }
  Output: { run_id, tone }

POST /simulation/tone/from-brand
  Input: { run_id? }
  Output: { status, message }  # stub until catalog integration

GET /admin/platform-profile
  Output: { profile }  # UCP platform profile used for intersection

PUT /admin/platform-profile
  Input: { name, version, profile }  # editable platform capabilities
```

### UI Components

- **Scenario Setup Form**: Query input, product description input, competitor inputs
- **Results Dashboard**: Side-by-side product cards with scores
- **Gap Analysis Panel**: Why you lost, what's missing
- **Protocol Readiness**: UCP/ACP readiness score + missing capabilities
- **Tone Card**: Suggested brand voice with accept/edit/clear
- **Optimization Preview**: Before/after with score delta
- **Re-test Button**: Immediate feedback on changes

---

## Full Catalog Workflow (Production)

After users validate the approach with the sandbox, they can connect their full catalogs.

---

## Phase 1: CONNECT

### Purpose
Brand connects their product data source so we can access their catalog.

### Supported Sources

| Source | Auth Method | Data Access | Status |
|--------|-------------|-------------|--------|
| **Shopify** | OAuth 2.0 | Storefront API (read/write) | Planned |
| **Google Merchant Center** | Service Account | Content API | Planned |
| **CSV/JSON Upload** | None | Direct file | Functional |
| **Website Scrape** | None (public) | Crawl product pages | Future |

### User Flow

1. Brand selects data source type
2. Brand authenticates (OAuth flow for Shopify/GMC) or uploads file
3. System validates connection and retrieves product count
4. Brand confirms catalog scope (all products or filtered subset)

### Data Model

```python
@dataclass
class CatalogConnection:
    id: str
    brand_id: str
    source_type: Literal["shopify", "google_merchant", "csv", "json", "scrape"]
    credentials: dict  # encrypted, varies by source
    product_count: int
    last_sync: datetime
    status: Literal["connected", "error", "syncing"]
```

### API Endpoints

```
POST /catalog/connect
  Input: { source_type, credentials_or_file }
  Output: { connection_id, product_count, status }

GET /catalog/{connection_id}/status
  Output: { status, product_count, last_sync, errors? }
```

### Hackathon Scope

For the demo, we simulate this phase:
- Accept mock product data or pre-loaded test catalog
- Skip OAuth flows
- Show the UI for source selection (non-functional)

---

## Phase 2: ANALYZE

### Purpose
Score every product's current "intent legibility" and identify discovery gaps.

### Process

1. **Ingest**: Pull all products from connected source
2. **Profile**: Run each through intentionality profiler
3. **Score**: Calculate discoverability score per product
4. **Aggregate**: Generate catalog-level health metrics
5. **Report**: Output Catalog Health Report

### Discoverability Score

Each product receives a 0-1 score based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| **Capability extraction** | 0.3 | Could we extract capabilities from the listing? |
| **Outcome mapping** | 0.3 | Could we map specs to user outcomes? |
| **Goal alignment coverage** | 0.2 | Does it address common intent patterns? |
| **Context fit signals** | 0.2 | Is usage context explicit? |

### Data Model

```python
@dataclass
class ProductAnalysis:
    product_id: str
    discoverability_score: float  # 0-1
    intentionality_profile: IntentionalityProfile
    gaps: List[str]  # e.g., ["no outcome framing", "specs-only description"]
    recommendations: List[str]  # e.g., ["add capability: 'reduces glare'"]

@dataclass
class CatalogHealthReport:
    catalog_id: str
    total_products: int
    avg_discoverability_score: float
    score_distribution: Dict[str, int]  # {"0-0.3": 42, "0.3-0.7": 156, ...}
    top_gaps: List[str]  # most common issues
    top_performers: List[str]  # product_ids with highest scores
    low_performers: List[str]  # product_ids needing most work
    generated_at: datetime
```

### API Endpoints

```
POST /catalog/{connection_id}/analyze
  Input: { product_ids?: list (optional, analyzes all if omitted) }
  Output: { job_id, status: "queued" }

GET /catalog/{connection_id}/analysis/{job_id}
  Output: { status, progress, results?: CatalogHealthReport }

GET /catalog/{connection_id}/report
  Output: CatalogHealthReport
```

### UI Components

- **Catalog Health Dashboard**: Overall score, distribution chart, trend line
- **Product Table**: Sortable by discoverability score, with gap indicators
- **Gap Summary**: Common issues across catalog with fix recommendations

### Hackathon Scope

Fully functional for the demo:
- Analyze products from mock catalog
- Display discoverability scores
- Show gap analysis per product
 - Generate a simple legibility report

---

## Phase 3: OPTIMIZE

### Purpose
Transform product data to be intent-legible using LLM-assisted enrichment.

### Process

1. **Select**: Brand selects products to optimize (or bulk-select)
2. **Enrich**: LLM generates capabilities, outcomes, context fit
3. **Preview**: Show before/after with alignment score comparison
4. **Edit**: Brand can modify suggestions
5. **Approve**: Brand confirms optimizations

### Optimization Types

| Type | Description | Example |
|------|-------------|---------|
| **Capability Extraction** | Transform specs into what the product enables | "3000 nits" → "Combat glare in bright rooms" |
| **Outcome Framing** | Describe what the user achieves | "Watch TV comfortably without closing blinds" |
| **Context Fit** | Explicit usage scenarios | "Ideal for: south-facing living rooms, offices with large windows" |
| **Goal Mapping** | Connect to intent categories | Serves goals: ["bright-room viewing", "daytime TV watching"] |

### Data Model

```python
@dataclass
class OptimizationSuggestion:
    product_id: str
    field: str  # e.g., "description", "metafield:capabilities"
    original_value: str
    suggested_value: str
    reason: str  # why this change helps
    confidence: float
    alignment_score_before: float
    alignment_score_after: float  # predicted

@dataclass
class OptimizationBatch:
    batch_id: str
    catalog_id: str
    products: List[str]
    suggestions: List[OptimizationSuggestion]
    status: Literal["draft", "approved", "deployed"]
    created_at: datetime
    approved_at: datetime | None
```

### API Endpoints

```
POST /catalog/{connection_id}/optimize
  Input: { product_ids, optimization_types?: list }
  Output: { batch_id, suggestions: List[OptimizationSuggestion] }

PUT /catalog/{connection_id}/optimize/{batch_id}
  Input: { action: "approve" | "reject", modified_suggestions?: list }
  Output: { batch_id, status }
```

### UI Components

- **Optimization Queue**: Products selected for optimization
- **Before/After Preview**: Side-by-side comparison with score delta
- **Edit Modal**: Brand can modify suggested changes
- **Batch Approval**: Approve all or select individual suggestions

### Hackathon Scope

Core demo feature:
- Show LLM-generated optimization suggestions
- Display before/after alignment scores
- Allow manual editing of suggestions
- Skip actual write-back (simulate approval)

---

## Phase 4: DEPLOY

### Purpose
Push optimized product data back to the source system.

### Process

1. **Prepare**: Format optimized data for target system
2. **Preview**: Show what will be changed in source
3. **Deploy**: Write changes to Shopify/GMC/etc.
4. **Verify**: Confirm changes applied successfully
5. **Rollback**: Option to revert if needed

### Deployment Strategies

| Source | Strategy | What Changes |
|--------|----------|--------------|
| **Shopify** | Product metafields | Add `intentionality.*` metafields, optionally update description |
| **Google Merchant Center** | Supplemental feed | Upload feed with enriched attributes |
| **CSV Export** | Download file | Brand manually uploads to their system |

### Data Model

```python
@dataclass
class DeploymentJob:
    job_id: str
    batch_id: str
    target: Literal["shopify", "google_merchant", "export"]
    products_affected: int
    status: Literal["pending", "in_progress", "completed", "failed", "rolled_back"]
    changes_applied: List[dict]  # audit trail
    created_at: datetime
    completed_at: datetime | None
```

### API Endpoints

```
POST /catalog/{connection_id}/deploy
  Input: { batch_id, target, dry_run?: bool }
  Output: { job_id, preview: List[ChangePreview] } if dry_run else { job_id, status }

GET /catalog/{connection_id}/deploy/{job_id}
  Output: { status, changes_applied, errors? }

POST /catalog/{connection_id}/deploy/{job_id}/rollback
  Output: { status, reverted_changes }
```

### Hackathon Scope

Simulated for demo:
- Show deployment preview (what would change)
- Display "deployed" confirmation
- Skip actual OAuth write-back

---

## Phase 5: VERIFY

### Purpose
Test whether optimization actually improved LLM discoverability.

### Process

1. **Configure**: Set up test scenarios (user queries + expected products)
2. **Query**: Send queries to multiple LLMs (Gemini, GPT, Claude)
3. **Track**: Record which products get recommended
4. **Compare**: Pre-optimization vs post-optimization recommendation rates
5. **Report**: Output Discoverability Lift Report

### Test Scenarios

```python
@dataclass
class TestScenario:
    scenario_id: str
    query: str  # e.g., "I need a TV for my bright living room"
    expected_products: List[str]  # product_ids that should surface
    llm_targets: List[str]  # ["gemini", "openai", "claude"]
```

### Verification Metrics

| Metric | Description |
|--------|-------------|
| **Recommendation Rate** | % of queries where product was recommended |
| **Position** | Where product appeared in recommendation list |
| **Mention Quality** | How the LLM described/positioned the product |
| **Discoverability Lift** | Change in recommendation rate pre vs post optimization |

### Data Model

```python
@dataclass
class VerificationResult:
    scenario_id: str
    llm: str
    query: str
    recommended_products: List[str]
    positions: Dict[str, int]  # product_id -> position
    response_snippet: str

@dataclass
class DiscoverabilityLiftReport:
    catalog_id: str
    period: str  # "pre" | "post"
    scenarios_tested: int
    products_tracked: int
    recommendation_rate: Dict[str, float]  # product_id -> rate
    avg_position: Dict[str, float]
    lift_vs_baseline: float  # % improvement
    top_gainers: List[str]  # products with biggest improvement
    generated_at: datetime
```

### API Endpoints

```
POST /catalog/{connection_id}/verify
  Input: { scenarios: List[TestScenario], baseline?: bool }
  Output: { job_id, status: "queued" }

GET /catalog/{connection_id}/verify/{job_id}
  Output: { status, progress, results?: List[VerificationResult] }

GET /catalog/{connection_id}/lift-report
  Output: DiscoverabilityLiftReport
```

### Hackathon Scope

Key demo differentiator:
- Pre-define 3-5 test scenarios
- Simulate recommendations for before/after (or run a single provider if available)
- Show before/after comparison
- Display lift metrics

---

## Summary: Hackathon vs Production

| Phase | Hackathon Implementation | Production Implementation |
|-------|-------------------------|--------------------------|
| **Connect** | Mock data / file upload | Full OAuth for Shopify, GMC |
| **Analyze** | Fully functional | Add batch processing, caching |
| **Optimize** | Fully functional | Add more optimization types |
| **Deploy** | Simulated (preview only) | Actual write-back to sources |
| **Verify** | Simulated or single-provider scenarios | Multi-LLM, custom scenarios, scheduled |

---

## Demo Flow Mapping

### Hackathon Demo (Simulation Sandbox)

The 60-second demo shows the core feedback loop:

1. **"Brand asks: why isn't my product in AI results?"** → THE PROBLEM
2. **"Set up a test: query + product + competitors"** → SCENARIO SETUP
3. **"Run simulation: see who wins"** → SIMULATE
4. **"Understand why you lost"** → GAP ANALYSIS
5. **"Apply suggested fix"** → OPTIMIZE
6. **"Re-test: now you're recommended"** → VERIFY

**The pitch**: "See what the LLM sees. Fix what's broken. Test until you win."

### Production Demo (Full Workflow)

The expanded demo for enterprise customers:

1. **"Connect your catalog"** → CONNECT (Shopify, Merchant Center)
2. **"See which products need work"** → ANALYZE (health report)
3. **"We optimize at scale"** → OPTIMIZE (batch processing)
4. **"Deploy to your store"** → DEPLOY (write-back)
5. **"Verify lift over time"** → VERIFY (monitoring dashboard)

---

## User Journey Summary

| Stage | What User Does | What They Get |
|-------|---------------|---------------|
| **Discovery** | Tries sandbox with one product | "Aha! Now I understand why I'm not showing up" |
| **Validation** | Tests multiple queries/products | Confidence that optimization works |
| **Adoption** | Connects full catalog | Batch analysis, prioritized fixes |
| **Integration** | Deploys to production | Live optimization in their store |
| **Ongoing** | Monitors discoverability | Alerts when things change |

---

*Document Version: 2026-01-22*
*Status: Active*
