# Brand-Side Intentionality Optimization + Verification for LLM Commerce

**Make products legible to reasoning agents. Prove the lift.**

> Google built the roads (UCP). OpenAI built the cars (Shopping Research). We built the compass that helps products get discovered.

---

## What This Is

This repository implements a **brand-side intentionality optimization + verification layer** that turns product data into intent‑legible structures and proves they lift organic AI recommendations.

We provide **the discovery layer that transaction protocols don't define**, working at the source data brands control:

```
┌─────────────────────────────────────────────────────────────┐
│              AI Agents (Gemini, ChatGPT, Claude)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│      THIS REPO: Brand-Side Optimization + Verification      │
│                                                             │
│   "What is the user trying to achieve?"                     │
│   "Which products enable that goal?"                        │
│   "Why does this product align with intent?"                │
│   "Did optimization improve discoverability?"               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         Commerce Protocols (UCP, ACP, etc.)                 │
└─────────────────────────────────────────────────────────────┘
```

**We are protocol-agnostic.** The discovery layer works with Google's UCP, OpenAI's ACP, or any future commerce protocol.

---

## Core Innovation: Intentionality + Alignment

We make products **intent‑legible** and rank them by alignment with inferred goals.

**Alignment (current model, explainable):**
- Signal‑overlap scoring across **intent signals**, **evidence signals**, and **our copy**.
- **Hard category gate**: if the query specifies a category (e.g., *shoes*) and the product copy doesn’t mention that category (or synonyms), the score is forced to **0** to prevent false positives.
- This baseline is transparent and auditable; semantic/Bayesian weighting is on the roadmap.

| Capability | What It Does | Implementation |
|-----------|--------------|----------------|
| **Intent Inference** | Model user goals from query + context | `domain/intent/` + `application/services/*` |
| **Intentionality Profiling** | Transform specs → capabilities → outcomes | `domain/intentionality/` + `application/services/intentionality_profiler.py` |
| **Alignment Scoring** | Score products against inferred intent | `domain/alignment/` + `infrastructure/alignment/goal_alignment_gateway.py` |
| **Evidence Discovery** | Analyze open-web representations for intent legibility | `domain/evidence/` + `application/services/evidence_service.py` |
| **Signal Extraction (Skills)** | Convert intent → phrase-level signals via editable skill prompts | `application/services/signal_extractor.py` + `infrastructure/db/skills.py` |
| **Verification (Lift)** | Show before/after discoverability impact | `domain/evidence/` + `application/services/evidence_verify.py` |
| **Simulation Sandbox** | Run → optimize → retest competitive scenarios | `domain/simulation/` + `application/services/simulation_service.py` |
| **Context Memory** | Persist goals and preferences for better inference | `domain/memory/` + `infrastructure/db/*` |
| **Protocol Readiness** | Score UCP/ACP readiness (profiles + feed freshness + checkout/payment) | `infrastructure/protocol/*` + `application/services/simulation_service.py` |

---

## Repository Structure

```
├── domain/                   # Pure types + pure logic (no IO)
├── application/              # Use-cases / orchestration services
├── infrastructure/           # DB/LLM/adapters (IO boundaries)
│   ├── llm/                  # Gemini/OpenRouter clients + gateway
├── shared/                   # Cross-cutting infrastructure
│   ├── llm/                  # Prompt templates
│   ├── db/                  # SQLite schema + connection
│   └── config/             # Environment configuration
│
├── api/                      # FastAPI routes
├── web/                      # Next.js chat + discovery dashboard
├── data/                     # Product data mocks, intent taxonomy
├── docs/                     # Architecture & design documentation
├── scripts/                  # Local dev utilities (seed, exports, etc.)
└── tests/                    # Module + integration tests
```

**Key principle:** `domain/` + `application/` define the system’s behavior; `infrastructure/` can be swapped without changing what the system optimizes for.

**Primary users:** Brand marketing managers, ecommerce growth teams, and agencies optimizing product visibility in AI discovery. Secondary users include commerce developers integrating intent alignment into their stacks.

---

## Quick Start

### Backend (FastAPI)

```bash
# 1. Set up environment
cp .env.example .env.local
# Edit .env.local: set OPENROUTER_API_KEY for local dev
# Optional: ADMIN_USER_IDS=user_123,user_456 (bypass client_id requirement)
# Optional: CLERK_WEBHOOK_SECRET=whsec_... (for Clerk user sync)

# 2. Install dependencies
uv sync

# 3. Run (use uv to ensure the venv is active)
uv run uvicorn api.main:app --reload
```

### Frontend (Next.js)

```bash
cd web
cp ../.env.example .env.local
# Edit web/.env.local: set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY + CLERK_SECRET_KEY
# Optional: NEXT_PUBLIC_API_URL=http://localhost:8000
# Required: NEXT_PUBLIC_CLIENT_ID=default (or your tenant id)
# Optional: NEXT_PUBLIC_ADMIN_MODE=true (shows manual client/brand/product pickers)
pnpm install && pnpm dev
```

Visit `http://localhost:3000` for the chat interface.

### Multi-tenant scoping

All API calls require `client_id` unless the caller is an admin user (see `ADMIN_USER_IDS`).
`brand_id` and `product_id` are optional on simulation endpoints for tying runs to a product record.
The UI exposes a manual admin context picker when `NEXT_PUBLIC_ADMIN_MODE=true` so you can
switch client/brand/product without automated onboarding.

### Skill prompts (admin-editable)

Signal extraction and copy generation run from **skills stored in the DB**.  
You can edit them in **Admin → Agent skills**. Each update writes an **audit trail** into
`skills_history` for traceability and safe iteration.

### Clerk user sync (webhook)

Set a Clerk webhook pointing to `POST /webhooks/clerk` with signing enabled, then store
`CLERK_WEBHOOK_SECRET` in `.env.local`. We upsert the local `users` table with email/name
metadata on `user.created` / `user.updated`, and mark as deleted on `user.deleted`.

### Verify

```bash
# Test product search
curl "http://localhost:8000/products/search?query=workspace&client_id=default"

# Evidence-first demo flow
curl -X POST "http://localhost:8000/evidence/analyze" \
  -H "Content-Type: application/json" \
  -d '{"query": "TV for a bright living room", "client_id": "default"}'

# Simulation sandbox
curl -X POST "http://localhost:8000/simulation/run" \
  -H "Content-Type: application/json" \
  -d '{"query": "running vest", "client_id": "default", "products": [{"id":"sim-1","name":"Trail Runner Vest","description":"Lightweight vest for long runs with breathable mesh.","source":"web"}]}'

# List lessons learned (optional)
curl "http://localhost:8000/simulation/lessons?client_id=default"

# Run test suite
make test
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/user-guide-complete.md](docs/user-guide-complete.md) | Full user manual |
| [docs/product-workflow.md](docs/product-workflow.md) | Automated lab workflow |
| [docs/architecture-visual.md](docs/architecture-visual.md) | System diagrams |
| [docs/evidence-first-flow.md](docs/evidence-first-flow.md) | Evidence + explanation UX |
| [docs/brand-belief-system.md](docs/brand-belief-system.md) | Belief updates & memory |
| [docs/experiment-orchestrator-enhancements.md](docs/experiment-orchestrator-enhancements.md) | Orchestrator logic |
| [docs/future-roadmap.md](docs/future-roadmap.md) | Deferred features |
| [docs/terminology.md](docs/terminology.md) | Definitions and naming conventions |
| [docs/2-layer-arch/arch-migratoion/agentic-arch-transformation.md](docs/2-layer-arch/arch-migratoion/agentic-arch-transformation.md) | Why + what to change for agentic clean architecture |
| [docs/2-layer-arch/arch-migratoion/agentic-arch-execution-summary.md](docs/2-layer-arch/arch-migratoion/agentic-arch-execution-summary.md) | Step-by-step execution plan (incremental) |
| [docs/deployment.md](docs/deployment.md) | Environment setup, deployment guide |

---

## Architectural Invariants

These rules keep the system grounded in intent legibility:

1. **Intent inference drives ranking**
2. **Products are represented as capabilities, not specs**
3. **Alignment scores are explainable**
4. **Memory improves inference (not surveillance)**
5. **Adapters stay protocol-agnostic**

---

## Key Concepts

| Term | Definition |
|------|------------|
| **Intentionality Profile** | Product representation in terms of capabilities and outcomes |
| **Intent Inference** | Modeling user goals from query + context |
| **Alignment Score** | Match confidence between intent and product |
| **Discoverability Lift** | Improvement in organic LLM recommendations |

See [docs/terminology.md](docs/terminology.md) for complete definitions.

---

## Environment Configuration

| Environment | LLM Provider | Use Case |
|-------------|--------------|----------|
| **Local** | `openrouter` | Development without API costs |
| **Dev** | `gemini` | Preview deployments |
| **Prod** | `gemini` | Production with full telemetry |

Evidence data is generated from the latest chat session and stored per client.
(default). Override with `EVIDENCE_DEMO_PATH` if you want a different dataset.

Protocol readiness (UCP/ACP) is computed from brand profiles + feed metadata and shown in the
Simulation Sandbox “Why you lost” section and history list. Seeded demo brands include
mock UCP business profiles and ACP feed fields to make readiness scores visible.

Copy `.env.example` to `.env.local` for backend settings, and add Clerk keys to
`web/.env.local` for the frontend.

---

## Testing

```bash
make test          # Run full test suite
make lint          # Check code style
```

The test suite covers module-level unit tests, MCP tool execution, conversation API routes, and clarification workflow integration.

## Database Initialization

SQLite is initialized automatically when `SessionManager` or any memory repository is used. The schema is loaded from `shared/db/schema.sql`.

Manual helpers:

```bash
make db-init   # create/open DB and apply schema
make db-reset  # delete local DB and re-init
make db-path   # print current DB path
make seed-demo # seed demo multi-tenant clients/brands/products
```

### Local dev DB (seeded demo tenants)

If you want the UI client dropdown to show the seeded demo tenants (Nike/Adidas/Under Armour/New Balance/Reebok), make sure you **seed and run against the same SQLite file**.

Example using the local dev DB (`./tmp/local.db`):

```bash
rm -f ./tmp/local.db
DATABASE_PATH=./tmp/local.db ./.venv/bin/python -m shared.db.connection
DATABASE_PATH=./tmp/local.db make seed-demo
DATABASE_PATH=./tmp/local.db uv run uvicorn api.main:app --reload --port 8000
```

Quick verify:

```bash
sqlite3 ./tmp/local.db "select id,name from clients order by name;"
```

---

## Strategic Position

We are **the missing brand-side discovery layer for agentic commerce**.

UCP and ACP define *how* transactions flow. We define *why* a product gets recommended by a reasoning agent.

| What They Built | What We Built |
|-----------------|---------------|
| Transaction plumbing | **Intent legibility layer** |
| Shopping Research | **Alignment scoring** |
| Checkout flow | **Product intentionality profiling** |
| Catalog ingestion | **Discoverability metrics** |

See [docs/strategic-positioning.md](docs/strategic-positioning.md) for the full positioning narrative.


---

## Contributing

This is an open-source project exploring LLM commerce discovery. Contributions welcome.

---

## License

Apache 2.0

---

> *Discovery without intent legibility is noise. This repo makes it signal.*
