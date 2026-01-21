# Strategic Positioning: Evidence-First Organic Discovery for AI Commerce

## Executive Summary

Google built paid placement (Direct Offers). OpenAI is building answer independence. **We built organic discovery.**

When LLMs recommend products, they don't match keywords—they infer intent and select products that serve that intent. Products structured around human goals get recommended. Products described in pure specs don't.

**We help brands become discoverable by reasoning agents.**

This document maps our strategic position in the evolving agentic commerce landscape:
1. Competitive analysis: paid vs organic discovery
2. Why our approach works (the intentionality thesis)
3. Technical integration strategy
4. Business positioning

---

## 1. The Landscape: Two Paths to LLM Commerce

### Path 1: Paid Placement

Google's Direct Offers (January 2026) introduces paid ads into AI Mode recommendations:

| What Direct Offers Does | What It Doesn't Do |
|------------------------|-------------------|
| Lets retailers pay to appear in AI recommendations | Doesn't make the AI *trust* the product |
| Auction-based bidding for placement | Doesn't improve product-intent alignment |
| Performance tracking (CPA, CPC) | Doesn't help products get *organically* recommended |
| Integration with Shopping ecosystem | Doesn't optimize product data for LLM reasoning |

**Key insight**: Paid placement puts you in the auction. It doesn't make your product the right answer to the user's question.

### Path 2: Answer Independence (OpenAI)

OpenAI's approach separates advertising from answers:

| Principle | Implementation |
|-----------|---------------|
| "Answer independence" | Ads marked, don't influence recommendations |
| User control | Opt-out available |
| Transparency | Clear commercial vs organic distinction |

**Key insight**: OpenAI optimizes for trust by separating commerce from answers. But what if the commerce *is* the answer? That's our thesis.

### Path 3: Organic Discovery (Our Position)

We take a different approach:

| What We Do | Why It Works |
|------------|--------------|
| Make products legible to intent inference | LLMs recommend products that "make sense" for user goals |
| Transform specs → capabilities → outcomes | Reasoning agents reason about outcomes, not specifications |
| Predict what LLMs will recommend | Alignment scoring correlates with actual recommendations |
| Help brands optimize for organic discovery | SEO for reasoning agents |

**Our thesis**: Products genuinely aligned with user intent get recommended—regardless of ad spend. We operationalize that alignment.

---

## 2. The Intentionality Thesis

### Why LLMs Recommend What They Recommend

Large language models trained on human text learn to model:
- What humans want (goals, preferences)
- Why they want it (underlying needs)
- What satisfies those wants (products as means to ends)

This is **intent inference**—the model predicts what would satisfy the user based on contextual signals.

### The Discovery Gap

Current product data is optimized for keyword search:

```
Traditional Product Data:
  "65-inch 4K QLED TV, 3000 nits brightness,
   anti-reflective coating, 120Hz refresh rate"
```

LLMs don't match keywords. They reason about whether the product serves the user's goal:

```
User Query: "I need a TV for my bright living room"

LLM Reasoning:
  - User goal: Enjoyable viewing despite ambient light
  - Underlying need: Glare reduction, brightness, daytime usability
  - Product fit: Does this TV address those needs?
```

**The gap**: Products described in specs don't surface intent alignment. Products described in capabilities do.

### Intent-Legible Products

We transform product data to be legible to this reasoning:

```
Intent-Legible Product Data:
  - Capabilities enabled: "Combat glare in bright rooms"
  - Goals served: "Enjoyable daytime viewing"
  - Outcomes expected: "Clear picture without closing blinds"
  - Context fit: { "bright_room": 0.95, "home_theater": 0.6 }
```

Now the LLM can reason: "User wants bright-room viewing. This product explicitly serves that goal. Recommend."

---

## 3. Competitive Position

### The Three-Layer Stack

```
┌─────────────────────────────────────────────────────────────┐
│              LLM Commerce Surfaces                           │
│     Google AI Mode │ ChatGPT Shopping │ Claude │ Others     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              INTENTIONALITY OPTIMIZATION LAYER               │
│                         (Our Position)                       │
│                                                              │
│   • Intent inference from user context                       │
│   • Product intentionality profiling                        │
│   • Alignment scoring and prediction                        │
│   • Discoverability optimization                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Protocol / Transaction Layer                    │
│          UCP (Google) │ ACP (OpenAI) │ Direct APIs          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Merchant / Brand Infrastructure                 │
│         Shopify │ BigCommerce │ Custom │ Marketplaces       │
└─────────────────────────────────────────────────────────────┘
```

### What Others Provide vs What We Provide

| Player | What They Provide | What We Provide |
|--------|-------------------|-----------------|
| **Google (Direct Offers)** | Paid placement in AI Mode | Organic discovery optimization |
| **OpenAI** | Answer-independent commerce | Intent-aligned recommendations |
| **UCP/ACP** | Transaction plumbing | Pre-transaction alignment |
| **Product Data Feeds** | Specs, prices, images | Intent-legible profiles |
| **Traditional SEO** | Keyword optimization | Intent optimization |

### Why We're Complementary, Not Competitive

**To Google**: Direct Offers handles paid placement. We handle organic discovery. Brands need both.

**To OpenAI**: Their "answer independence" principle means the best product wins on merit. We help brands become the best product for the user's intent.

**To Merchants**: Protocol adapters (UCP, ACP, Shopify) handle transactions. We handle discoverability.

---

## 4. The Product

### Who We Serve: Brands as Primary Customer

**We are an evidence-first optimization + verification platform, not middleware.**

Brands are our customer. We help them optimize their product representations so LLMs recommend them organically. We don't require integration with LLM providers to deliver value—we start with open‑web evidence and later plug into brand catalogs (Shopify, Merchant Center, product feeds).

| Customer | Problem | Our Solution |
|----------|---------|--------------|
| **Brands/Retailers** | "My products aren't appearing in AI shopping results" | Analyze → Optimize → Verify discoverability |
| **E-commerce platforms** | "Our merchants need AI discoverability tools" | White-label optimization layer |
| **Commerce developers** | "How do I match products to user intent?" | API access to intent + alignment scoring |

### Core Offering: Evidence-First Optimization + Verification

The brand workflow is a 5-step process:

```
┌─────────────────────────────────────────────────────────────┐
│  1. CONNECT                                                  │
│     Brand connects their product data source                 │
│     • Shopify store (OAuth)                                  │
│     • Google Merchant Center (service account)               │
│     • CSV/JSON feed upload                                   │
│     • Website scrape                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. ANALYZE                                                  │
│     Score current intent legibility                          │
│     • Run each product through intentionality profiler       │
│     • Generate "discoverability score" per product           │
│     • Identify gaps: specs without outcome framing           │
│     • Output: Catalog Health Report                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. OPTIMIZE                                                 │
│     Transform product data for intent legibility             │
│     • LLM-assisted enrichment of capabilities/outcomes       │
│     • Generate intent-aligned descriptions                   │
│     • Preview before/after alignment scores                  │
│     • Brand reviews and approves changes                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. DEPLOY                                                   │
│     Push optimized data back to source                       │
│     • Write-back to Shopify product metafields               │
│     • Update Merchant Center supplemental feed               │
│     • Export enriched feed for manual upload                 │
│     • Preserve original data, add intent layer               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. VERIFY                                                   │
│     Test actual LLM discoverability                          │
│     • Query multiple LLMs with user scenarios                │
│     • Track recommendation frequency                         │
│     • Compare pre/post optimization results                  │
│     • Output: Discoverability Lift Report                    │
└─────────────────────────────────────────────────────────────┘
```

### Why This Works Without LLM Provider Integration

We optimize at the source—the product data that LLMs crawl and consume:

| Where Data Lives | How LLMs Access It | How We Help |
|------------------|-------------------|-------------|
| **Shopify stores** | Crawled, indexed, or via API | Optimize product descriptions + metafields |
| **Google Merchant Center** | Feeds AI Mode directly | Enrich supplemental feeds |
| **Brand websites** | Crawled by search + AI | Generate intent-legible content |

The LLM doesn't know we exist. It just sees better product representations that match user intent. Verification proves the impact without platform deals.

### API Surface

```
POST /intent/infer
  Input: { query, session_context, user_id? }
  Output: { inferred_intent, confidence, signals }

POST /products/align
  Input: { inferred_intent, product_ids?, limit? }
  Output: { aligned_products: [{ product, alignment_score, reasoning }] }

POST /products/profile
  Input: { product_id }
  Output: { intentionality_profile }

POST /evidence/analyze
  Input: { query }
  Output: { evidence_products, profiles, alignment_scores }

POST /representation/optimize
  Input: { evidence_products }
  Output: { before_after_pairs, alignment_deltas }

POST /recommendation/verify
  Input: { query, evidence_products }
  Output: { predicted_vs_actual, lift }

POST /catalog/analyze
  Input: { catalog_url or feed }
  Output: { products_analyzed, intent_legibility_scores, recommendations }

GET /catalog/{catalog_id}/report
  Output: { discoverability_report }
```

---

## 5. Technical Integration

### Protocol-Agnostic Design

We work above the protocol layer:

```
modules/commerce/adapters/
├── base.py           # Abstract adapter interface
├── shopify.py        # Shopify Storefront API
├── google_merchant.py # Merchant Center feeds
├── mock.py           # Testing
└── ucp.py            # Google UCP (future)
```

Each adapter normalizes source data; our intentionality module enriches it.

### Data Flow

```
Brand Catalog
    │
    ▼
┌─────────────────────────────────────────┐
│ Adapter (Shopify/Merchant Center/etc)   │
│ Normalize to RawOffer                   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Intentionality Profiler                  │
│ Transform specs → capabilities          │
│ Map to goals and outcomes               │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Intent-Legible Product                   │
│ Ready for LLM discovery                 │
└─────────────────────────────────────────┘
```

### Integration with LLM Surfaces

We don't require platform integration to deliver value:

| Scenario | How We Help |
|----------|-------------|
| **Brand wants more AI recommendations** | Analyze catalog, optimize intentionality, measure lift |
| **Platform wants better recommendations** | Provide intent inference + alignment scoring as service |
| **Developer building commerce agent** | Use our APIs to match products to user intent |

---

## 6. Business Model

### Who Pays: Brands

Brands pay us to make their products more discoverable by AI. This is analogous to traditional SEO services, but for reasoning agents instead of keyword search.

### Revenue Streams

| Stream | What Brand Gets | Pricing Model |
|--------|-----------------|---------------|
| **Catalog Audit** | One-time discoverability report + recommendations | Per-catalog fee |
| **Optimization SaaS** | Ongoing enrichment, monitoring, re-optimization | Monthly subscription |
| **API Access** | Programmatic intent + alignment scoring | Usage-based |
| **Enterprise** | White-label for platforms, custom integration | Contract |

### Customer Tiers

| Tier | Customer | Problem | Solution |
|------|----------|---------|----------|
| **Primary** | D2C Brands & Retailers | "We're invisible to AI shopping" | Full catalog optimization + verification |
| **Secondary** | E-commerce Platforms | "Our merchants need AI discoverability" | White-label tools, platform integration |
| **Tertiary** | Commerce Developers | "How do I match products to intent?" | API access |

### Why Brands Will Pay

1. **Measurable lift**: We show before/after discoverability metrics
2. **No ad spend required**: Organic discovery, not paid placement
3. **Data ownership**: Brand keeps optimized content, can use anywhere
4. **Competitive moat**: Early adopters gain discoverability advantage

---

## 7. Competitive Moat

### Why This Is Defensible

| Asset | Why It's Defensible |
|-------|---------------------|
| **Intentionality taxonomy** | Structured mapping of specs → capabilities → outcomes |
| **Legibility scoring** | Consistent, explainable scoring tied to catalog improvements |
| **Before/after dataset** | Proprietary optimization + verification outcomes over time |
| **Protocol-agnostic architecture** | Works with any commerce infrastructure |
| **First-mover in organic LLM discovery** | New category, establishing standards |

### What Competitors Would Need to Replicate

1. Understanding that LLMs do intent inference (not keyword matching)
2. Taxonomy of product capabilities and human goals
3. Scoring system validated against actual LLM behavior
4. Multi-platform adapter architecture
5. Trust from brands who want organic discovery

---

## 8. Demo Flow (60 Seconds)

### The Pitch

1. **Show a user query**: "I need a TV for my bright living room"

2. **Show intent inference**:
   - Primary goal: "Enjoyable viewing despite ambient light"
   - Underlying needs: ["glare reduction", "brightness", "daytime usability"]

3. **Show two products**:
   - Product A: Optimized for intent legibility ("Combat glare in bright rooms")
   - Product B: Specs only ("65-inch 4K QLED, 3000 nits")

4. **Show alignment scores**:
   - Product A: 0.89 (capabilities match intent)
   - Product B: 0.52 (specs present, but not intent-legible)

5. **Show the result**: "Product A gets recommended. Product B doesn't. Same underlying product, different framing."

6. **The close**: "We help brands structure their products to be legible to intent inference. That's organic discovery for AI commerce."

---

## 9. Partnership Positioning

### Value Proposition by Partner

| Partner | Why They Need Us |
|---------|------------------|
| **Google** | Direct Offers handles paid. Organic discovery is unaddressed. Complementary offering. |
| **OpenAI** | "Answer independence" means best product wins. We help brands become the best product. |
| **Shopify** | Merchants want AI discoverability. We provide it without requiring ad spend. |
| **Brands/Retailers** | Direct route to AI recommendations without paying per click. |

### Integration Scenarios

1. **Merchant tools**: Shopify app for intentionality optimization
2. **Platform integration**: Optional discovery layer if LLM providers want a neutral partner
3. **API service**: Developers building commerce agents use our APIs
4. **White-label**: Brands use our technology under their branding

---

## Summary

**The strategic position**:

- Google built paid placement for AI commerce
- OpenAI built answer independence
- **We built organic discovery**

Products that genuinely serve user intent get recommended by reasoning agents. We make products legible to that reasoning and prove the lift. That's the intentionality advantage.

**One-line positioning**:

*"SEO for reasoning agents—help brands become discoverable by AI."*

---

*Document Version: 2026-01-20*
*Status: Active*
