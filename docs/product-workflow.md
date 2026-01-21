# Product Workflow: Brand Catalog Optimization + Verification

**Purpose**: Detailed specification of the brand journey from onboarding through verified discoverability lift.

---

## Overview

The brand workflow is a 5-step process that transforms product catalogs from spec-heavy listings into intent-legible content and verifies lift in AI recommendations.

```
CONNECT → ANALYZE → OPTIMIZE → DEPLOY → VERIFY
```

This document specifies each phase in detail, including:
- User actions
- System processes
- Data models
- API endpoints
- UI components

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

The 60-second demo corresponds to phases:

1. **"Here's a brand's catalog"** → CONNECT (show connected state)
2. **"Most products score poorly"** → ANALYZE (show health report)
3. **"We optimize with intent framing"** → OPTIMIZE (show before/after)
4. **"Changes deploy to their store"** → DEPLOY (show confirmation)
5. **"Now LLMs recommend them"** → VERIFY (show lift metrics)

---

*Document Version: 2026-01-20*
*Status: Active*
