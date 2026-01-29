# Strategic Positioning: AI Discoverability Simulation Sandbox

## Executive Summary

Google built paid placement (Direct Offers). OpenAI is building answer independence. **We built the simulation sandbox.**

Brand marketers are asking: *"Why isn't my product showing up in ChatGPT or Google AI Mode?"* They have no tools to investigate, no way to test changes, and no visibility into how LLMs make recommendations.

**We give them the answer—and a way to fix it.**

Our simulation sandbox lets brands:
1. Test their product against a user query
2. See who wins (them or competitors)
3. Understand WHY they lost
4. Confirm brand tone (accept or edit the suggested voice)
5. Optimize and re-test until they win

Gap analysis uses semantic matching (embeddings + keyword fallback), so brands get true intent coverage rather than literal token overlap.

Each simulation run also yields a short "lesson learned" that becomes reusable guidance for future product data optimization.

This document maps our strategic position:
1. The user problem: who we serve and their pain
2. Competitive analysis: paid vs organic discovery
3. Why our approach works (the intentionality thesis)
4. Business positioning

---

## 0. The User Problem

> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

See [user-problem.md](user-problem.md) for full details.

### Who We Serve

| Role | Their Question |
|------|----------------|
| **Brand Marketing Manager** | "Why aren't my products showing up in AI results?" |
| **E-commerce Growth Lead** | "I know SEO, but AI works differently—what are the rules?" |
| **Agency Account Manager** | "Client asks why they're not in ChatGPT. I have no tools to answer." |
| **Product Feed Manager** | "I write for keyword search. What should I change for LLMs?" |

### Why Now

LLMs don't match keywords—they **infer intent**. Existing SEO tools don't help because the ranking factors are completely different. Brands need new tools for this new channel.

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

## 4. The Product: Simulation Sandbox

### Core Concept

**We are a simulation sandbox for AI shopping—like a flight simulator for LLM recommendations.**

Brands can test their products against user queries, see who wins, understand why, and optimize until they win. This closed feedback loop is what's missing from every other tool in the market.

Tone confirmation is a key step in the loop: we auto-derive brand voice from existing copy, let the user confirm it, and then use it in the optimization rewrite.

### The User Journey

```
1. SET UP SCENARIO
   User defines: query + their product + competitors

2. RUN SIMULATION
   App simulates what an LLM shopping agent would do

3. SEE RESULTS
   Who won? Who lost? Why?

4. OPTIMIZE
   Apply suggested changes to product description

5. RE-TEST
   Verify the changes improved the score
```

### Who We Serve

| Customer | Problem | Our Solution |
|----------|---------|--------------|
| **Brands/Retailers** | "My products aren't appearing in AI shopping results" | Simulation sandbox: test → understand → fix |
| **E-commerce platforms** | "Our merchants need AI discoverability tools" | White-label simulation tools |
| **Commerce developers** | "How do I match products to user intent?" | API access to intent + alignment scoring |

### Full Brand Workflow (Production)

In production, the simulation sandbox expands to a full workflow:

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

**Multi-tenant requirement:** All API requests include `client_id`. `brand_id`/`product_id` are optional on simulation endpoints to bind runs to product records.

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

Catalog automation endpoints are intentionally deferred; v1 focuses on
protocol readiness + simulation outcomes.
```

---

## 5. Technical Integration

### Protocol-Agnostic Design

We work above the protocol layer, focusing on readiness and simulation:

```
ACP/UCP Profiles + Feeds
    │
    ▼
Protocol Readiness Checks
    │
    ▼
Simulation + Gap Analysis
```

External catalog adapters (Shopify/Merchant Center) are intentionally out of scope
for the first release to keep the product focused on protocol readiness.

### Data Flow

```
Brand Protocol Metadata
    │
    ▼
┌─────────────────────────────────────────┐
│ Protocol Readiness (ACP/UCP)            │
│ Validate feeds + business profiles      │
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
| **Brand wants more AI recommendations** | Analyze product data, optimize intentionality, measure lift |
| **Platform wants better recommendations** | Provide intent inference + alignment scoring as service |
| **Developer building commerce agent** | Use our APIs to match products to user intent |

---

## 6. Business Model

### Who Pays: Brands

Brands pay us to make their products more discoverable by AI. This is analogous to traditional SEO services, but for reasoning agents instead of keyword search.

### Revenue Streams

| Stream | What Brand Gets | Pricing Model |
|--------|-----------------|---------------|
| **Product Data Audit** | One-time discoverability report + recommendations | Per‑product data fee |
| **Optimization SaaS** | Ongoing enrichment, monitoring, re-optimization | Monthly subscription |
| **API Access** | Programmatic intent + alignment scoring | Usage-based |
| **Enterprise** | White-label for platforms, custom integration | Contract |

### Customer Tiers

| Tier | Customer | Problem | Solution |
|------|----------|---------|----------|
| **Primary** | D2C Brands & Retailers | "We're invisible to AI shopping" | Product data optimization + verification (future) |
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
| **Legibility scoring** | Consistent, explainable scoring tied to product data improvements |
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

### The Simulation Sandbox Demo

1. **Set up the scenario**:
   - Query: "I need a TV for my bright living room"
   - Brand's product: Samsung QN90B ("65-inch 4K QLED, 3000 nits")
   - Competitors: LG C3 ("Bright room viewing, anti-glare"), Sony A80K

2. **Run simulation**: App infers user intent and scores all products

3. **Show results**:
   - LG C3: 0.78 ✅ RECOMMENDED
   - Samsung QN90B: 0.52 ❌ NOT PICKED
   - Sony A80K: 0.61 ❌ NOT PICKED

4. **Explain why brand lost**:
   - Missing: outcome framing ("Combat glare")
   - Missing: context fit ("bright living room")
   - Present but hidden: 3000 nits (the actual differentiator)

5. **Show optimization**:
   - Before: "65-inch 4K QLED, 3000 nits"
   - After: "Combat glare in bright rooms. Clear picture without closing blinds."

6. **Re-test and verify**:
   - Samsung QN90B: 0.52 → 0.85 ✅ NOW RECOMMENDED

7. **The pitch**: "See what the LLM sees. Fix what's broken. Test until you win."

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
- **We built the simulation sandbox**

Brands ask: "Why isn't my product showing up in AI results?" We give them the answer and a way to fix it.

**One-line positioning**:

*"See what the LLM sees. Fix what's broken. Test until you win."*

**The user problem we solve**:

> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

**The solution**:

A simulation sandbox where brands can test products against queries, see who wins, understand why, and optimize until they win.

---

*Document Version: 2026-01-22*
*Status: Active*
