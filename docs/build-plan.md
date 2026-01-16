# Build Plan: Completing World B

**Current Status:** ~70% complete
**Target:** Production-ready empowerment commerce engine + hackathon demo

This document maps what remains to be built, ordered by priority and dependency.

---

## Status Overview

| Module | Complete | Status | Critical Gap |
|--------|----------|--------|--------------|
| `commerce/` | 85% | Functional | No UCP adapter, no real-time inventory |
| `intent/` | 80% | Functional | Single-intent only, no semantic matching |
| `memory/` | 80% | Functional | No vector embeddings, no pruning |
| `empowerment/` | 75% | Partial | String matching, shallow alienation |
| `values/` | 80% | Functional | Keyword extraction, no validation |
| `conversation/` | 80% | Functional | Research scaffold exists; needs tool routing + citations |
| `mcp/` | 85% | Functional | `web_fetch` live; `image_analyze`/`memory_write` still stubbed |
| `attribution/` | 85% | Functional | No GA4, in-memory only |
| `evaluation/` | 60% | Partial | 1 metric, no A/B harness |
| `api/` | 85% | Functional | No streaming, no auth |
| `web/` | 75% | Functional | Basic styling, no persistence |

---

## Phase 1: Hackathon Critical Path

**Goal:** Demo-ready by Feb 9, 2026
**Focus:** Visible differentiation from World A

### 1.1 Semantic Goal-Product Alignment (P0)

**Current:** Embedding-based alignment implemented; embeddings not yet persisted
**Target:** Embeddings stored + reused (goal/product)

```
Dependency: None
Effort: 3-4 days
Impact: Core differentiator — "we understand your goals"
```

**Tasks:**
- [ ] Add embedding generation to `shared/llm/gateway.py`
- [ ] Create `shared/llm/embeddings.py` with caching
- [ ] Update `modules/empowerment/goal_alignment.py` to use cosine similarity
- [ ] Add embedding columns to SQLite schema (`goal_embedding`, `product_embedding`)
- [ ] Update `modules/memory/repositories/goals.py` to store embeddings
- [ ] Update `modules/commerce/domain.py` Product to include capability embeddings

**Files to modify:**
- `shared/llm/gateway.py`
- `shared/llm/embeddings.py` (new)
- `shared/db/schema.sql`
- `modules/empowerment/goal_alignment.py`
- `modules/memory/repositories/goals.py`
- `modules/commerce/domain.py`

---

### 1.2 Hard Constraint Enforcement (P0)

**Current:** Constraint checks now block in guard; pattern library needs expansion + UI surfacing
**Target:** Hard stops for manipulation patterns

```
Dependency: None
Effort: 2-3 days
Impact: Core differentiator — "we don't manipulate"
```

**Tasks:**
- [ ] Expand `modules/empowerment/alienation.py` with pattern library:
  - Artificial scarcity ("Only 3 left!")
  - Urgency language ("Limited time!")
  - Social pressure ("Everyone's buying this")
  - Dark patterns (hidden costs, forced upsells)
  - Cognitive overload (too many options)
- [ ] Add `ConstraintResult` dataclass with `blocked: bool`, `reason: str`
- [ ] Update `modules/conversation/guards.py` to enforce blocks
- [ ] Add constraint check before `CommerceAgent.build_plan()`
- [ ] Create `modules/empowerment/constraints.py` for constraint catalog
- [ ] Add constraint check results to API response

**Files to modify:**
- `modules/empowerment/alienation.py`
- `modules/empowerment/constraints.py` (new)
- `modules/empowerment/domain.py`
- `modules/conversation/guards.py`
- `modules/conversation/agents.py`
- `api/routes/conversation.py`

---

### 1.3 Impulse Interception (P0)

**Current:** No impulse detection
**Target:** "You've been browsing 3 minutes. This is a $2000 decision."

```
Dependency: Memory timestamps
Effort: 2 days
Impact: WOW demo moment — visible user protection
```

**Tasks:**
- [ ] Add `first_viewed_at` timestamp to session memory
- [ ] Add `decision_weight` scoring based on price/category
- [ ] Create `modules/empowerment/impulse.py`:
  - `detect_impulse(session, product)` → ImpulseCheck
  - Time thresholds by decision weight
  - Cooling-off period suggestions
- [ ] Integrate impulse check into conversation flow
- [ ] Add "Save for later" as explicit option
- [ ] Add impulse check results to empowerment extension

**Files to create/modify:**
- `modules/empowerment/impulse.py` (new)
- `modules/memory/session_manager.py`
- `modules/conversation/agents.py`
- `api/routes/conversation.py`

---

### 1.4 "No Purchase Needed" Path (P0)

**Current:** Always recommends products
**Target:** Explicit non-purchase alternatives

```
Dependency: Intent classification
Effort: 1-2 days
Impact: Core differentiator — "we're not just selling"
```

**Tasks:**
- [ ] Add `NoPurchaseOption` to recommendation responses
- [ ] Update `CommerceAgent.build_plan()` to always include non-purchase path
- [ ] Create non-purchase alternatives library:
  - "Exercise routine might help your back pain"
  - "Free resources exist for learning Python"
  - "Wait and see if you still want this tomorrow"
- [ ] Add non-purchase tracking to attribution
- [ ] Display non-purchase option prominently in UI

**Files to modify:**
- `modules/conversation/agents.py`
- `modules/commerce/plan_builder.py`
- `modules/attribution/events.py`
- `web/components/products/ProductReasoning.tsx`

---

### 1.5 Reflection Loop Closure (P0)

**Current:** Reflection generated but not scheduled
**Target:** "14 days later: Did this help?"

```
Dependency: Memory persistence
Effort: 2 days
Impact: Unique feature — learning from outcomes
```

**Tasks:**
- [ ] Add `reflection_scheduled_at` to recommendations table
- [ ] Create `modules/empowerment/reflection_scheduler.py`:
  - Schedule reflection prompts
  - Calculate optimal timing by category
- [ ] Add reflection endpoint: `POST /conversation/reflect`
- [ ] Store reflection outcomes in episodic memory
- [ ] Update goal alignment based on reflections
- [ ] Add reflection UI component

**Files to create/modify:**
- `modules/empowerment/reflection_scheduler.py` (new)
- `shared/db/schema.sql`
- `modules/memory/repositories/recommendations.py`
- `api/routes/conversation.py`
- `web/components/empowerment/ReflectionPrompt.tsx` (new)

---

### 1.6 World A vs World B Demo View (P1)

**Current:** Basic comparison component exists
**Target:** Side-by-side visual comparison for demo

```
Dependency: 1.2 constraints, 1.3 impulse
Effort: 2 days
Impact: Visual demo impact
```

**Tasks:**
- [ ] Create `WorldASimulator` that generates manipulative version
- [ ] Add urgency signals, social proof, hidden costs to World A
- [ ] Show constraint violations that World B blocked
- [ ] Add empowerment score comparison gauge
- [ ] Polish WorldAvsB component styling
- [ ] Add toggle for live switching

**Files to modify:**
- `modules/conversation/simulators/world_a.py` (new)
- `web/components/empowerment/WorldAvsB.tsx`
- `web/components/empowerment/EmpowermentGauge.tsx` (new)

---

## Phase 2: Protocol Integration

**Goal:** UCP/ACP compatibility for strategic positioning
**Focus:** Demonstrate protocol-agnostic architecture

### 2.1 UCP Adapter (P1)

**Current:** Designed in strategic-positioning.md, not implemented
**Target:** Working UCP merchant discovery and checkout

```
Dependency: None
Effort: 3-4 days
Impact: Strategic — "we integrate with Google's standard"
```

**Tasks:**
- [ ] Create `modules/commerce/adapters/ucp/` directory
- [ ] Implement `client.py`:
  - `discover_merchant(url)` → UCPDiscoveryProfile
  - `create_checkout(items, buyer)` → CheckoutSession
  - `apply_discount(checkout_id, code)` → CheckoutSession
- [ ] Implement `mapper.py`:
  - UCP Item → RawOffer transformation
  - Preserve confidence metadata
- [ ] Add empowerment extension injection
- [ ] Add UCP adapter to loader registry
- [ ] Write integration tests with mock UCP server

**Files to create:**
- `modules/commerce/adapters/ucp/__init__.py`
- `modules/commerce/adapters/ucp/client.py`
- `modules/commerce/adapters/ucp/mapper.py`
- `modules/commerce/adapters/ucp/schemas.py`
- `tests/modules/commerce/test_ucp_adapter.py`

---

### 2.2 Empowerment Extension Schema (P1)

**Current:** Designed in strategic-positioning.md
**Target:** Publishable JSON Schema for UCP extension

```
Dependency: 2.1 UCP Adapter
Effort: 1 day
Impact: Strategic — open standard contribution
```

**Tasks:**
- [ ] Create `schemas/ucp/empowerment-extension.json`
- [ ] Validate schema with JSON Schema validator
- [ ] Document extension in `docs/ucp-extension.md`
- [ ] Add extension injection to UCP checkout flow
- [ ] Create sample extension payloads

**Files to create:**
- `schemas/ucp/empowerment-extension.json`
- `docs/ucp-extension.md`

---

### 2.3 OpenAI ACP Adapter (P2)

**Current:** Not started
**Target:** Basic ACP compatibility

```
Dependency: 2.1 UCP Adapter (similar pattern)
Effort: 2-3 days
Impact: Strategic — dual-protocol support
```

**Tasks:**
- [ ] Research ACP specification (Stripe integration)
- [ ] Create `modules/commerce/adapters/acp/` directory
- [ ] Implement cart creation/update
- [ ] Implement payment token delegation
- [ ] Add empowerment metadata passthrough

---

## Phase 3: MCP Tools Completion

**Goal:** Full tool suite for agent capabilities
**Focus:** Enable advanced agent workflows

### 3.1 web_fetch Tool (P1)

**Current:** Stub in `modules/mcp/tools/web_fetch.py`
**Target:** Fetch and parse web content with allowlist

```
Dependency: None
Effort: 1-2 days
Impact: Enables research agent
```

**Tasks:**
- [ ] Implement URL fetching with httpx
- [ ] Add domain allowlist from `WEB_FETCH_ALLOWLIST` env
- [ ] Parse HTML to markdown/text
- [ ] Add content summarization via LLM
- [ ] Respect robots.txt
- [ ] Add rate limiting

**Files to modify:**
- `modules/mcp/tools/web_fetch.py`
- `shared/config/env.py`

---

### 3.2 image_analyze Tool (P2)

**Current:** Stub in `modules/mcp/tools/image_analyze.py`
**Target:** Analyze product images for empowerment signals

```
Dependency: Gemini Vision API
Effort: 2 days
Impact: Multimodal empowerment (ergonomics, quality signals)
```

**Tasks:**
- [ ] Implement image URL fetching
- [ ] Add Gemini Vision integration to gateway
- [ ] Create empowerment-focused image prompts:
  - Ergonomic assessment
  - Quality indicators
  - Misleading imagery detection
- [ ] Return structured analysis

**Files to modify:**
- `modules/mcp/tools/image_analyze.py`
- `shared/llm/gateway.py`
- `shared/llm/prompts.py`

---

### 3.3 memory_write Tool (P2)

**Current:** Stub in `modules/mcp/tools/memory_write.py`
**Target:** Persist goals/preferences from conversation

```
Dependency: Memory module
Effort: 1 day
Impact: Enables agent-driven memory updates
```

**Tasks:**
- [ ] Implement goal persistence
- [ ] Implement preference persistence
- [ ] Add consent check before write
- [ ] Add write confirmation response

**Files to modify:**
- `modules/mcp/tools/memory_write.py`
- `modules/memory/session_manager.py`

---

### 3.4 Research Agent (P2)

**Current:** Stub in `modules/conversation/research.py`
**Target:** Web-based information gathering for better recommendations

```
Dependency: 3.1 web_fetch
Effort: 2-3 days
Impact: Deeper research capabilities
```

**Tasks:**
- [ ] Implement research query planning
- [ ] Multi-source information gathering
- [ ] Source quality assessment
- [ ] Summary generation
- [ ] Integration with commerce flow

**Files to modify:**
- `modules/conversation/research.py`
- `modules/conversation/agents.py`

---

## Phase 4: Evaluation & Metrics

**Goal:** Measure empowerment impact
**Focus:** Prove World B works

### 4.1 Dual Dashboard Metrics (P1)

**Current:** Metrics defined in docs, not implemented
**Target:** Real-time empowerment metrics

```
Dependency: Attribution events
Effort: 2-3 days
Impact: Provable differentiation
```

**Tasks:**
- [ ] Create `modules/evaluation/metrics/` directory:
  - `goal_consistency.py` — alignment scores over time
  - `exploration_diversity.py` — Shannon entropy of recommendations
  - `regret_proxy.py` — returns, negative feedback
  - `trust_proxy.py` — repeat usage, referrals
- [ ] Create metrics aggregation service
- [ ] Add metrics endpoint: `GET /metrics/dashboard`
- [ ] Create dashboard UI component

**Files to create:**
- `modules/evaluation/metrics/goal_consistency.py`
- `modules/evaluation/metrics/exploration_diversity.py`
- `modules/evaluation/metrics/regret_proxy.py`
- `modules/evaluation/metrics/trust_proxy.py`
- `modules/evaluation/dashboard.py`
- `api/routes/metrics.py`
- `web/components/empowerment/Dashboard.tsx`

---

### 4.2 A/B Testing Harness (P2)

**Current:** Simulation framework started
**Target:** Compare World A vs World B outcomes

```
Dependency: 4.1 Metrics
Effort: 3-4 days
Impact: Statistical proof of value
```

**Tasks:**
- [ ] Create experiment configuration schema
- [ ] Implement user cohort assignment
- [ ] Add treatment/control logic
- [ ] Implement statistical significance testing
- [ ] Create experiment results dashboard

---

## Phase 5: Production Readiness

**Goal:** Deployable, scalable, secure
**Focus:** Beyond hackathon

### 5.1 API Streaming (P2)

**Current:** Request/response only
**Target:** SSE streaming for chat

```
Dependency: None
Effort: 2 days
```

**Tasks:**
- [ ] Add SSE endpoint for conversation
- [ ] Stream LLM responses
- [ ] Stream plan building progress
- [ ] Update web client for streaming

---

### 5.2 Authentication (P2)

**Current:** No auth
**Target:** User authentication for persistence

```
Dependency: None
Effort: 2-3 days
```

**Tasks:**
- [ ] Add JWT authentication
- [ ] User registration/login endpoints
- [ ] Session binding to authenticated users
- [ ] Privacy controls for memory

---

### 5.3 Production Adapters (P2)

**Current:** Shopify/Google Shopping partially implemented
**Target:** Production-ready integrations

```
Dependency: Credentials
Effort: 3-4 days
```

**Tasks:**
- [ ] Complete Shopify adapter with real credentials
- [ ] Add Google Shopping Content API integration
- [ ] Implement real-time inventory sync
- [ ] Add variant-level product handling
- [ ] Add rate limiting and error handling

---

### 5.4 Frontend Polish (P2)

**Current:** Functional but basic
**Target:** Demo-quality UI

```
Dependency: None
Effort: 3-4 days
```

**Tasks:**
- [ ] Add persistent session storage
- [ ] Improve mobile responsiveness
- [ ] Add loading states and animations
- [ ] Add accessibility (aria labels, keyboard nav)
- [ ] Dark mode support
- [ ] Product image gallery

---

### 5.5 Observability (P3)

**Current:** No monitoring
**Target:** Production observability

```
Dependency: None
Effort: 2-3 days
```

**Tasks:**
- [ ] Add structured logging
- [ ] Add request tracing
- [ ] Add LLM call metrics
- [ ] Add error alerting
- [ ] Add performance dashboards

---

## Phase 6: Documentation & Demo

**Goal:** Hackathon submission ready
**Focus:** Clear story, polished demo

### 6.1 Demo Video Script (P1)

```
Dependency: Phases 1.1-1.6
Effort: 1 day
```

**Tasks:**
- [ ] Script 3-minute walkthrough
- [ ] Prepare demo scenarios
- [ ] Record and edit video
- [ ] Add captions/annotations

---

### 6.2 Devpost Submission (P1)

```
Dependency: Demo video
Effort: 1 day
```

**Tasks:**
- [ ] Write project description
- [ ] Document Gemini integration
- [ ] Add screenshots/GIFs
- [ ] Submit before deadline

---

## Priority Matrix

### P0 — Hackathon Critical (Must Have)

| Item | Effort | Dependency | Impact |
|------|--------|------------|--------|
| 1.1 Semantic Goal Alignment | 3-4 days | None | Core differentiator |
| 1.2 Hard Constraints | 2-3 days | None | Core differentiator |
| 1.3 Impulse Interception | 2 days | Memory | WOW moment |
| 1.4 No Purchase Path | 1-2 days | None | Core differentiator |
| 1.5 Reflection Loop | 2 days | Memory | Unique feature |
| 1.6 World A vs B Demo | 2 days | 1.2, 1.3 | Visual impact |

**Total P0:** ~12-15 days

### P1 — Strategic Value (Should Have)

| Item | Effort | Dependency | Impact |
|------|--------|------------|--------|
| 2.1 UCP Adapter | 3-4 days | None | Protocol positioning |
| 2.2 Empowerment Schema | 1 day | 2.1 | Open standard |
| 3.1 web_fetch Tool | 1-2 days | None | Research capability |
| 4.1 Dual Dashboard | 2-3 days | Attribution | Proof of value |
| 6.1 Demo Video | 1 day | P0 complete | Submission |
| 6.2 Devpost | 1 day | 6.1 | Submission |

**Total P1:** ~10-12 days

### P2 — Completeness (Nice to Have)

| Item | Effort | Dependency | Impact |
|------|--------|------------|--------|
| 2.3 ACP Adapter | 2-3 days | 2.1 | Dual protocol |
| 3.2 image_analyze | 2 days | None | Multimodal |
| 3.3 memory_write | 1 day | None | Agent memory |
| 3.4 Research Agent | 2-3 days | 3.1 | Deep research |
| 4.2 A/B Harness | 3-4 days | 4.1 | Statistical proof |
| 5.1 API Streaming | 2 days | None | UX improvement |
| 5.2 Authentication | 2-3 days | None | Persistence |
| 5.3 Production Adapters | 3-4 days | None | Real data |
| 5.4 Frontend Polish | 3-4 days | None | Demo quality |

**Total P2:** ~20-25 days

### P3 — Future (Post-Hackathon)

- 5.5 Observability
- Multi-intent detection
- Semantic memory with vector search
- Real-time inventory sync
- Mobile app

---

## Recommended Build Order

### Week 1: Core Empowerment
1. **1.1 Semantic Goal Alignment** (foundation for everything)
2. **1.2 Hard Constraints** (parallel with 1.1)
3. **1.4 No Purchase Path** (quick win)

### Week 2: User Protection + Demo
4. **1.3 Impulse Interception** (after memory updates from 1.1)
5. **1.5 Reflection Loop** (parallel with 1.3)
6. **1.6 World A vs B Demo** (after 1.2, 1.3)

### Week 3: Protocol + Metrics
7. **2.1 UCP Adapter** (strategic value)
8. **3.1 web_fetch Tool** (enables research)
9. **4.1 Dual Dashboard** (proof of value)

### Week 4: Polish + Submit
10. **Frontend improvements** (as needed)
11. **6.1 Demo Video**
12. **6.2 Devpost Submission**

---

## Definition of Done

Each feature is complete when:

1. **Code complete** — Implementation matches spec
2. **Tests pass** — Unit + integration tests written and passing
3. **Docs updated** — README/docs reflect new capability
4. **Demo ready** — Can be shown in 30-second demo
5. **API documented** — Endpoints documented if applicable

---

## Success Metrics

### Hackathon Success
- [ ] 3-minute demo video completed
- [ ] All P0 features working
- [ ] World A vs B comparison visible
- [ ] "No purchase needed" scenario demonstrated
- [ ] Reflection loop shown

### Technical Success
- [ ] Semantic goal alignment accuracy > 80%
- [ ] Constraint detection covers top 10 manipulation patterns
- [ ] API response time < 2s for recommendations
- [ ] Zero crashes during demo

### Strategic Success
- [ ] UCP adapter functional
- [ ] Empowerment extension documented
- [ ] Clear positioning vs Google/OpenAI

---

**Document Version:** 2026-01-14
**Next Review:** After Phase 1 completion
