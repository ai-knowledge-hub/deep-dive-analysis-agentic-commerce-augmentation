# Architecture v2: LLM Discoverability Simulation Sandbox

## Purpose

This system is a **simulation sandbox for AI shopping discoverability**.

Brand marketers ask: "Why isn't my product showing up in ChatGPT or Google AI Mode?" We give them the answer and a way to fix it.

When an AI agent recommends products, it doesn't match keywords, it infers what the user is trying to achieve and selects products that serve that goal. Products structured around human capabilities and outcomes get recommended. Products described in pure specs don't.

We let brands **see what the LLM sees**, understand why they're losing, and test changes until they win.

---

## The User Problem

> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

See [user-problem.md](user-problem.md) for detailed user personas and pain points.

## Architecture Evolution (Agentic + Clean)

This codebase is transitioning from a monolithic module layout to a layered architecture that better supports:
- Two-layer discovery (inference/web + protocol/feeds)
- Replayable, observable runs (for calibration)
- Incremental migration without breaking features (strangler pattern)

Reference docs:
- `docs/2-layer-arch/arch-migratoion/agentic-arch-transformation.md`
- `docs/2-layer-arch/arch-migratoion/agentic-arch-execution-summary.md`

### Who We Serve

| Role | Their Question |
|------|----------------|
| **Brand Marketing Manager** | "Why aren't my products showing up in AI results?" |
| **E-commerce Growth Lead** | "I know SEO, but AI works differently, what are the rules?" |
| **Agency Account Manager** | "Client asks why they're not in ChatGPT. I have no tools to answer." |
| **Product Feed Manager** | "I write for keyword search. What should I change for LLMs?" |

### The Missing Feedback Loop

Today, brands have no visibility:

```
Product Data → ??? → LLM Recommendation (or not)
```

We provide the missing loop:

```
Product Data → Analyze → Simulate → See Who Wins → Understand Why → Confirm Tone → Optimize → Re-Test
     ↑                                                                              │
     └──────────────────────────────────────────────────────────────────────────────┘
```

---

## The Solution: Simulation Sandbox

Think of it as a **flight simulator for AI shopping**. Brands can:

1. **Set up a test scenario**: query + their product + competitors
2. **Run a simulation**: see which product the LLM would recommend
3. **Understand the gap**: why did they lose? what's missing?
4. **Confirm brand tone**: accept or edit the suggested voice
5. **Optimize**: apply suggested changes to product description
6. **Re-test**: verify the changes improved their score

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
│  │ Tone Profiling + Rewrite                             │    │
│  │ Derive brand tone and rewrite intent-legible copy    │    │
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

Note: In production, evidence sources can be replaced by brand product data and protocol feeds
as a future phase. The pipeline stays the same.
```

---

## Database ERD (Multi-Tenant v1)

```
clients (id, name)
  ├─< brands (id, client_id, name)
  │     └─< products (id, brand_id, name, description)
  └─< client_users (id, client_id, user_id, role)

users (id, preferences_json, metadata_json)
  ├─< sessions (id, user_id, client_id, brand_id, state_json)
  │     ├─< turns (id, session_id, speaker, content)
  │     ├─< goals (id, user_id, session_id, client_id, brand_id, goal_text)
  │     └─< recommendations (id, session_id, client_id, product_ids_json)
  ├─< episodes (id, user_id, session_id, client_id, outcome)
  └─< semantic_memory (id, user_id, client_id, key, value_json, embedding)

simulation_runs (id, user_id, session_id, client_id, brand_id, product_id, query, result_json)
  └─< simulation_lessons (id, run_id, user_id, client_id, lesson)
```

Notes:
- `client_id` scopes all data for tenant isolation.
- `brand_id` is optional and only set when a chat/simulation is explicitly tied to a brand.
- `product_id` is optional to allow simulations without product records.

---

## Core Modules

### 1. Intent Module (`domain/intent/` + `application/services/*`)

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

### 2. Product Intentionality Module (`domain/intentionality/`)

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

**Note:** The legacy “empowerment” framing has been removed; intentionality is now the core representation layer.

---

### 3. Alignment Scoring Module (`domain/alignment/` + `infrastructure/alignment/*`)

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

### 4. Simulation Sandbox Module (`domain/simulation/` + `application/services/simulation_service.py`)

**Purpose**: Run competitive scenarios, surface gaps, and drive the optimize → retest loop.

**Key outputs**:
- Ranked scores + winner
- Gap analysis (“why you lost”)
- Suggested tone (auto-derived from product copy)
- Optimization rewrite with confirmed tone
- Semantic gap matching (embeddings + keyword fallback)
- Lessons learned (winner vs loser takeaways)
- Lessons persisted per user for reuse across runs

---

### 5. Context Memory Module (`domain/memory/` + `infrastructure/db/*`)

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

### 6. Protocol Integrations (ACP/UCP)

**Purpose**: Validate protocol readiness and surface discovery gaps for ACP and UCP.

**Scope (v1)**:
- Business profile discovery + negotiation/intersection (UCP)
- Feed readiness checks + delegated payment readiness (ACP)
- Protocol readiness issues surfaced in simulation output

**Note**: External catalog adapters (Shopify/Merchant Center) are removed from the v1
scope to keep the product focused on protocol readiness and simulation feedback loops.

---

## What's Removed

The following legacy concepts are **deprecated** in this architecture:

| Removed | Reason |
|---------|--------|
| Manipulation detection framing | User-protection framing; not core to brand discovery |
| Post-purchase reflection loop | Nice-to-have; not core to the simulation sandbox |
| Constraint enforcement gates | Not core to intent legibility / discovery simulation |
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

**Multi-tenant requirement:** Every request includes `client_id` unless the caller is an admin user. `brand_id` and `product_id` are optional on simulation endpoints to link runs to product records.

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

Catalog automation endpoints are deferred; v1 focuses on simulation,
query batteries, and protocol readiness (ACP/UCP).

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

1. Automated product data enrichment (future)
2. Multi-LLM testing harness (AI Mode, ChatGPT, Claude)
3. Brand dashboard showing discoverability metrics

### P2 — Scale

1. Batch product processing (future)
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

We don't sit in the runtime path between users and LLMs. We optimize the *source data* that LLMs eventually discover—through ACP/UCP profiles today, and (future) Merchant Center feeds, Shopify stores, website content, and structured data.

Think of it as **SEO for LLMs**: just as SEO agencies optimize websites for Google Search, we optimize product data for AI recommendations.

### The Brand Workflow (Future)

**Current release focus:** ACP/UCP protocol readiness + simulation feedback loops.  
Catalog connection + enrichment workflows below are deferred until post‑v1.

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
│     • Overall product legibility score                       │
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
| **Analysis** | One-time legibility report | Per‑product data fee |
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
| Batch product processing | Not built | P1 |
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
