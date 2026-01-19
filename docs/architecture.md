# Architecture v2: Intentionality Optimization Layer

## Purpose

This system makes products **legible to LLM intent inference**.

When an AI agent recommends products, it doesn't match keywords — it infers what the user is trying to achieve and selects products that serve that goal. Products structured around human capabilities and outcomes get recommended. Products described in pure specs don't.

We help brands become **discoverable by reasoning agents**.

---

## The Problem We Solve

Google's Direct Offers lets retailers pay to appear in AI Mode recommendations. But paid placement doesn't make the AI *trust* your product — it just puts you in the auction.

Organic discovery in LLM commerce requires something different: **alignment between product attributes and inferred user intent**.

This is SEO for reasoning agents.

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
│                     Brand / Merchant                         │
│              Product catalog, offers, content                │
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
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Commerce Surfaces                           │
│     Google AI Mode │ ChatGPT Shopping │ Claude │ Others     │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### 1. Intent Module (`modules/intent/`)

**Purpose**: Infer user goals from observable signals.

**Inputs**:
- User query (natural language)
- Session context (previous turns, stated preferences)
- Memory (historical goals, past purchases, reflections)

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

## Demo Flow

The system should support this demo in 60 seconds:

1. **Show a user query**: "I need a TV for my bright living room"

2. **Show intent inference**:
   - Primary goal: "Enjoyable viewing despite ambient light"
   - Underlying needs: ["glare reduction", "brightness", "daytime usability"]

3. **Show two products**:
   - Product A: "65-inch 4K QLED, 3000 nits, anti-reflective coating"
   - Product B: "65-inch 4K QLED, 3000 nits" (same specs, no intent language)

4. **Show alignment scores**:
   - Product A: 0.89 (capabilities match intent)
   - Product B: 0.52 (specs present, but not intent-legible)

5. **Show the result**: "Product A gets recommended. Product B doesn't. Same product, different framing."

6. **The pitch**: "We help brands structure their products to be legible to intent inference. That's organic discovery for AI commerce."

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

### For Brands (Future)

```
POST /catalog/analyze
  Input: { catalog_url or feed }
  Output: { products_analyzed, intent_legibility_scores, recommendations }

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


