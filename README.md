# Brand-Side Intentionality Optimization + Verification for LLM Commerce

**Make products legible to reasoning agents. Prove the lift.**

> Google built the roads (UCP). OpenAI built the cars (Shopping Research). We built the compass that helps products get discovered.

---

## What This Is

This repository implements a **brand-side intentionality optimization + verification layer** that turns product catalogs into intent‑legible data structures and proves they lift organic AI recommendations.

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
│         Commerce Protocols (UCP, ACP, Shopify, etc.)        │
└─────────────────────────────────────────────────────────────┘
```

**We are protocol-agnostic.** The discovery layer works with Google's UCP, OpenAI's ACP, Shopify direct, or any future commerce protocol.

---

## Core Innovation: Intentionality + Alignment

We make products **intent‑legible** and rank them by alignment with inferred goals.

| Capability | What It Does | Implementation |
|-----------|--------------|----------------|
| **Intent Inference** | Model user goals from query + context | `modules/intent/` |
| **Intentionality Profiling** | Transform specs → capabilities → outcomes | `modules/intentionality/` |
| **Alignment Scoring** | Score products against inferred intent | `modules/alignment/` |
| **Evidence Discovery** | Analyze open-web representations for intent legibility | `modules/evidence/` |
| **Verification (Lift)** | Show before/after discoverability impact | `modules/evidence/` |
| **Context Memory** | Persist goals and preferences for better inference | `modules/memory/` |

---

## Repository Structure

```
├── modules/                  # Core feature modules
│   ├── commerce/            # Product adapters, search, catalog
│   ├── intent/              # Intent inference + classification
│   ├── intentionality/      # Product intent profiling
│   ├── alignment/           # Intent-product alignment scoring
│   ├── memory/              # Working, episodic, semantic memory
│   ├── conversation/        # Orchestration, context management
│   ├── values/              # Goal clarification dialogue
│   ├── mcp/                 # LLM-callable tools (MCP protocol)
│   ├── attribution/         # Event tracking, conversion attribution
│   └── evaluation/          # Discovery metrics, A/B testing
│
├── shared/                   # Cross-cutting infrastructure
│   ├── llm/                 # Gemini, OpenRouter clients + prompts
│   ├── db/                  # SQLite schema + connection
│   └── config/             # Environment configuration
│
├── api/                      # FastAPI routes
├── web/                      # Next.js chat + discovery dashboard
├── data/                     # Product catalogs, intent taxonomy
├── docs/                     # Architecture & design documentation
└── tests/                    # Module + integration tests
```

**Key principle:** Only `modules/` defines system behavior. Everything else can be replaced without changing what the system optimizes for.

---

## Quick Start

### Backend (FastAPI)

```bash
# 1. Set up environment
cp .env.example .env.local
# Edit .env.local: set OPENROUTER_API_KEY for local dev

# 2. Install dependencies
uv sync

# 3. Run (use uv to ensure the venv is active)
uv run uvicorn api.main:app --reload
```

### Frontend (Next.js)

```bash
cd web
cp .env.local.example .env.local
pnpm install && pnpm dev
```

Visit `http://localhost:3000` for the chat interface.

### Verify

```bash
# Test product search
curl "http://localhost:8000/products/search?query=workspace"

# Evidence-first demo flow
curl -X POST "http://localhost:8000/evidence/analyze" \
  -H "Content-Type: application/json" \
  -d '{"query": "TV for a bright living room"}'

# Run test suite
make test
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | Intentionality optimization architecture |
| [docs/strategic-positioning.md](docs/strategic-positioning.md) | Market positioning, UCP/ACP integration |
| [docs/build-plan.md](docs/build-plan.md) | Execution plan for the pivot |
| [docs/product-workflow.md](docs/product-workflow.md) | Brand workflow: connect → analyze → optimize → deploy → verify |
| [docs/terminology.md](docs/terminology.md) | Definitions and naming conventions |
| [docs/sequence-diagram.md](docs/sequence-diagram.md) | End-to-end interaction flow |
| [docs/adapters.md](docs/adapters.md) | Shopify, Google Merchant adapter setup |
| [docs/feed_schema.md](docs/feed_schema.md) | RawOffer → Product data pipeline |
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

| Environment | Catalog | LLM Provider | Use Case |
|-------------|---------|--------------|----------|
| **Local** | `mock` | `openrouter` | Development without API costs |
| **Dev** | `google_merchant` | `gemini` | Preview deployments |
| **Prod** | `google_merchant` | `gemini` | Production with full telemetry |

Set `CATALOG_SOURCE` to choose: `mock`, `shopify`, `google_shopping`, or `google_merchant`.
When `CATALOG_SOURCE=mock`, the catalog stream is disabled and the UI shows research insights only to avoid misleading recommendations.

Evidence-first demo data loads from `data/evidence_demo.json` when `EVIDENCE_DEMO=true`
(default). Override with `EVIDENCE_DEMO_PATH` if you want a different dataset.

Copy `.env.example` to `.env.local` and adjust for your environment.

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

## Research Foundation

This implementation builds on:

- **Intent inference / theory of mind in LLMs** — LLMs model goals and can align products to those goals.
- **Active inference / free energy** — recommendations that fit context reduce uncertainty.
- **Computational Intentionality Theory (CIT)** — products become discoverable when mapped to human capabilities *(paper forthcoming)*.

---

## Contributing

This is an open-source project exploring LLM commerce discovery. Contributions welcome.

---

## License

Apache 2.0

---

> *Discovery without intent legibility is noise. This repo makes it signal.*
