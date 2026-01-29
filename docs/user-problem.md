# User Problem: AI Discoverability Gap

## The Core Problem

> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

Brand marketing managers, e-commerce growth leads, and agency account managers are suddenly responsible for a new channel they don't understand: **AI shopping recommendations**.

Unlike traditional SEO (where tools show you rankings, keywords, and competitors), there's no visibility into why an LLM recommends one product over another.

---

## Who We Serve

| Role | Context | Their Question |
|------|---------|----------------|
| **Brand Marketing Manager** | Owns product visibility across channels | "Why aren't my products showing up in ChatGPT or Google AI Mode?" |
| **E-commerce Growth Lead** | Owns conversion and discovery metrics | "I know how to optimize for Google Search, but AI works differently—what are the rules?" |
| **Agency Account Manager** | Managing multiple brand accounts | "Client asks why their product isn't in AI results. I have no tools to investigate or fix it." |
| **Product Feed Manager** | Maintains Merchant Center / Shopify feeds | "I write descriptions for keyword search. What should I change for LLM reasoning?" |

---

## Why This Problem Exists Now

### The Shift: Keyword Matching → Intent Inference

Traditional search matches keywords. LLMs do something different: they **infer user intent** and select products that serve that intent.

```
Traditional Search:
  User types: "65-inch TV bright room"
  Search matches: products containing those keywords

LLM Shopping:
  User says: "I need a TV for my bright living room"
  LLM infers: User wants enjoyable viewing despite ambient light
  LLM selects: Products that ADDRESS that need (not just mention those words)
```

The problem: **most product data is optimized for keyword matching, not intent alignment**.

### Two Ecosystems, Same Challenge

| Platform | How It Works | Implication |
|----------|--------------|-------------|
| **OpenAI Shopping** | Pure organic selection—model picks products based on relevance, no paid boost | If your product isn't legible to intent reasoning, you're invisible |
| **Google AI Mode + UCP** | Organic + ads entangled—paid gets you in candidate pool, but LLM still picks winners | Even with ads, the LLM chooses based on alignment with user intent |

**Key insight**: In both ecosystems, organic discoverability matters. The LLM is the gatekeeper.

---

## The Missing Feedback Loop

### What Users Have Today

```
Product Data → ??? → LLM Recommendation (or not)

No visibility into:
- What the LLM "sees" in your product
- Why it chose a competitor instead
- What to change to win next time
```

### What Users Need

```
Product Data → Analyze → Score → Simulate → See Result
     ↑                                           │
     └────── Optimize ← Understand Gap ←─────────┘
```

A **closed-loop simulation sandbox** where users can:
1. Test their product against a user query
2. See who wins (their product vs competitors)
3. Understand WHY they lost
4. Confirm brand tone (accept or edit the suggested voice)
5. Optimize and re-test until they win

---

## User Stories

### Story 1: "Why did I lose?"

> *Sarah is a marketing manager at a TV brand. A customer mentions they asked ChatGPT for a TV recommendation and got a competitor. Sarah has no idea why.*

**What Sarah needs:**
- Simulate the same query in our app
- See her product scored against competitors
- Get an explanation: "Your product scored 0.52 because it focuses on specs. The competitor scored 0.78 because it explicitly mentions 'bright room viewing.'"
- Get a suggestion: "Add outcome framing like 'Combat glare in bright rooms'"

### Story 2: "What should I change?"

> *Marcus manages product feeds for 500 SKUs. He knows AI shopping is growing but doesn't know which products need work or what "work" means.*

**What Marcus needs:**
- Provide product data or protocol profiles for readiness and simulation
- Get a legibility report: "340 products score below 0.5. Common issue: specs-only descriptions."
- Prioritized list: "Fix these 20 high-margin products first"
- Before/after suggestions for each

### Story 3: "Did my changes work?"

> *Agency account manager Priya optimized a client's product descriptions last month. The client asks: "Are we showing up in AI results now?"*

**What Priya needs:**
- Run verification queries: "TV for bright room", "best OLED for gaming", etc.
- See if client products now appear in simulated LLM responses
- Show client: "Before optimization: 0 mentions. After: 3 out of 5 queries."

---

## The Solution: Simulation Sandbox

Our app is a **test environment for LLM discoverability**—like a flight simulator for AI shopping.

### Core Loop

```
┌─────────────────────────────────────────────────────────────┐
│  1. SET UP SCENARIO                                          │
│                                                              │
│  User defines:                                               │
│  • Query: "I need a TV for my bright living room"           │
│  • Their product: Samsung QN90B                              │
│  • Competitors: LG C3, Sony A80K (optional)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. SIMULATE                                                 │
│                                                              │
│  App simulates LLM shopping behavior:                        │
│  • Infer user intent from query                              │
│  • Score all products against that intent                    │
│  • Predict which product LLM would recommend                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. SEE RESULTS                                              │
│                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ LG C3       │ │ Samsung     │ │ Sony A80K   │            │
│  │ Score: 0.78 │ │ Score: 0.52 │ │ Score: 0.61 │            │
│  │ ✅ WINNER   │ │ ❌ LOST     │ │ ❌ LOST     │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│                                                              │
│  WHY YOU LOST:                                               │
│  • Missing: outcome framing for "bright room viewing"        │
│  • Missing: context fit signal                               │
│  • Present but hidden: 3000 nits (the actual differentiator) │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. CONFIRM TONE                                             │
│                                                              │
│  Suggested tone: "confident, concise, technical"             │
│  [Use suggestion]  [Edit]  [Clear]                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. OPTIMIZE                                                 │
│                                                              │
│  Suggested change:                                           │
│  Before: "65-inch 4K QLED, 3000 nits brightness"            │
│  After:  "Combat glare in bright rooms. Clear picture       │
│           without closing blinds. 65-inch 4K, 3000 nits."   │
│                                                              │
│  [Apply Suggestion]  [Edit]  [Re-Test]                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. RE-TEST                                                  │
│                                                              │
│  Samsung QN90B: 0.52 → 0.85                                  │
│  ✅ NOW RECOMMENDED                                          │
│                                                              │
│  [Save Changes]  [Export Optimized Description]              │
└─────────────────────────────────────────────────────────────┘
```

---

## Value Proposition

| For | Value |
|-----|-------|
| **Brand marketers** | "Finally see what the AI sees. Stop guessing." |
| **Feed managers** | "Know exactly which products need work and what to change." |
| **Agencies** | "Show clients measurable improvement in AI discoverability." |

### One-Liner

> **"See what the LLM sees. Fix what's broken. Test until you win."**

---

## How This Maps to OpenAI vs Google

### OpenAI Shopping (Pure Organic)

- No paid placement—model picks winners purely on merit
- Our simulation helps brands win the organic game
- Verification shows: "Would ChatGPT recommend you?"

### Google AI Mode (Organic + Ads)

- Paid placement gets you in the candidate pool
- But LLM still selects which candidates to highlight
- Our simulation helps brands win *after* they're in the pool
- Complementary to Direct Offers, not competitive

### Both Ecosystems

The LLM is the gatekeeper. Whether you pay for placement or not, **the model decides who gets recommended**. We help brands understand and optimize for that decision.

---

## What We're NOT

| Not This | Why Not |
|----------|---------|
| **Middleware between brands and LLMs** | We don't sit in the runtime path |
| **Paid placement platform** | We optimize organic discovery, not ads |
| **Generic SEO tool** | We focus specifically on LLM reasoning, not keyword ranking |
| **LLM provider** | We help brands be discovered by *any* LLM |

---

## Summary

| Question | Answer |
|----------|--------|
| **Who is the user?** | Brand/agency people responsible for product visibility in AI shopping |
| **What's their pain?** | "I don't know why my product isn't showing up in AI results" |
| **Why now?** | LLMs do intent inference, not keyword matching—existing tools don't help |
| **What's the solution?** | Simulation sandbox: test → see who wins → understand why → optimize → re-test |
| **What's the value?** | "See what the LLM sees. Fix what's broken. Test until you win." |

---

*Document Version: 2026-01-22*
*Status: Active*
