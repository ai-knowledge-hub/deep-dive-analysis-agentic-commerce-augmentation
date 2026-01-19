# Strategic Positioning: Organic Discovery for AI Commerce

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

### Core Offering: Intentionality Optimization

1. **Catalog Analysis**
   - Ingest product feeds (Shopify, Google Merchant, custom)
   - Score current "intent legibility" of each product
   - Identify discovery gaps

2. **Intentionality Profiling**
   - Transform specs → capabilities → outcomes
   - Generate intent-legible product descriptions
   - Map products to user goal categories

3. **Alignment Prediction**
   - Predict which products LLMs will recommend for which intents
   - Identify misalignments (good products that won't surface)
   - Provide optimization recommendations

4. **Discovery Metrics**
   - Track recommendation frequency across LLM surfaces
   - Measure alignment score accuracy
   - Report discoverability trends

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

### Revenue Streams

| Stream | Description |
|--------|-------------|
| **Catalog Analysis** | One-time or periodic analysis of brand's product data |
| **Intentionality SaaS** | Ongoing optimization and monitoring |
| **API Access** | Intent inference + alignment scoring for developers |
| **Enterprise** | White-label for platforms, custom integrations |

### Target Customers

**Primary**: Brands/retailers who want LLM recommendations
- Problem: "We're not showing up in AI shopping results"
- Solution: Intentionality optimization for organic discovery

**Secondary**: Commerce platforms who want better recommendations
- Problem: "Our recommendations don't match user intent well"
- Solution: Intent inference + alignment scoring layer

**Tertiary**: Developers building commerce agents
- Problem: "How do I match products to what users actually want?"
- Solution: Our APIs

---

## 7. Competitive Moat

### Why This Is Defensible

| Asset | Why It's Defensible |
|-------|---------------------|
| **Intent inference models** | Trained on goal-product relationships, improves with usage |
| **Intentionality taxonomy** | Structured mapping of specs → capabilities → outcomes |
| **Alignment scoring** | Empirically validated against LLM recommendations |
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

1. **Platform integration**: Provide intentionality layer to Google AI Mode, ChatGPT Shopping
2. **Merchant tools**: Shopify app for intentionality optimization
3. **API service**: Developers building commerce agents use our APIs
4. **White-label**: Brands use our technology under their branding

---

## Summary

**The strategic position**:

- Google built paid placement for AI commerce
- OpenAI built answer independence
- **We built organic discovery**

Products that genuinely serve user intent get recommended by reasoning agents. We make products legible to that reasoning. That's the intentionality advantage.

**One-line positioning**:

*"SEO for reasoning agents—help brands become discoverable by AI."*

---

*Document Version: 2026-01-17*
*Status: Active*
