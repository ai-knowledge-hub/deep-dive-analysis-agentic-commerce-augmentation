# Terminology Glossary

This document defines the core terms used across the AI Discoverability Simulation Sandbox codebase.

The goal is to ensure **conceptual precision**, prevent semantic drift, and align architecture with implementation.

---

## Simulation Sandbox

**Definition**
A test environment where brand marketers can simulate LLM shopping behavior to understand why their products do or don't get recommended.

**Core Loop**
```
SET UP SCENARIO → SIMULATE → SEE RESULTS → OPTIMIZE → RE-TEST
```

**Key Property**
> The simulation sandbox solves the core user problem: "I don't know what the LLM sees when it decides whether to recommend my product."

**In Code**
```
api/routes/simulation.py
web/components/simulation/*
```

---

## Gap Analysis

**Definition**
The explanation of why a product lost in a competitive simulation—what's missing, what's hidden, and what to fix.

**Components**
- Missing elements: capabilities the product doesn't express
- Hidden strengths: features present but not highlighted in intent-legible form
- Optimization suggestions: specific changes to make

**In Code**
```
domain/simulation/gap_analysis.py
```

---

## Intentionality Optimization

**Definition**
Intentionality Optimization is an **optimization paradigm** for LLM commerce discovery.

Systems using intentionality optimization:
- Transform product data to be **legible to LLM intent inference**
- Score products on **alignment with inferred user goals**
- Predict which products LLMs will **recommend organically**

**Key Property**
> Intentionality optimization is defined by making products discoverable by reasoning agents, not by keyword matching or ad bidding.

This repository represents the **first implementation of intentionality optimization for commerce**.

---

## Intent Inference

**Definition**
Intent inference is the process by which LLMs determine what a user is **actually trying to achieve** from their query and context.

Intent inference:
- Goes beyond surface queries to underlying goals
- Considers context, history, and implicit signals
- Produces structured representations of user intent

**In Code**

```
domain/intent/*
infrastructure/llm/intent_classifier.py
```

**Example**
- Query: "I need a laptop"
- Inferred Intent: "Enable portable creative work for freelance transition"
- Underlying Needs: ["professional credibility", "mobility", "creative software support"]

---

## Inferred Intent

**Definition**
The structured output of intent inference, representing what the user is trying to achieve.

**Data Structure**
```python
@dataclass
class InferredIntent:
    primary_goal: str           # "Enable portable creative work"
    underlying_needs: List[str] # ["professional credibility", "mobility"]
    context_signals: List[str]  # Evidence from query/session
    confidence: float           # 0.0-1.0
```

---

## Intentionality Profile

**Definition**
A structured representation of a product in terms of **human capabilities and outcomes**, not just specifications.

Intentionality profiles:
- Transform specs into capabilities
- Map features to human goals
- Describe expected outcomes

**Data Structure**
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

**In Code**

```
domain/intentionality/profiling.py
domain/intentionality/types.py
```

---

## Intent Legibility

**Definition**
The degree to which a product's data is structured in a way that LLMs can reason about for intent alignment.

**High Intent Legibility**
- "Combat glare in bright rooms"
- "Run professional creative software"
- "Reduce back pain during long sessions"

**Low Intent Legibility**
- "65-inch 4K QLED, 3000 nits"
- "16GB RAM, M3 chip"
- "Ergonomic lumbar support"

Products with high intent legibility get recommended. Products with low intent legibility get overlooked.

---

## Alignment Score

**Definition**
A numerical measure (0.0-1.0) of how well a product's intentionality profile matches an inferred user intent.

**Data Structure**
```python
@dataclass
class AlignmentScore:
    product_id: str
    score: float                    # 0.0-1.0
    matched_capabilities: List[str] # Which capabilities match intent
    alignment_reasoning: str        # Human-readable explanation
    confidence: float               # Certainty of the match
```

**Key Property**
> High alignment score = LLM will recommend. Low alignment score = LLM will skip.

**In Code**

```
domain/alignment/scoring.py
infrastructure/alignment/goal_alignment_gateway.py
```

---

## Brand Tone

**Definition**
The stylistic voice of a brand’s product copy (formality, sentence length, jargon level, adjective density).

**How it’s used**
- Auto-derived from product copy
- Confirmed by the user via a tone card
- Injected into optimization rewrites

**In Code**
```
domain/simulation/tone.py
shared/llm/prompts.py
```

---

## Organic Discovery

**Definition**
Products appearing in LLM recommendations without paid placement—because they genuinely align with user intent.

**Contrast with Paid Placement**
| Paid Placement | Organic Discovery |
|---------------|------------------|
| Pay to appear in results | Recommended because aligned |
| Auction-based bidding | Intent-based matching |
| Direct Offers (Google) | Intentionality optimization |

Brands need both. We provide the organic path.

---

## Capability Mapping

**Definition**
The transformation of product specifications into human capabilities.

**Examples**
| Specification | Capability |
|--------------|------------|
| "3000 nits brightness" | "Combat glare in bright rooms" |
| "M3 chip, 16GB RAM" | "Run professional creative software" |
| "Lumbar support, adjustable arms" | "Reduce back pain during long sessions" |

**In Code**

```
domain/intentionality/profiling.py
```

---

## Discovery Metrics

**Definition**
Measurements of how well intentionality optimization works.

| Metric | Description |
|--------|-------------|
| Alignment Accuracy | Correlation between our scores and actual LLM recommendations |
| Discoverability Lift | Increase in recommendations after optimization |
| Inference Quality | Accuracy of inferred intents (human evaluation) |

**In Code**

Planned (see `docs/build-plan.md` Phase 4).

---

## Memory (Context Memory)

**Definition**
Persistent context that improves intent inference over time.

| Type | Description |
|------|-------------|
| Working Memory | Current session context |
| Semantic Memory | Long-term goals and preferences |
| Episodic Memory | Purchase history for inference |

Memory enables **better inference**, not surveillance.

**In Code**

```
domain/memory/
infrastructure/db/
```

---

## UCP — Universal Commerce Protocol

**Definition**
Google's open standard for agentic commerce (released January 2026).

UCP provides:
- Merchant capability discovery (`/.well-known/ucp`)
- Standardized checkout sessions
- Payment handler abstraction
- Fulfillment schemas

**Relationship to Intentionality Optimization**
UCP defines *how* transactions flow. We define which products are **discoverable** in the first place.

---

## ACP — Agentic Commerce Protocol

**Definition**
OpenAI's commerce protocol (co-built with Stripe).

ACP enables:
- Cart creation/update via API
- Payment token delegation
- Merchant-of-record preservation

**Relationship to Intentionality Optimization**
Like UCP, ACP is transaction plumbing. We provide the **pre-transaction** discovery layer.

---

## Direct Offers

**Definition**
Google's paid placement system for AI Mode recommendations (announced January 2026).

Direct Offers:
- Lets retailers pay to appear in AI recommendations
- Auction-based bidding (CPA, CPC)
- Integrated with Google Shopping ecosystem

**Relationship to Intentionality Optimization**
Direct Offers = paid placement. We = organic discovery. Complementary, not competitive.

---

## Answer Independence

**Definition**
OpenAI's principle that advertising should not influence AI answers.

**How We Relate**
If ads don't influence answers, then recommendations must be based on genuine alignment. We help brands achieve that alignment.

---

## LLM Commerce Surface

**Definition**
Any interface where an LLM can recommend products.

Examples:
- Google AI Mode
- ChatGPT Shopping
- Claude with commerce tools
- Custom commerce agents

We optimize for discoverability across all surfaces.

---

## Theoretical Foundation

**Definition**
The research basis for why intentionality optimization works.

| Concept | Application |
|---------|-------------|
| Bayesian Intent Inference | User goals as latent variables inferred from signals |
| Active Inference / Free Energy | LLMs minimize predictive surprise; aligned products are "low-surprise" |
| Theory of Mind in LLMs | Models learn to predict beliefs, desires, intentions |

The theory explains *why* it works. The demo shows *that* it works.

---

## Summary Statement

> **Simulation Sandbox** lets brands test their products
> **Intent Inference** determines what users want
> **Intentionality Profiles** describe what products provide
> **Alignment Scoring** predicts what LLMs recommend
> **Gap Analysis** explains why products lose
> **Re-test Loop** verifies optimization works
> **Organic Discovery** is the outcome

**The pitch:**
> "See what the LLM sees. Fix what's broken. Test until you win."

---

*Document Version: 2026-01-22*
*Status: Active*
