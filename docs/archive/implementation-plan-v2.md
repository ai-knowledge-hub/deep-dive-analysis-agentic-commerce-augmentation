# Implementation Plan: Architecture v2

## Objective

Transform the codebase from "empowerment-first commerce" to "intentionality optimization for LLM discovery."

This plan maps every file that needs to change, be removed, or be created.

---

## Phase 1: Module Restructuring

### 1.1 Rename `modules/empowerment/` → `modules/alignment/`

**Rationale**: "Empowerment" is user-protection framing. "Alignment" describes the function: scoring products against inferred intent.

| Old File | Action | New File |
|----------|--------|----------|
| `empowerment/__init__.py` | Rename | `alignment/__init__.py` |
| `empowerment/domain.py` | Rewrite | `alignment/domain.py` |
| `empowerment/goal_alignment.py` | Rewrite | `alignment/scoring.py` |
| `empowerment/optimizer.py` | Simplify | `alignment/ranker.py` |
| `empowerment/llm_reasoner.py` | Keep, adapt | `alignment/llm_reasoner.py` |
| `empowerment/schemas.py` | Merge into domain | (removed) |
| `empowerment/alienation.py` | **Delete** | — |
| `empowerment/reflection.py` | **Delete** | — |

**New domain model** (`alignment/domain.py`):

```python
@dataclass
class AlignmentScore:
    product_id: str
    score: float                      # 0.0-1.0
    matched_capabilities: List[str]
    alignment_reasoning: str
    confidence: float

@dataclass
class IntentionalityProfile:
    product_id: str
    capabilities_enabled: List[str]
    goals_served: List[str]
    prerequisites: List[str]
    outcomes_expected: List[str]
    context_fit: Dict[str, float]
```

---

### 1.2 Create `modules/intentionality/`

**Purpose**: Transform raw product data into intent-legible profiles.

| File | Purpose |
|------|---------|
| `intentionality/__init__.py` | Module exports |
| `intentionality/profiler.py` | Generate IntentionalityProfile from product |
| `intentionality/enricher.py` | LLM-assisted capability extraction |
| `intentionality/transforms.py` | Spec → capability mappings |

**Key function**:

```python
async def generate_intentionality_profile(
    product: Product,
    llm_gateway: LLMGateway
) -> IntentionalityProfile:
    """Transform raw product into intent-legible profile."""
    ...
```

---

### 1.3 Simplify `modules/intent/`

**Current state**: Has intent taxonomy, classifier, LLM classifier
**New state**: Focused on inferring user intent from query + context

| Old File | Action | New File |
|----------|--------|----------|
| `intent/__init__.py` | Keep | `intent/__init__.py` |
| `intent/domain.py` | Rewrite | `intent/domain.py` |
| `intent/classifier.py` | Simplify | `intent/inference.py` |
| `intent/llm_classifier.py` | Merge | `intent/inference.py` |
| `intent/taxonomy.py` | Keep, simplify | `intent/taxonomy.py` |

**New domain model** (`intent/domain.py`):

```python
@dataclass
class InferredIntent:
    primary_goal: str
    underlying_needs: List[str]
    context_signals: List[str]
    confidence: float

@dataclass
class IntentContext:
    query: str
    session_history: List[str]
    user_goals: List[str]  # From memory
    user_preferences: Dict[str, Any]
```

---

### 1.4 Simplify `modules/memory/`

**Current state**: Working, episodic, semantic memory with reflection support
**New state**: Context memory for intent inference

| Old File | Action | Notes |
|----------|--------|-------|
| `memory/__init__.py` | Keep | |
| `memory/working.py` | Keep | Session context |
| `memory/semantic.py` | Simplify | Goals and preferences only |
| `memory/episodic.py` | **Simplify heavily** | Remove reflection, keep purchase history |
| `memory/session_manager.py` | Keep | |
| `memory/repositories/*.py` | Simplify | Remove reflection tables |

**Remove from schema**:
- Reflection scheduling
- Reflection outcomes
- Agency metrics

**Keep in schema**:
- User goals
- User preferences
- Session context
- Purchase history (for inference)

---

### 1.5 Simplify `modules/commerce/`

**Current state**: Products as "capability-enabling tools" with empowerment metadata
**New state**: Products with intentionality profiles

| Old File | Action | Notes |
|----------|--------|-------|
| `commerce/__init__.py` | Keep | |
| `commerce/domain.py` | Rewrite | Remove empowerment fields, add intentionality |
| `commerce/service.py` | Simplify | |
| `commerce/plan_builder.py` | **Delete** | Orchestration, not core |
| `commerce/adapters/*.py` | Keep | |

**Updated Product model**:

```python
@dataclass
class Product:
    id: str
    title: str
    description: str
    price: float
    # ... standard fields

    # Intentionality fields (new)
    intentionality: Optional[IntentionalityProfile] = None

    # Removed
    # capabilities_enabled: List[str]  — moved to IntentionalityProfile
    # prerequisites: List[str]         — moved to IntentionalityProfile
    # effort_required: str             — removed (empowerment framing)
```

---

### 1.6 Simplify `modules/conversation/`

**Current state**: Full orchestration with guards, agents, context management
**New state**: Thin demo layer

| Old File | Action | Notes |
|----------|--------|-------|
| `conversation/__init__.py` | Keep | |
| `conversation/agents.py` | Simplify | Demo flow only |
| `conversation/context.py` | Keep | |
| `conversation/guards.py` | **Delete** | User-protection framing |
| `conversation/research.py` | **Delete** | Not core |
| `conversation/simulators/` | **Delete** | World A simulation not needed |

---

### 1.7 Simplify `modules/values/`

**Current state**: Values clarification dialogue
**New state**: Goal elicitation (simpler)

| Old File | Action | Notes |
|----------|--------|-------|
| `values/__init__.py` | Keep | |
| `values/agent.py` | Rename/simplify | → `values/goal_elicitation.py` |
| `values/domain.py` | Simplify | |

Goal elicitation serves intent inference. "Values clarification" is empowerment framing.

---

### 1.8 Remove/Archive `modules/attribution/` and `modules/evaluation/`

**Rationale**: These measure user outcomes (agency). We need to measure brand discoverability instead.

| Module | Action |
|--------|--------|
| `attribution/` | Archive (may reuse for discoverability tracking) |
| `evaluation/` | Archive |

**Future**: Create `modules/discovery/` for tracking brand visibility across LLM surfaces.

---

## Phase 2: Documentation Rewrite

### 2.1 Core Docs — Rewrite

| Document | Action | New Focus |
|----------|--------|-----------|
| `docs/architecture.md` | Replace with v2 | Intentionality optimization |
| `docs/manifesto.md` | **Delete or archive** | Empowerment framing |
| `docs/strategic-positioning.md` | Rewrite | Brand discovery positioning |
| `docs/build-plan.md` | Replace | New implementation priorities |
| `docs/hackathon-plan.md` | Rewrite | New demo flow |

### 2.2 Technical Docs — Simplify

| Document | Action | Notes |
|----------|--------|-------|
| `docs/agency-layer.md` | **Delete** | User-protection framing |
| `docs/empowerment_metrics.md` | **Delete** | Replaced by discovery metrics |
| `docs/adapters.md` | Keep, minor updates | |
| `docs/feed_schema.md` | Keep | |
| `docs/sequence-diagram.md` | Rewrite | New flow |
| `docs/terminology.md` | Rewrite | New vocabulary |
| `docs/attribution.md` | Archive | |
| `docs/deployment.md` | Keep | |

### 2.3 New Docs — Create

| Document | Purpose |
|----------|---------|
| `docs/architecture-v2.md` | Final architecture (from draft) |
| `docs/intent-inference.md` | How we infer user intent |
| `docs/intentionality-profiles.md` | How we profile products |
| `docs/alignment-scoring.md` | How we score alignment |
| `docs/discovery-metrics.md` | How we measure brand discoverability |
| `docs/theoretical-foundation.md` | Bayesian/Friston grounding (light) |

---

## Phase 3: API Simplification

### 3.1 Core Endpoints

| Endpoint | Action | Notes |
|----------|--------|-------|
| `POST /conversation/start` | Keep | |
| `POST /conversation/message` | Simplify | Remove guard checks |
| `POST /conversation/goals` | Keep | For goal elicitation |
| `POST /conversation/recommend` | Rewrite | Return alignment scores |
| `POST /conversation/reflect` | **Delete** | Reflection not core |

### 3.2 New Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /intent/infer` | Infer intent from query + context |
| `POST /products/align` | Score products against intent |
| `POST /products/profile` | Get/generate intentionality profile |
| `POST /catalog/enrich` | Batch enrich catalog with intentionality |

---

## Phase 4: Frontend Simplification

### 4.1 Components to Remove

| Component | Reason |
|-----------|--------|
| `WorldAvsB.tsx` | Ethical comparison framing |
| `ReflectionPrompt.tsx` | User follow-up not core |
| Impulse interception UI | User protection framing |
| Agency metrics display | Wrong metrics |
| Consent gates UI | GDPR framing not core |

### 4.2 Components to Keep/Adapt

| Component | Action |
|-----------|--------|
| Chat interface | Keep |
| Product cards | Adapt (show alignment scores) |
| Goal summary | Keep |
| Recommendation display | Adapt |

### 4.3 New Components

| Component | Purpose |
|-----------|---------|
| `AlignmentScore.tsx` | Display alignment score with explanation |
| `IntentDisplay.tsx` | Show inferred intent |
| `DiscoveryDemo.tsx` | Side-by-side: aligned vs unaligned product |

---

## Phase 5: Database Schema Updates

### 5.1 Tables to Simplify

```sql
-- Remove from goals table
ALTER TABLE goals DROP COLUMN agency_score;
ALTER TABLE goals DROP COLUMN reflection_scheduled;

-- Remove reflections table entirely
DROP TABLE IF EXISTS reflections;

-- Remove from recommendations table
ALTER TABLE recommendations DROP COLUMN impulse_check_passed;
ALTER TABLE recommendations DROP COLUMN cooling_off_offered;
ALTER TABLE recommendations DROP COLUMN reflection_scheduled_at;

-- Add intentionality fields
ALTER TABLE products ADD COLUMN intentionality_profile JSON;
ALTER TABLE products ADD COLUMN alignment_cache JSON;
```

### 5.2 New Tables

```sql
-- Intent inference cache
CREATE TABLE inferred_intents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    query TEXT NOT NULL,
    inferred_intent JSON NOT NULL,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product intentionality profiles
CREATE TABLE intentionality_profiles (
    product_id TEXT PRIMARY KEY,
    capabilities_enabled JSON,
    goals_served JSON,
    prerequisites JSON,
    outcomes_expected JSON,
    context_fit JSON,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Phase 6: Prompts Rewrite

### 6.1 Prompts to Remove

| Prompt | File | Reason |
|--------|------|--------|
| Impulse guardian | `shared/llm/prompts.py` | User protection |
| Reflection generator | `shared/llm/prompts.py` | Not core |
| Alienation detector | `shared/llm/prompts.py` | User protection |

### 6.2 Prompts to Rewrite

| Prompt | Old Purpose | New Purpose |
|--------|-------------|-------------|
| Values clarification | Understand user values | Elicit goals for inference |
| Product reasoning | Explain empowerment | Explain alignment |
| Intent classifier | Route to categories | Infer underlying goals |

### 6.3 New Prompts

| Prompt | Purpose |
|--------|---------|
| Intent inference | Deep inference of user goals from query + context |
| Intentionality extraction | Extract capabilities/outcomes from product data |
| Alignment explanation | Explain why product matches intent |

---

## Implementation Order

### Week 1: Core Modules

1. Create `modules/intentionality/` (new)
2. Rename + rewrite `modules/empowerment/` → `modules/alignment/`
3. Simplify `modules/intent/`
4. Update `modules/commerce/domain.py`

### Week 2: Integration + API

5. Simplify `modules/memory/`
6. Simplify `modules/conversation/`
7. Update API routes
8. Update database schema

### Week 3: Frontend + Demo

9. Simplify frontend components
10. Build demo flow
11. Create 3-5 compelling product examples

### Week 4: Documentation + Polish

12. Finalize all documentation
13. Record demo video
14. Prepare submission

---

## File-by-File Checklist

### Delete

- [ ] `modules/empowerment/alienation.py`
- [ ] `modules/empowerment/reflection.py`
- [ ] `modules/conversation/guards.py`
- [ ] `modules/conversation/research.py`
- [ ] `modules/conversation/simulators/`
- [ ] `modules/commerce/plan_builder.py`
- [ ] `docs/manifesto.md` (or archive)
- [ ] `docs/agency-layer.md`
- [ ] `docs/empowerment_metrics.md`
- [ ] `web/components/empowerment/WorldAvsB.tsx`
- [ ] `web/components/empowerment/ReflectionPrompt.tsx`

### Rename

- [ ] `modules/empowerment/` → `modules/alignment/`
- [ ] `modules/empowerment/goal_alignment.py` → `modules/alignment/scoring.py`
- [ ] `modules/empowerment/optimizer.py` → `modules/alignment/ranker.py`
- [ ] `modules/values/agent.py` → `modules/values/goal_elicitation.py`

### Rewrite

- [ ] `modules/alignment/domain.py`
- [ ] `modules/alignment/scoring.py`
- [ ] `modules/intent/domain.py`
- [ ] `modules/intent/inference.py`
- [ ] `modules/commerce/domain.py`
- [ ] `modules/memory/semantic.py`
- [ ] `modules/memory/episodic.py`
- [ ] `shared/llm/prompts.py`
- [ ] `shared/db/schema.sql`
- [ ] `api/routes/conversation.py`
- [ ] `docs/architecture.md` (replace with v2)
- [ ] `docs/strategic-positioning.md`
- [ ] `docs/build-plan.md`
- [ ] `docs/hackathon-plan.md`
- [ ] `docs/terminology.md`

### Create

- [ ] `modules/intentionality/__init__.py`
- [ ] `modules/intentionality/profiler.py`
- [ ] `modules/intentionality/enricher.py`
- [ ] `modules/intentionality/transforms.py`
- [ ] `docs/intent-inference.md`
- [ ] `docs/intentionality-profiles.md`
- [ ] `docs/alignment-scoring.md`
- [ ] `docs/discovery-metrics.md`
- [ ] `docs/theoretical-foundation.md`
- [ ] `web/components/alignment/AlignmentScore.tsx`
- [ ] `web/components/intent/IntentDisplay.tsx`
- [ ] `web/components/demo/DiscoveryDemo.tsx`

---

## Validation Criteria

Before considering implementation complete:

1. **Demo works**: Can show intent inference → alignment scoring → recommendation in 60 seconds
2. **No empowerment language**: Grep for "empowerment", "World A", "World B", "alienation", "impulse" — should return nothing in active code
3. **Docs aligned**: All docs tell the same story (intentionality optimization)
4. **API clean**: Only core endpoints remain
5. **Tests pass**: All remaining tests pass with new module structure

---

*Document Version: 2026-01-17*
*Status: DRAFT — Pending approval before execution*
