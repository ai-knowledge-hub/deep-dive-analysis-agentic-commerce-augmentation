# Hackathon Plan – Gemini 3 Competition

## 1. Overview

- **Goal:** Demo-ready intentionality optimization system before **Feb 9, 2026**
- **Core Innovation:** "SEO for reasoning agents" — help brands become discoverable by LLMs through intent alignment
- **Judging Criteria:** Technical Execution (40%), Innovation (30%), Impact (20%), Presentation (10%)

## 2. The Demo (60 Seconds)

The demo must show the core insight in under a minute:

1. **User Query**: "I need a TV for my bright living room"

2. **Intent Inference**:
   - Primary goal: "Enjoyable viewing despite ambient light"
   - Underlying needs: ["glare reduction", "brightness", "daytime usability"]
   - Show this visually

3. **Two Products** (same underlying specs):
   - Product A: Intent-legible ("Combat glare in bright rooms, clear picture without closing blinds")
   - Product B: Spec-only ("65-inch 4K QLED, 3000 nits, anti-reflective coating")

4. **Alignment Scores**:
   - Product A: 0.89 (capabilities match inferred intent)
   - Product B: 0.52 (specs present, not intent-legible)

5. **The Result**: "Product A gets recommended. Product B doesn't. Same product, different framing."

6. **The Pitch**: "We help brands structure their products to be legible to intent inference. That's organic discovery for AI commerce."

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
- `modules/intent/inference.py`: Deep goal extraction from queries
- `modules/intent/domain.py`: InferredIntent dataclass
- Gemini-powered intent inference prompts
- Embedding support for semantic matching

**Intentionality Profiler**
- `modules/intentionality/profiler.py`: Spec → capability transformation
- `modules/intentionality/domain.py`: IntentionalityProfile dataclass
- `modules/intentionality/transforms.py`: Common spec mappings
- LLM-assisted capability extraction

**Alignment Scorer**
- `modules/alignment/scoring.py`: Score products against intent
- `modules/alignment/ranker.py`: Rank and explain recommendations
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
- `AlignmentScore.tsx`: Show score with explanation
- `DiscoveryDemo.tsx`: Side-by-side product comparison

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
| `modules/intent/inference.py` | Infer user goals | P0 |
| `modules/intentionality/profiler.py` | Transform product specs | P0 |
| `modules/alignment/scoring.py` | Score alignment | P0 |
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
"Direct Offers handles paid placement. We handle organic discovery. Brands need both."

**For OpenAI judges**:
"Your 'answer independence' means the best product wins. We help brands become the best product for the user's intent."

**For investors**:
"The intentionality layer — protocol-agnostic, LLM-native, inevitable."

**For developers**:
"Open-source intent inference for any commerce API."

**One-liner**:
"SEO for reasoning agents — help brands become discoverable by AI."

---

*Document Version: 2026-01-17*
*Status: Active*
