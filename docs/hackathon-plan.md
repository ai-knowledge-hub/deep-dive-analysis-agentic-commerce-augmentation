# Hackathon Plan – Gemini 3 Competition

## 1. Overview

- **Goal:** Demo-ready simulation sandbox before **Feb 9, 2026**
- **Core Innovation:** A test environment for AI shopping discoverability—brands can see what LLMs see and fix what's broken
- **The Pitch:** "See what the LLM sees. Fix what's broken. Test until you win."
- **Judging Criteria:** Technical Execution (40%), Innovation (30%), Impact (20%), Presentation (10%)

## 2. The User Problem We Solve

> "I don't know what the LLM 'sees' when it decides whether to recommend my product, and I have no way to test or improve it."

Brand marketers, e-commerce leads, and agency managers have no visibility into LLM shopping recommendations. They don't know:
- Why their product isn't showing up
- What to change to get recommended
- Whether their changes actually worked

We give them a **simulation sandbox** to test, understand, and fix.

## 3. The Demo (60 Seconds)

The demo shows the complete feedback loop:

### Step 1: Set Up Scenario
```
Query: "I need a TV for my bright living room"
Brand's Product: Samsung QN90B ("65-inch 4K QLED, 3000 nits")
Competitors: LG C3 ("Bright room viewing, anti-glare"), Sony A80K
```

### Step 2: Run Simulation
System infers user intent and scores all products.

### Step 3: See Results
```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ LG C3           │ │ Samsung QN90B   │ │ Sony A80K       │
│ Score: 0.78     │ │ Score: 0.52     │ │ Score: 0.61     │
│ ✅ RECOMMENDED  │ │ ❌ NOT PICKED   │ │ ❌ NOT PICKED   │
└─────────────────┘ └─────────────────┘ └─────────────────┘

WHY YOU LOST:
• Missing: outcome framing ("Combat glare")
• Present but hidden: 3000 nits (the actual differentiator)
```

### Step 4: Optimize
```
Before: "65-inch 4K QLED, 3000 nits"
After:  "Combat glare in bright rooms. Clear picture without closing blinds."
```

### Step 5: Re-Test
```
Samsung QN90B: 0.52 → 0.85 ✅ NOW RECOMMENDED
```

### The Pitch
"See what the LLM sees. Fix what's broken. Test until you win."

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Query                               │
│              "I need a TV for my bright living room"         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              INTENT INFERENCE ENGINE                         │
│                                                              │
│   Query + Context + Memory → InferredIntent                 │
│   • primary_goal: "Enjoyable viewing despite ambient light" │
│   • underlying_needs: ["glare reduction", "brightness"]     │
│   • confidence: 0.92                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              INTENTIONALITY PROFILER                         │
│                                                              │
│   Product specs → IntentionalityProfile                     │
│   • capabilities_enabled: ["glare reduction", "brightness"] │
│   • goals_served: ["daytime viewing", "bright room use"]    │
│   • outcomes_expected: ["clear picture without blinds"]     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ALIGNMENT SCORER                                │
│                                                              │
│   Intent × Profile → AlignmentScore                         │
│   • score: 0.89                                              │
│   • matched_capabilities: ["glare reduction", "brightness"] │
│   • reasoning: "Capabilities directly address user needs"   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              RANKED RECOMMENDATIONS                          │
│                                                              │
│   Products sorted by alignment, with explanations           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 4. Current Stack → Target Stack

| Current | Target |
|---------|--------|
| Empowerment-focused modules | Intentionality optimization modules |
| Goal alignment (user protection) | Alignment scoring (brand discovery) |
| Legacy framing | Aligned vs unaligned product comparison |
| Agency metrics | Discovery metrics |
| Reflection loops | (Removed — not core to demo) |

## 5. Phase Plan

### Phase 1 — Core Modules (Week 1-2)

**Intent Inference Engine**
- `modules/intent/llm_classifier.py`: Deep goal extraction from queries
- `modules/intent/domain.py`: InferredIntent dataclass
- Gemini-powered intent inference prompts
- Embedding support for semantic matching

**Intentionality Profiler**
- `modules/intentionality/profiling.py`: Spec → capability transformation
- `modules/intentionality/domain.py`: IntentionalityProfile dataclass
- `modules/intentionality/transforms.py`: Common spec mappings
- LLM-assisted capability extraction

**Alignment Scorer**
- `modules/alignment/goal_alignment.py`: Score products against intent
- `modules/alignment/llm_reasoner.py`: Explain recommendations
- `modules/alignment/domain.py`: AlignmentScore dataclass

### Phase 2 — API & Integration (Week 2-3)

**New Endpoints**
- `POST /intent/infer`: Infer intent from query + context
- `POST /products/align`: Score products against intent
- `POST /products/profile`: Generate intentionality profile

**Module Updates**
- Simplify `modules/memory/`: Context for inference only
- Simplify `modules/conversation/`: Demo flow only
- Update `modules/commerce/`: Add intentionality to products

### Phase 3 — Demo UI (Week 3)

**New Components**
- `IntentDisplay.tsx`: Show inferred intent visually
- `ProductReasoning.tsx`: Show alignment score + explanations
- `IntentionalityProfileCard.tsx`: Show profile + discoverability delta

**Polish**
- Product cards with alignment scores
- Clean demo flow
- Loading states, animations

### Phase 4 — Demo & Submission (Week 4)

**Demo Video**
- Record 3-minute walkthrough
- Cover: intent inference → alignment → recommendation
- Clear "aha moment" with product comparison

**Submission**
- Devpost entry
- Gemini integration description
- Screenshots and demo link

## 6. Deliverables Matrix

| Component | Purpose | Priority |
|-----------|---------|----------|
| `modules/intent/llm_classifier.py` | Infer user goals | P0 |
| `modules/intentionality/profiling.py` | Transform product specs | P0 |
| `modules/alignment/goal_alignment.py` | Score alignment | P0 |
| Demo product data | Show the difference | P0 |
| API endpoints | Enable demo | P0 |
| Demo UI components | Visual impact | P0 |
| Demo video | Submission | P1 |
| Discovery metrics | Prove it works | P1 |

## 7. Demo Scenarios

### Scenario 1: TV for Bright Room
- Query: "I need a TV for my bright living room"
- Intent: Glare reduction, daytime viewing
- Show: Intent-legible product wins over spec-only

### Scenario 2: Laptop for Freelance Design
- Query: "I'm transitioning to freelance design work"
- Intent: Portable creative capability, professional credibility
- Show: Career-focused framing wins over raw specs

### Scenario 3: Chair for Back Pain
- Query: "I work from home and my back hurts"
- Intent: Pain reduction, sustained comfort, posture support
- Show: Outcome-focused product wins over feature list

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Gemini rate limits | Exponential backoff, caching, hybrid routing |
| Demo data quality | Carefully crafted product pairs |
| Alignment scoring accuracy | Test against expected LLM behavior |
| UI polish timeline | Focus on demo flow, skip non-essential features |

## 9. Success Criteria

### Technical
- [ ] Intent inference produces meaningful goals from diverse queries
- [ ] Alignment scores predict which product LLMs recommend
- [ ] API response time < 2s for full flow
- [ ] Zero crashes during demo

### Innovation
- [ ] Clear differentiation: "organic discovery" vs "paid placement"
- [ ] Novel insight: LLMs do intent inference, not keyword matching
- [ ] Practical application: help brands, not just theory

### Impact
- [ ] Solves real problem: brands want LLM discoverability
- [ ] Complementary to existing systems (Google, OpenAI)
- [ ] Clear business model potential

### Presentation
- [ ] 60-second "aha moment" demo
- [ ] Clear pitch: "SEO for reasoning agents"
- [ ] Professional UI for demo

## 10. Pitch Variations

**For Google judges**:
"Brands ask: 'Why isn't my product in AI Mode?' We give them the answer—and a way to fix it."

**For OpenAI judges**:
"Your 'answer independence' means the best product wins. We help brands test and optimize until they're the best."

**For investors**:
"The first simulation sandbox for AI shopping discoverability. Brands need visibility into LLM recommendations."

**For developers**:
"Open-source intent inference and alignment scoring for any commerce API."

**One-liner**:
"See what the LLM sees. Fix what's broken. Test until you win."

**Alternative one-liner**:
"A flight simulator for AI shopping—test your products before they go live."

---

*Document Version: 2026-01-22*
*Status: Active*
