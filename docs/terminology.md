# Terminology Glossary

Status: current
Last verified: 2026-09-05
Baseline: `origin/main@96a1c23` (includes PR #120)

This document defines the core terms used across the agentic commerce codebase.

The goal is to ensure **conceptual precision**, prevent semantic drift, and align architecture with implementation.

---

## Agent-First Commerce Control Plane

**Definition**
The current product direction: a governed commerce execution surface where humans, internal agents, and external agents operate through scoped principals, policy profiles, skills, tools, and auditable execution receipts.

**Key Property**
> The UI is a supervision and intervention surface; the backend runtime is the execution substrate.

**In Code**
```
api/routes/agent_runs.py
application/services/agent_runtime/*
web/app/agent-runs/page.tsx
web/app/interventions/page.tsx
```

---

## Exact Approval

**Definition**
An immutable decision that authorizes one canonical executable payload, target,
capability contract, effect class, authority, policy, revision, and validity
window. Approval status alone is not execution authority.

**Key Property**
The payload approved is byte-for-byte the canonical payload consumed by
governed execution; defaults or normalization cannot be added afterward.

---

## Effect-Start Snapshot

**Definition**
Immutable evidence committed immediately before a governed effect begins,
binding the single-use effect identity to its exact approval, payload,
authority, lease, budget reservation, and registry contract.

**Key Property**
Reconciliation uses this snapshot, not mutable run or action projections.

---

## Governed Effect Receipt

**Definition**
A durable, effect-bound record proving the committed outcome of a governed
capability. A lab-promotion receipt binds tenant, experiment, variant, and
source metric after their relationship is revalidated transactionally.

**Key Property**
A receipt is evidence of the exact committed effect; a successful function
return or internally consistent but cross-tenant identifier set is not.

---

## Uncertain Effect

**Definition**
A governed effect that started but whose authoritative outcome was not safely
committed locally. It must not be retried as though no effect occurred.

---

## Effect Reconciliation

**Definition**
A tenant-authorized recovery command that discovers durable provider or local
evidence, verifies it against the immutable effect-start snapshot, commits the
outcome without re-executing the effect, and restores non-terminal projections
without overwriting cancellation or concurrent replanning.

---

## Principal

**Definition**
The actor whose authority is used for a run or event.

Allowed principal types:
- `human`
- `internal_agent`
- `external_agent`

**In Code**
```
api/utils/principals.py
shared/db/migrations/027_agent_first_slice.sql
```

---

## Skill

**Definition**
A reusable workflow capability for agents, composed from one or more policy-governed tools.

Examples:
- `optimize-product-representation`
- `request-validation-and-ingest-result`
- `triage-failed-run`

**In Code**
```
application/services/agent_runtime/agent_first.py
GET /agent-runs/registry
```

---

## Tool

**Definition**
A machine-facing operation identifier mapped from legacy runtime capabilities. Tools carry effect classes and side-effect declarations so policy can reason about execution risk.

Example:
`run_variant` maps to `experiment.run_variant`.

**In Code**
```
application/services/agent_runtime/registry/contracts.py
application/services/agent_runtime/agent_first.py
```

---

## Simulation Sandbox

**Definition**
A lab workspace where operators can simulate LLM shopping behavior to understand why products do or do not get recommended.

**Core Loop**
```
SET UP SCENARIO → SIMULATE → SEE RESULTS → OPTIMIZE → RE-TEST
```

**Key Property**
> The simulation sandbox remains useful, but it is now a lab surface inside the broader agent-first control plane.

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
> Alignment score is a **proxy** for semantic match + intent coverage (clarity, relevant signals).
> It can improve “LLM-friendliness”, but it does **not** guarantee rankings in any production shopping stack.

**Robustness Note**
This app can compute alignment via:
- `semantic` (embeddings-based similarity)
- `keyword` (signal/coverage-based)

A win that holds under both is reported as a stronger, more robust signal than a single-score lift.

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
- Alignment and experiment metrics are implemented in current backend services and routes.

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

## Agent Operator Mode

**Definition**
A planned operating mode where an automated agent can run the lab protocol (experiments/validation/learning loop) under strict constraints.

Key idea:
- agents have **plan autonomy** (they propose and queue actions),
- the system retains **execution enforcement** (guardrails, budgets, and approval gates).

**In Docs**
`docs/agentic-layer.md`

---

## AgentRuntime

**Definition**
A backend orchestration boundary that runs agent sessions as jobs.

An `agent_run` maintains:
- current protocol stage/state
- objective (what is being optimized)
- tenant scope (client/brand/product/experiment)
- allowed capabilities + pinned capability/policy versions

It emits a sequence of `agent_actions` (proposed and executed).

---

## Capability (Registry)

**Definition**
A named, versioned unit of system functionality that can be requested by agents or humans.

Examples:
- `freeze_retrieval_protocol`
- `run_control_baseline`
- `seed_hypotheses`
- `generate_variants`
- `run_variant`
- `request_synthetic_validation`
- `review_validation_readiness`
- `update_posterior_and_decisions`
- `recommend_next_action`
- `promote_variant_lab`
- `promote_variant_prod`
- `publish_copy_revision`

**Capability Registry**
A catalog that defines for each capability:
- input/output schema
- preconditions (policy checks)
- side effects (which artifacts/tables it can write)

Agents should request capabilities, not call raw API routes directly.

---

## Policy-as-Code (Enforcement)

**Definition**
Explicit system-side checks that enforce protocol correctness for both human and agent flows.

Examples:
- retrieval-backed runs require frozen snapshots (`snapshot_version`)
- baseline-first gating (control must be scored before candidates)
- spend/runs/query caps per cycle
- approval gates for promotion/publish actions

---

## Agent Action (Audit Event)

**Definition**
An auditable event that records an agent request and its outcome.

Typical fields:
- `agent_run_id`, `agent_id`
- `capability_name`, `capability_version`
- `inputs_hash`, `outputs_hash`
- scope anchors: `client_id`, `brand_id`, `product_id`, `experiment_id`
- protocol anchors: `snapshot_version`, `hypothesis_id`, `variant_id`
- `rationale`, `confidence`
- status: `proposed | approved | executed | rejected | failed`

---

## Capability/Policy Versioning

**Definition**
Versioning that captures experiment semantics, not just code changes.

Must cover:
- prompts/prompt versions
- scoring parameters
- validation weighting thresholds
- provider configs/modes

Purpose:
- keep results comparable over time
- make agent decisions reproducible and defensible

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

# Quick Reference (v1)

## Start the app (local)
```bash
# Backend
DATABASE_PATH=./tmp/local.db uv run uvicorn api.main:app --reload --port 8000

# Frontend
cd web
npm run dev
```

## Core Pages
- **Chat** (`/`) — generate intent + evidence
- **Alignment** (`/alignment`) — intent + goals + research alignment
- **Evidence** (`/evidence`) — winners, signals, next actions
- **Simulation** (`/simulation`) — optimize copy + feeds, re‑test
- **Experiments** (`/experiments`) — lab loop + batteries

## Evidence tabs
- **Evidence** — ranked open‑web results
- **Explanation** — score distribution + signal model
- **Next actions** — counterfactual lift + CTA to simulation

## Key Metrics
- **Alignment**: 0–1 product‑goal fit score
- **Win rate**: % queries where a variant wins
- **Avg score**: mean alignment across queries
- **Lift**: % improvement vs baseline
