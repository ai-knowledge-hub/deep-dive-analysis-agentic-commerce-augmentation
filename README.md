# World B: The Empowerment Commerce Engine

**AI shopping that optimizes for human flourishing, not clicks.**

> Google built the roads (UCP). OpenAI built the cars (Shopping Research). We built the compass that ensures you arrive where you actually want to go.

---

## The Fork

The same AI machinery that can maximize compulsion can maximize empowerment. The technology doesn't choose. **The objective function does.**

This codebase builds **World B**: where AI commerce becomes genuine service, where systems that help you buy things are aligned with your interests, not just your impulses.

| World A (Current Paradigm) | World B (What We Build) |
|---------------------------|------------------------|
| Optimize for clicks/conversion | Optimize for goal alignment |
| Infer intent from behavior | Ask users what they want |
| Products as desire objects | Products as capability tools |
| Urgency, scarcity, FOMO | Honest tradeoffs, alternatives |
| Track engagement | Measure empowerment |
| Silent data collection | Explicit consent gates |
| Funnel to purchase | Support "no purchase needed" |

Read the full thesis: [The Empowerment Imperative](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing)

---

## What This Is

This repository implements **Contextual Commerce Optimization (CCO)** — a paradigm where AI-driven commerce is subordinated to human intent.

We provide **the intelligence layer that transaction protocols don't define**:

```
┌─────────────────────────────────────────────────────────────┐
│              AI Agents (Gemini, ChatGPT, Claude)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           THIS REPO: World B Intelligence Layer             │
│                                                             │
│   "Should this purchase happen?"                            │
│   "Does it align with user's goals?"                        │
│   "What alternatives exist?"                                │
│   "Will they regret this?"                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         Commerce Protocols (UCP, ACP, Shopify, etc.)        │
└─────────────────────────────────────────────────────────────┘
```

**We are protocol-agnostic.** The empowerment layer works with Google's UCP, OpenAI's ACP, Shopify direct, or any future commerce protocol.

---

## Core Innovation: The Four Guardrails

Every interaction passes through four checkpoints that distinguish World B from World A:

| Guardrail | What It Does | Implementation |
|-----------|--------------|----------------|
| **Explicit Goals** | Ask what users want, don't infer from clicks | `modules/intent/`, `modules/values/` |
| **Consent Gates** | Personalization is off until opted in | `modules/memory/` |
| **Constraint Checks** | Hard limits on manipulation patterns | `modules/empowerment/alienation.py` |
| **Dual Reward Signal** | Optimize for agency AND performance | `modules/empowerment/optimizer.py` |

See [docs/agency-layer.md](docs/agency-layer.md) for the complete specification.

---

## Repository Structure

```
├── modules/                  # Core feature modules
│   ├── commerce/            # Product adapters, search, catalog
│   ├── intent/              # Goal clarification, intent classification
│   ├── memory/              # Working, episodic, semantic memory
│   ├── empowerment/         # Goal alignment, alienation detection, optimizer
│   ├── values/              # Values clarification agent
│   ├── conversation/        # Orchestration, context management
│   ├── mcp/                 # LLM-callable tools (MCP protocol)
│   ├── attribution/         # Event tracking, conversion attribution
│   └── evaluation/          # Empowerment metrics, A/B testing
│
├── shared/                   # Cross-cutting infrastructure
│   ├── llm/                 # Gemini, OpenRouter clients + prompts
│   ├── db/                  # SQLite schema + connection
│   └── config/             # Environment configuration
│
├── api/                      # FastAPI routes
├── web/                      # Next.js chat + empowerment dashboard
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

# 3. Run
uvicorn api.main:app --reload
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

# Run test suite
make test
```

---

## Documentation

### Philosophy & Vision

| Document | Purpose |
|----------|---------|
| [docs/manifesto.md](docs/manifesto.md) | Why this exists — World A vs World B philosophy |
| [docs/strategic-positioning.md](docs/strategic-positioning.md) | Market position, UCP/ACP integration, hackathon pitch |

### Architecture & Design

| Document | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | System architecture and module responsibilities |
| [docs/agency-layer.md](docs/agency-layer.md) | The four guardrails specification |
| [docs/terminology.md](docs/terminology.md) | Precise definitions (CCO, AIS, CCIA, etc.) |
| [docs/sequence-diagram.md](docs/sequence-diagram.md) | End-to-end interaction flow |

### Technical Reference

| Document | Purpose |
|----------|---------|
| [docs/empowerment_metrics.md](docs/empowerment_metrics.md) | Dual dashboard — what we measure |
| [docs/feed_schema.md](docs/feed_schema.md) | RawOffer → Product data pipeline |
| [docs/adapters.md](docs/adapters.md) | Shopify, Google Merchant adapter setup |
| [docs/attribution.md](docs/attribution.md) | AI-aware conversion attribution |
| [docs/deployment.md](docs/deployment.md) | Environment setup, deployment guide |

---

## Architectural Invariants

These rules are **non-negotiable**. If any are violated, the system collapses back into persuasive AI:

1. **Empowerment logic always outranks commerce logic**
2. **Memory must exist** (even if minimal)
3. **Agents orchestrate, modules decide**
4. **Products are instruments, not objectives**
5. **Reflection is mandatory feedback, not optional UX**

---

## Key Concepts

| Term | Definition |
|------|------------|
| **CCO** | Contextual Commerce Optimization — the optimization paradigm |
| **AIS** | Augmented Intentionality System — the governing constraints |
| **CCIA** | Context-Conditioned Intent Activation — goal clarification |
| **Empowerment** | The primary optimization objective |
| **Alienation** | What we detect and prevent |

See [docs/terminology.md](docs/terminology.md) for complete definitions.

---

## Environment Configuration

| Environment | Catalog | LLM Provider | Use Case |
|-------------|---------|--------------|----------|
| **Local** | `mock` | `openrouter` | Development without API costs |
| **Dev** | `google_merchant` | `gemini` | Preview deployments |
| **Prod** | `google_merchant` | `gemini` | Production with full telemetry |

Set `CATALOG_SOURCE` to choose: `mock`, `shopify`, `google_shopping`, or `google_merchant`.

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

We are **the missing half of agentic commerce**.

Google's UCP and OpenAI's ACP define *how* transactions flow. We define *whether* those transactions serve users.

| What They Built | What We Built |
|-----------------|---------------|
| Transaction plumbing | **Objective function** |
| Shopping Research | **Goal clarification** |
| Checkout flow | **Empowerment scoring** |
| Product discovery | **Alienation detection** |
| Order management | **Reflection loops** |

See [docs/strategic-positioning.md](docs/strategic-positioning.md) for complete competitive analysis and integration strategy.

---

## Research Foundation

This implementation operationalizes:

- [The Empowerment Imperative](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing) — Manifesto for agentic marketing that serves human flourishing
- **Computational Intentionality Theory (CIT)** — Framework treating AI advertising as a Turing-class machine whose objective function determines outcomes *(paper forthcoming)*

---

## Contributing

This is an open-source project exploring ethical AI commerce. Contributions welcome.

---

## License

Apache 2.0

---

> *Philosophy without code is commentary. This repo is the proof.*
