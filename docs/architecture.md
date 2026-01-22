# Architecture v2: LLM Discoverability Simulation Sandbox

## Purpose

This system is a **simulation sandbox for AI shopping discoverability**.

Brand marketers ask: "Why isn't my product showing up in ChatGPT or Google AI Mode?" We give them the answer—and a way to fix it.

When an AI agent recommends products, it doesn't match keywords—it infers what the user is trying to achieve and selects products that serve that goal. Products structured around human capabilities and outcomes get recommended. Products described in pure specs don't.

We let brands **see what the LLM sees**, understand why they're losing, and test changes until they win.

---

## The User Problem

> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

See [user-problem.md](user-problem.md) for detailed user personas and pain points.

### Who We Serve

| Role | Their Question |
|------|----------------|
| **Brand Marketing Manager** | "Why aren't my products showing up in AI results?" |
| **E-commerce Growth Lead** | "I know SEO, but AI works differently—what are the rules?" |
| **Agency Account Manager** | "Client asks why they're not in ChatGPT. I have no tools to answer." |
| **Product Feed Manager** | "I write for keyword search. What should I change for LLMs?" |

### The Missing Feedback Loop

Today, brands have no visibility:

```
Product Data → ??? → LLM Recommendation (or not)
```

We provide the missing loop:

```
Product Data → Analyze → Simulate → See Who Wins → Understand Why → Optimize → Re-Test
     ↑                                                                              │
     └──────────────────────────────────────────────────────────────────────────────┘
```

---

## The Solution: Simulation Sandbox

Think of it as a **flight simulator for AI shopping**. Brands can:

1. **Set up a test scenario**: query + their product + competitors
2. **Run a simulation**: see which product the LLM would recommend
3. **Understand the gap**: why did they lose? what's missing?
4. **Optimize**: apply suggested changes to product description
5. **Re-test**: verify the changes improved their score

This is a closed feedback loop—the key differentiator from static "legibility reports."

---

## How OpenAI and Google Shopping Work

Our simulation models how real LLM shopping agents behave:

| Platform | Discovery Layer | Implication |
|----------|-----------------|-------------|
| **OpenAI Shopping** | Pure organic—model picks based on relevance, no paid boost | If you're not legible to intent reasoning, you're invisible |
| **Google AI Mode + UCP** | Organic + ads—paid gets you in candidate pool, LLM picks winners | Even with ads, the LLM chooses based on intent alignment |

**Key insight**: In both ecosystems, the LLM is the gatekeeper. Our simulation predicts what it will do.

---

## Core Thesis

LLMs trained on human text have learned to model:
- What humans want (goals, preferences)
- Why they want it (underlying needs, capabilities sought)
- What satisfies those wants (products as means to ends)

This is a form of **intent inference** — the model predicts what would satisfy the user based on contextual signals.

Products that are structured to be legible to this inference process get recommended. Products that aren't get overlooked — regardless of quality or ad spend.

**We operationalize this insight.**

---

## Theoretical Foundation

The system is grounded in:

1. **Bayesian Intent Inference** — User goals are latent variables inferred from observable signals (queries, context, history). Products are scored on posterior probability of serving those goals.

2. **Active Inference / Free Energy** — LLMs can be modeled as agents minimizing predictive surprise (ref. Karl Friston). Recommendations that align with inferred intent reduce uncertainty. Products that "make sense" given user context are low-surprise options.

3. **Theory of Mind in LLMs** — Research suggests large language models develop emergent ability to model beliefs, desires, and intentions. We leverage this by structuring products in terms of human-centric attributes.

This foundation informs architecture but does not dominate user-facing messaging. The theory explains *why* it works; the demo shows *that* it works.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Evidence Sources (web/product pages)            │
│              Product representations, content                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              INTENTIONALITY OPTIMIZATION LAYER               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Product Intentionality Mapping                       │    │
│  │ Transform specs → capabilities → outcomes            │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Intent Inference Engine                              │    │
│  │ Model user goals from query + context + memory       │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Alignment Scoring                                    │    │
│  │ Score products against inferred intent               │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Context Memory                                       │    │
│  │ Persist goals, preferences, history for inference    │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Verification + Reporting                             │    │
│  │ Measure discoverability lift (pre/post)              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Commerce Surfaces                           │
│     Google AI Mode │ ChatGPT Shopping │ Claude │ Others     │
└─────────────────────────────────────────────────────────────┘

Note: In production, evidence sources are replaced by brand catalogs and feeds
(Shopify, Merchant Center, JSON-LD). The pipeline stays the same.
```

---

## Core Modules

### 1. Intent Module (`modules/intent/`)

**Purpose**: Infer user goals from observable signals.

**Inputs**:
- User query (natural language)
- Session context (previous turns, stated preferences)
- Memory (historical goals, past purchases, reflections)
- Goal clarification state (when present)
- User identity (optional; used to scope sessions and memory)

**Outputs**:
- `InferredIntent`: Structured representation of what user is trying to achieve
- `IntentConfidence`: Uncertainty estimate
- `IntentSignals`: Evidence used for inference

**Key insight**: Intent is not stated, it's inferred. "I need a laptop" doesn't tell you the intent. "I'm transitioning to freelance design work" does.

```python
@dataclass
class InferredIntent:
    primary_goal: str           # "Enable portable creative work"
    underlying_needs: List[str] # ["professional credibility", "mobility", "creative software support"]
    context_signals: List[str]  # Evidence from query/session
    confidence: float           # 0.0-1.0
```

---

### 2. Product Intentionality Module (`modules/intentionality/`)

**Purpose**: Transform product data into intent-legible format.

**The transformation**:
```
Raw Product Data          →    Intent-Legible Product
─────────────────────────────────────────────────────
"4K, 65-inch, QLED"       →    "Combat glare in bright rooms"
"16GB RAM, M3 chip"       →    "Run professional creative software"
"Ergonomic lumbar"        →    "Reduce back pain during long sessions"
```

**Key concept**: Products are **means to ends**. Specs describe the means. Capabilities describe the ends. LLMs reason about ends.

```python
@dataclass
class IntentionalityProfile:
    product_id: str
    capabilities_enabled: List[str]    # What human capabilities this enables
    goals_served: List[str]            # What goals this helps achieve
    prerequisites: List[str]           # What user needs to benefit
    outcomes_expected: List[str]       # What changes after purchase
    context_fit: Dict[str, float]      # Fit scores for different contexts
```

**This module replaces**: `modules/empowerment/` (reframed from "user protection" to "intent legibility")

---

### 3. Alignment Scoring Module (`modules/alignment/`)

**Purpose**: Score products against inferred intent.

**Method**:
1. Embed user intent and product intentionality profiles
2. Compute alignment via semantic similarity + structured matching
3. Adjust for context (user history, stated preferences)
4. Return ranked products with alignment explanations

```python
@dataclass
class AlignmentScore:
    product_id: str
    score: float                    # 0.0-1.0
    matched_capabilities: List[str] # Which capabilities match intent
    alignment_reasoning: str        # Human-readable explanation
    confidence: float               # Certainty of the match
```

**Key insight**: High alignment = LLM will recommend. Low alignment = LLM will skip. We make this predictable.

---

### 4. Context Memory Module (`modules/memory/`)

**Purpose**: Persist context that improves intent inference over time.

**What we store**:
- Declared goals (user's own words)
- Inferred preferences (from behavior)
- Purchase history (what they've bought)
- Outcome data (did it work? — optional reflection)

**What we don't store**:
- Behavioral tracking for manipulation
- Signals used for urgency/scarcity
- Data without clear inference value

**Architecture**:
- `working.py` — Session-scoped context
- `semantic.py` — Long-term goals and preferences
- `episodic.py` — Specific interactions and outcomes (optional)

**Identity + sessions**:
- Sessions are persisted in SQLite and scoped by `user_id`.
- The demo uses Clerk for lightweight auth (free tier) to supply `user_id`.
  If auth is disabled, a default user scope is used.

Memory enables **better inference**, not surveillance. The distinction matters.

---

### 5. Commerce Adapters (`modules/commerce/adapters/`)

**Purpose**: Ingest product data from any source, transform to our schema.

**Adapters**:
- `mock.py` — Testing
- `shopify.py` — Shopify Storefront API
- `google_merchant.py` — Merchant Center feeds
- `ucp.py` — Google Universal Commerce Protocol (future)

**Pipeline**:
```
External Feed → RawOffer → IntentionalityProfile → Aligned Product
```

Each adapter normalizes source data; the intentionality module enriches it.

---

## What's Removed

The following modules/concepts are **deprecated** in this architecture:

| Removed | Reason |
|---------|--------|
| `empowerment/alienation.py` | "Manipulation detection" is user-protection framing; doesn't serve brand discovery |
| `empowerment/reflection.py` | Post-purchase follow-up is nice-to-have, not core |
| `conversation/guards.py` | Constraint enforcement is user-protection framing |
| World A vs World B comparison | Ethical framing; distracts from value prop |
| Impulse interception | User-protection feature; not core to intent legibility |
| Dual dashboard (agency metrics) | Measures user outcomes; we measure brand discoverability |
| "No purchase needed" path | User-protection feature |
| Consent gates | GDPR-style framing; orthogonal to core value |

These may return as features later, but they're not the core product.

---

## What's Renamed/Reframed

| Old Name | New Name | Why |
|----------|----------|-----|
| Empowerment scoring | Alignment scoring | Describes what it does, not why |
| Goal alignment | Intent alignment | "Intent" is the core concept |
| Agency metrics | Discovery metrics | We measure brand visibility, not user agency |
| World B | (removed) | Ethical framing; now implicit |
| Capability expansion | Capability mapping | Describes the function |

---

## Demo Flow: The Simulation Sandbox

The demo shows the complete feedback loop in 60 seconds:

### Step 1: Set Up Scenario

```
Query: "I need a TV for my bright living room"

Your Product: Samsung QN90B
  "65-inch 4K QLED, 3000 nits brightness"

Competitors:
  - LG C3 OLED: "Bright room viewing, anti-glare technology"
  - Sony A80K: "4K OLED with anti-reflective coating"
```

### Step 2: Run Simulation

```
Inferred User Intent:
  Primary goal: "Enjoyable viewing despite ambient light"
  Underlying needs: ["glare reduction", "brightness", "daytime usability"]
```

### Step 3: See Results

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ LG C3           │ │ Samsung QN90B   │ │ Sony A80K       │
│ Score: 0.78     │ │ Score: 0.52     │ │ Score: 0.61     │
│ ✅ RECOMMENDED  │ │ ❌ NOT PICKED   │ │ ❌ NOT PICKED   │
└─────────────────┘ └─────────────────┘ └─────────────────┘

WHY YOU LOST:
• Missing: outcome framing ("Combat glare")
• Missing: context fit ("bright living room")
• Present but hidden: 3000 nits (the actual differentiator)
```

### Step 4: Optimize

```
Suggested Change:
  Before: "65-inch 4K QLED, 3000 nits brightness"
  After:  "Combat glare in bright rooms. Clear picture without
           closing blinds. 65-inch 4K QLED with 3000 nits."

[Apply & Re-Test]
```

### Step 5: Verify

```
Samsung QN90B: 0.52 → 0.85
✅ NOW RECOMMENDED

Lift: +63% alignment score
```

### The Pitch

> "See what the LLM sees. Fix what's broken. Test until you win."

---

## API Surface

### Core Endpoints

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

POST /products/enrich
  Input: { raw_product }
  Output: { enriched_product_with_intentionality }
```

### Evidence-First Demo (Current)

```
POST /evidence/analyze
  Input: { query }
  Output: { evidence_products, profiles, alignment_scores }

POST /representation/optimize
  Input: { evidence_products }
  Output: { before_after_pairs, alignment_deltas }

POST /recommendation/verify
  Input: { query, evidence_products }
  Output: { predicted_vs_actual, lift }
```

### For Brands (Future)

```
POST /catalog/analyze
  Input: { catalog_url or feed }
  Output: { products_analyzed, intent_legibility_scores, recommendations }

POST /catalog/optimize
  Input: { product_ids, optimization_types? }
  Output: { suggestions, alignment_deltas }

POST /catalog/verify
  Input: { scenarios, baseline? }
  Output: { recommendation_rates, lift }

GET /catalog/{catalog_id}/report
  Output: { discoverability_report }
```

---

## Success Metrics

### Primary: Intent Alignment Accuracy

"When we predict a product will be recommended by an LLM, is it?"

- Test against AI Mode, ChatGPT, Claude
- Measure correlation between our alignment scores and actual LLM recommendations

### Secondary: Brand Discoverability Lift

"Do brands using our system get recommended more often?"

- A/B test: same products with/without intentionality enrichment
- Measure recommendation frequency across LLM surfaces

### Tertiary: Inference Quality

"Do we correctly infer user intent?"

- Human evaluation of inferred intents
- Downstream alignment accuracy as proxy

---

## Implementation Priorities

### P0 — Hackathon Critical

1. Intent inference from query + context
2. Product intentionality profiling (manual + LLM-assisted)
3. Alignment scoring with explanations
4. Demo UI showing the full flow
5. 3-5 compelling product examples

### P1 — Strategic Value

1. Automated catalog enrichment
2. Multi-LLM testing harness (AI Mode, ChatGPT, Claude)
3. Brand dashboard showing discoverability metrics

### P2 — Scale

1. Batch catalog processing
2. Real-time feed integration
3. Historical discoverability tracking

---

## Relationship to External Systems

### Google Direct Offers

We are **complementary**, not competitive:
- Direct Offers = paid placement (auction)
- Our system = organic discoverability (alignment)

Brands need both. We're the organic path.

### UCP / ACP

We sit **above** the protocol layer:
- UCP/ACP define how transactions flow
- We define how products become recommendable

Protocol-agnostic. Works with any commerce infrastructure.

### LLM Providers

We are **LLM-agnostic**:
- Our scoring predicts what *any* reasoning LLM will recommend
- We test against multiple providers
- No dependency on specific model internals

---

## Product: Brand Catalog Optimization

### The Use Case

**We are a brand-side optimization tool.** Brands pay us to make their products discoverable by AI.

We don't sit in the runtime path between users and LLMs. We optimize the *source data* that LLMs eventually discover—through Merchant Center feeds, Shopify stores, website content, and structured data.

Think of it as **SEO for LLMs**: just as SEO agencies optimize websites for Google Search, we optimize product catalogs for AI recommendations.

### The Brand Workflow

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
│     Score current intent legibility of each product          │
│     • Overall catalog legibility score                       │
│     • Per-product breakdown                                  │
│     • Gap analysis: what's missing for discoverability       │
│     • Priority ranking: which products to optimize first     │
│                                                              │
│     Output: Catalog Legibility Report                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. OPTIMIZE                                                 │
│     Generate intent-aligned product descriptions             │
│     • Transform specs → capabilities → outcomes              │
│     • Preserve brand voice and tone                          │
│     • Generate A/B variants for testing                      │
│     • Human review queue for approval                        │
│                                                              │
│     Input: "65-inch 4K QLED, 3000 nits"                     │
│     Output: "Combat glare in bright living rooms.            │
│              Clear picture without closing blinds.           │
│              65-inch 4K QLED with 3000 nits brightness."    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. DEPLOY                                                   │
│     Push optimized content back to brand's systems           │
│     • Update Shopify product descriptions                    │
│     • Update Merchant Center feeds                           │
│     • Generate JSON-LD structured data for website           │
│     • Version control for rollback                           │
│                                                              │
│     Result: Brand's live product data is now intent-legible  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. VERIFY                                                   │
│     Test and monitor discoverability                         │
│     • Run products against LLM recommendation queries        │
│     • Track "did we get recommended?" over time              │
│     • Compare against competitors                            │
│     • Alert on discoverability changes                       │
│                                                              │
│     Output: Discoverability Dashboard                        │
└─────────────────────────────────────────────────────────────┘
```

### What Happens After Optimization

Once we optimize a brand's product data, the improvement propagates everywhere:

```
                    Brand's Optimized Product Data
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │ Shopify  │        │ Merchant │        │ Website  │
    │ Store    │        │ Center   │        │ + JSON-LD│
    └──────────┘        └──────────┘        └──────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                    LLMs discover this data via:
                    • Web browsing (AI Mode, Operator)
                    • Product feeds (Shopping integrations)
                    • Structured data (JSON-LD parsing)
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │ Google   │        │ ChatGPT  │        │ Claude   │
    │ AI Mode  │        │ Shopping │        │          │
    └──────────┘        └──────────┘        └──────────┘
                              │
                              ▼
                    User gets recommendation
                    (Brand's product is now discoverable)
```

### Revenue Model

| Tier | What Brand Gets | Pricing Model |
|------|-----------------|---------------|
| **Analysis** | One-time legibility report | Per-catalog fee |
| **Optimization** | Rewritten product descriptions | Per-product or flat fee |
| **SaaS** | Ongoing monitoring + re-optimization | Monthly subscription |
| **Enterprise** | Custom integration + priority support | Annual contract |

### Why This Works

1. **No LLM partnership required.** We optimize source data that LLMs already access.

2. **Brands control their data.** We're a tool they use, not a middleman.

3. **Measurable ROI.** We can show before/after discoverability changes.

4. **Protocol-agnostic.** Works regardless of which commerce protocols (UCP, ACP) win.

5. **Complements paid placement.** Google Direct Offers is paid. We're organic. Brands need both.

---

## Hackathon vs. Production Scope

### Hackathon Demo (Current)

| Component | Status |
|-----------|--------|
| Intent inference | ✅ Live |
| Intentionality profiling | ✅ Live |
| Alignment scoring | ✅ Live |
| API endpoints | ✅ Live |
| Demo UI | ✅ Live |
| Before/after comparison | ✅ Live |

**Demo flow:** Upload product → Show legibility analysis → Show optimized version → Show alignment score improvement

### Production (Post-Hackathon)

| Component | Status | Priority |
|-----------|--------|----------|
| Shopify OAuth + write-back | Not built | P1 |
| Merchant Center integration | Not built | P1 |
| Batch catalog processing | Not built | P1 |
| LLM testing harness | Not built | P1 |
| Discoverability monitoring | Not built | P2 |
| Brand dashboard | Not built | P2 |
| Competitive analysis | Not built | P3 |

---

## Summary

**What we are:** A simulation sandbox for AI shopping discoverability.

**Who we serve:** Brand marketers, growth leads, and agencies who need to understand and improve AI recommendations.

**The user problem:** "I don't know why my product isn't showing up in AI results."

**The solution:** Test → See who wins → Understand why → Optimize → Re-test.

**What we do:** Simulate LLM shopping behavior so brands can see what the AI sees and fix what's broken.

**Who pays:** Brands who want their products recommended by AI.

**The pitch:** "See what the LLM sees. Fix what's broken. Test until you win."
