# Brand-Side Intentionality Optimization + Validation for LLM Commerce

**Make products legible to reasoning agents. Validate lift with real-world feedback.**

---

## What This Is

This repository implements a **brand-side intentionality optimization + validation layer** that turns product data into intent-legible structures and helps teams validate whether lab improvements hold in real traffic.

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

**We are protocol-agnostic.** The discovery layer works with UCP, ACP, or any future commerce protocol.

---

## Product Positioning

This app is a **screening + validation** system:
- Lab metrics are directional signals for LLM-friendliness.
- Manual validation logs and external analytics events provide reality checks.
- Pattern insights are soft-gated by validation progress.

We do **not** position lab scores as guaranteed production ranking outcomes.

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
| **Verification (Lift)** | Show before/after *simulated* discoverability impact | `domain/evidence/` + `application/services/evidence_verify.py` |
| **Simulation Sandbox** | Run → optimize → retest competitive scenarios | `domain/simulation/` + `application/services/simulation_service.py` |
| **Validation Logging** | Track lab predictions vs. observed outcomes | `api/routes/experiments.py` + `application/services/experiment_validation_service.py` |
| **Validation Jobs (BYOK)** | Run in-app or external validation with structured results | `api/routes/validation.py` + `application/services/validation_service.py` |
| **Context Memory** | Persist goals and preferences for better inference | `domain/memory/` + `infrastructure/db/*` |
| **Protocol Readiness** | Score UCP/ACP readiness (profiles + feed freshness + checkout/payment) | `infrastructure/protocol/*` + `application/services/simulation_service.py` |
| **Canonical Intent Spec** | Controlled onboarding fields for bottom-up query generation | `web/app/admin/page.tsx` + `products.metadata.canonical_intent_spec` |
| **Query Quality Gating** | Accept/reject generated queries with reject reasons | `application/services/query_battery_builder.py` |
| **Canonical Autofill** | UCP/ACP/feed to canonical spec (preview/apply) | `application/services/canonical_intent_spec_service.py` + `api/routes/admin.py` |

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

### Model gateway (BYOK)

Use **Admin → Operational controls → Model gateway** to set provider keys and active models:
- **Chat/generation key + model** drive all in-app LLM calls.
- **Validation key + model** are used only for validation jobs (fallbacks to chat key if empty).
- Activating a provider updates `.env.local` and refreshes the backend runtime.

Default model shortcuts (override in Admin if needed):
- OpenRouter: `openai/gpt-oss-120b`
- OpenAI: `gpt-5.2-2025-12-11`
- Claude (Anthropic): `claude-sonnet-4-5-20250929`
- Gemini: `gemini-3-flash-preview`

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

# Battery eval loop summary
curl "http://localhost:8000/batteries/<battery_id>/eval-summary?client_id=default"

# Run test suite
make test
# Lint backend + frontend
make lint
make web-lint
```

### LLM Provider Health

Check which providers are configured:

```
curl "http://localhost:8000/health/llm"
```

### Validation Page

Open `http://localhost:3000/validation` to run in-app BYOK validations or submit
external paste-back JSON. Provider readiness is shown at the top of the page.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/user-guide-complete.md](docs/user-guide-complete.md) | User manual (current features) |
| [docs/app-architecture.md](docs/app-architecture.md) | Comprehensive architecture (current + planned) |
| [docs/app-workflows.md](docs/app-workflows.md) | All workflows and how they connect |
| [docs/terminology.md](docs/terminology.md) | Glossary + quick reference |
| [docs/future-roadmap.md](docs/future-roadmap.md) | Deferred features (planned) |
| [docs/deployment.md](docs/deployment.md) | Environment setup, deployment guide |
| [docs/validation-mcp.md](docs/validation-mcp.md) | Validation MCP tool schema (draft) |

---

## Architectural Invariants

These rules keep the system grounded in intent legibility:

1. **Intent inference drives proxy ranking**
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
| **Discoverability Lift** | Improvement in simulated “LLM‑friendliness” metrics |

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
make db-migrate # alias of db-init (re-apply schema bootstrap)
make db-validate-migrate # apply validation job/result migrations
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
DATABASE_PATH=./tmp/local.db make seed-canonical
DATABASE_PATH=./tmp/local.db make seed-demo-acme
DATABASE_PATH=./tmp/local.db make db-validate-migrate
DATABASE_PATH=./tmp/local.db uv run uvicorn api.main:app --reload --port 8000

Seed demo data (Acme Sports):
make seed-demo-acme
```

`seed-canonical` populates `canonical_intent_spec` for existing products so bottom-up
query generation can run without clarification blocks.

Quick verify:

```bash
sqlite3 ./tmp/local.db "select id,name from clients order by name;"
```

---

## Contributing

This is an open-source project exploring LLM commerce discovery. Contributions welcome.

---

## License

Apache 2.0

---

> *Discovery without intent legibility is noise. This repo makes it signal.*
