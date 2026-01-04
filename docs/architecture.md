# Architecture Overview  
## Agentic Commerce as Contextual Commerce Optimization (CCO)

---

## 1. Purpose of This Architecture

This repository implements **Agentic Commerce as a Contextual Commerce Optimization (CCO) system**, designed from first principles around the **Augmented Intentionality System (AIS)**.

Rather than building a generic commerce platform first and layering ethics or empowerment later, this codebase **starts with empowerment as the objective function** and directly optimizes commerce around it.

The architecture demonstrates that:

> AI-driven commerce can be optimized for **human capability, autonomy, and goal alignment** — not just conversion.

This repository is intentionally designed to:
- Treat **Contextual Commerce Optimization (CCO)** as an *optimization paradigm*, not a pre-existing platform
- Preserve **memory and empowerment** as first-class architectural concepts
- Remain **hackathon-friendly, demo-ready, and extensible** to future runtimes (GPT apps, Gemini apps, search, programmatic, social)

### Research Basis

This architecture operationalizes the thesis from [*The Empowerment Imperative: Rewriting Agentic Marketing from Extraction to Human Flourishing*](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing) (Performics Labs, 2026). That paper frames agentic marketing as a fork between extraction loops (World A) and empowerment-oriented trajectories (World B), calls for a minimal “agency layer” (explicit goals, consent gates, constraint checks, agency reward signals), and declares that agentic marketing inevitably converges into agentic commerce. The code in this repo is the embodiment of that manifesto: a first concrete CCO system where empowerment logic, constraint enforcement, and agency metrics are the optimization targets rather than afterthoughts.

This repo is also the first applied use case of the forthcoming foundational research *From Computable to Desirable: Redesigning AI Advertising as an Engine for Intentional Human Development*. That broader work introduces **Computational Intentionality Theory (CIT)**—a framework that treats AI advertising like a Turing-class machine whose objective function determines whether it becomes an alienation engine or an Augmented Intentionality System (AIS). While the general CIT platform is still under development, this commerce implementation serves as its proof-of-concept: values clarification, capability scaffolding, autonomy-preserving nudges, wellbeing-aligned metrics, and participatory governance are all implemented here in miniature so we can validate the theory before publishing the full paper and generalized runtime.

---

## 2. Layered Architecture (Mental Model)

The system is organized into **three strict layers**:

```
┌──────────────────────────────────────────┐
│ UI / Demo Layer                          │
│ (chat, modals, flows, hackathon UX)      │
└──────────────────────────────────────────┘
↓
┌──────────────────────────────────────────┐
│ Agent Façade Layer                       │
│ (thin orchestration, no core logic)      │
└──────────────────────────────────────────┘
↓
┌──────────────────────────────────────────┐
│ Core Cognition Layer (src/)              │
│ Intent · Memory · Empowerment · MCP      │
└──────────────────────────────────────────┘
```
**Only the bottom layer defines system behavior.**  
Everything above it can be replaced without changing the system’s meaning.

---

## 2.1 Implementation Directories (Clean Boundaries, Pragmatic Modules)

To keep the philosophy portable, the repo mirrors these layers without forcing
Clean Architecture everywhere:

- `core/` — canonical schemas, text utilities, and transformers. These modules
  have zero platform dependencies and can be reused in any runtime.
- `adapters/` — integration surfaces (Shopify, CSV, mock loaders). They are
  intentionally messy and may depend on vendor SDKs.
- `src/` — legacy glue while we migrate existing logic into the new layout.
- `agents/` and `demos/` — façade logic and hackathon-ready experiences; allowed
  to be lightweight scripts so we don’t over-engineer conversational flows.
- `attribution/` and `evaluation/` — measurement scaffolding that proves
  empowerment wins in practice.
- `api/` — thin FastAPI bindings that expose the core feed + search features.

This mapping preserves the empowerment-first constraints (objective function,
memory, autonomy guardrails) while giving contributors a clear place to plug in
without coupling unrelated concerns.

---

## 3. Core Cognition Layer (`src/`) — Source of Truth

The `src/` directory defines the **canonical Contextual Commerce Optimization core**.

Any logic that affects:
- decisions
- scoring
- constraints
- outcomes

**must live here**.

This layer is framework-agnostic and portable to future production systems.

---

### 3.1 Intent Module (`src/intent/`)

**Responsibility**
Understand *what the user is trying to achieve*, not just what they are searching for.

**Key concepts**
- Contextual intent (CCIA)
- Intent taxonomies
- Intent grounding before commerce execution

This module ensures that **commerce is always downstream of clarified human goals**.

**Critical Design Note: Intent ≠ Objective Function**

The intent taxonomy (`data/intent_taxonomy.json`) provides **routing signals**, not optimization targets. It helps the system understand the domain of a request (workspace, health, career) to ask better clarifying questions.

The **actual objective function** operates on user-declared goals stored in semantic memory (`src/memory/semantic.py`). These goals are:
- Free-form strings in the user's own words
- Explicitly stated, not inferred from behavior
- The target against which all recommendations are scored

This distinction is critical:
- **World A** would infer intent from clicks and optimize toward platform-defined categories
- **World B** asks the user what they want and optimizes toward their stated goals

The intent classifier is a heuristic helper. The goal alignment engine (`src/empowerment/goal_alignment.py`) is the objective function.

---

### 3.2 Memory Module (`src/memory/`)

**Responsibility**  
Preserve continuity, learning, and agency over time.

| Memory Type | Purpose |
|------------|--------|
| `working.py` | In-session state |
| `episodic.py` | Post-action reflection (“Did this help?”) |
| `semantic.py` | Long-term goals, values, and capabilities |

Without memory, the system is a chatbot.  
With memory, the system becomes **agentic**.

Hackathon implementations are lightweight but **structurally correct**.

---

### 3.3 Products Module (`src/products/`)

**Responsibility**  
Provide agentic access to catalogs **without embedding persuasion logic**.

Products are treated as **capability-enabling tools**, not desire objects.

Schemas emphasize:
- capabilities enabled
- prerequisites
- effort required
- alternatives

They explicitly avoid:
- urgency
- popularity
- social proof
- manipulation signals

#### Ingestion Surfaces (RawOffer → RawProduct → Product)

LLM-mediated commerce spans merchant-owned catalogs (e.g., Shopify) and third-party discovery graphs (e.g., Google Shopping). To prevent any source from leaking platform semantics upstream, adapters emit **RawOffer** objects that describe:

- `source` (shopify, google_shopping, amazon, etc.)
- `confidence` and `completeness` scores
- merchant metadata (offer URL, merchant name)
- asserted vs. inferred attributes

These offers are converted into **RawProduct** entries (variant-level truth) and finally into canonical **Product** models that power reasoning. This layered pipeline lets the empowerment objective function reason about uncertainty:

- First-party feeds (Shopify) → high confidence, precise variants
- Aggregated feeds (Google Shopping) → lower confidence, explicit caveats

The agent can therefore say “this is a strong candidate” vs. “this is a hunch,” preserving autonomy even when data quality varies.

---

### 3.4 Empowerment Module (`src/empowerment/`) — AIS Core

This module implements the **Augmented Intentionality System**.

It defines **what the system is allowed to optimize for**.

| File | Responsibility |
|----|---------------|
| `goal_alignment.py` | Aligns actions with user-stated goals |
| `alienation.py` | Detects manipulation & autonomy erosion |
| `optimizer.py` | Optimizes for agency, not CTR |
| `reflection.py` | Closes the learning loop |
| `schemas.py` | Shared empowerment ontology |

This module **replaces traditional engagement optimization**.

It is:
- P0
- invariant
- non-optional

---

### 3.5 MCP Module (`src/mcp/`)

**Responsibility**  
Expose system capabilities as **LLM-callable tools**.

This enables:
- Gemini integration
- GPT App portability
- tool-based reasoning instead of prompt-only systems

No business logic lives here — **only interfaces**.

---

## 4. Agent Façade Layer (`agents/`)

Agents are **thin orchestration wrappers**.

They:
- coordinate calls across modules
- manage execution order
- adapt to UI / LLM constraints

They do **not**:
- define objectives
- score outcomes
- override empowerment logic

If logic appears here, it belongs in `src/`.

---

## 5. UI / Demo Layer (`ui/`, `app.py`)

This layer exists to:
- demonstrate behavior
- support hackathon UX
- enable fast iteration

It is **intentionally disposable**.

The system remains valid even if this layer is removed.

---

## 6. Data & Demos

- `data/` contains **explicit schemas**, not scraped behavior
- `demos/` provide **goal-driven scenarios**, not funnels

All demos follow the same pattern:

goal → capability → choice → reflection

---

## 7. Architectural Invariants (Non-Negotiable Rules)

These rules apply to this repository and all future CCO implementations:

1. Empowerment logic always outranks commerce logic  
2. Memory must exist (even if minimal)  
3. Agents orchestrate, modules decide  
4. Products are instruments, not objectives  
5. Reflection is mandatory feedback, not optional UX  

If any of these are violated, the system collapses back into persuasive AI.

---

## 8. Relationship to Contextual Commerce Optimization (CCO)

Contextual Commerce Optimization (CCO) is **not a separate system implemented elsewhere**.

CCO is the **optimization paradigm embodied by this architecture**:
- commerce decisions are evaluated in human context
- intent is clarified before execution
- empowerment, not conversion, is the objective function

This repository represents the **first concrete CCO implementation**, directly optimized around:
- Augmented Intentionality
- memory-preserving agency
- autonomy-constrained recommendations

Future expansions (search, programmatic, social, conversational agents) are **additional CCO runtimes**, not prerequisites.

> **CCO is defined by its objective function, not by a platform boundary.**

---

## 9. Why This Architecture Matters

This architecture demonstrates a critical point:

> AI systems can be both **commercially useful** and **human-aligned**  
> if the objective function is designed correctly.

Agentic Commerce is not rejected —  
it is **subordinated to human intent**.

---

## 10. Summary

- `src/` defines cognition  
- `empowerment/` defines ethics and optimization  
- `memory/` enables agency  
- `agents/` orchestrate  
- `ui/` demonstrates  

Everything else is implementation detail.

---

**End of Architecture Overview**
