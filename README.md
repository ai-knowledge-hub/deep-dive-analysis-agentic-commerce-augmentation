# Agentic Commerce Augmentation

**An empowerment-first commerce platform that optimizes for human flourishing, not clicks.**

This repository implements [Contextual Commerce Optimization (CCO)](https://ai-news-hub.performics-labs.com/news/agentic-commerce-llm-shopping-revolution) — a paradigm where AI-driven commerce is subordinated to human intent, not the other way around.

> Philosophy without code is commentary. This repo is the proof.

---

## The Fork

The same AI machinery that can maximize compulsion can maximize empowerment. The technology doesn't choose. The objective function does.

This codebase builds **World B**: where marketing becomes genuine service, where systems that help you buy things are aligned with your interests, not just your impulses.

Read the full thesis: [The Empowerment Imperative](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing)

---

## Architecture

```
┌────────────────────────────────────────┐
│ Research & Ethics Layer                │
│ (CIT, AIS, Empowerment Theory)         │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│ Core Platform (CCO)                    │
│ Memory · Intent · Products · MCP       │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│ Demo / Runtime Surfaces                │
│ Hackathon · GPT App · Gemini App       │
└────────────────────────────────────────┘
```

**Key principle:** Only the Core Platform defines system behavior. Everything above it can be replaced without changing the system's meaning.

---

## Repository Layout

```
├── app.py                    # Demo entrypoint
├── vision.md                 # High-level platform vision
│
├── core/                     # Canonical schemas & transformers (vendor-agnostic)
├── adapters/                 # Shopify + mock feed adapters
├── src/                      # Legacy core logic (intent, memory, empowerment, MCP)
├── orchestration/            # Façade services orchestrating domain modules
├── attribution/              # AI-aware measurement scaffolding
├── evaluation/               # Representation A/B testing harness
├── api/                      # Thin FastAPI interface
├── demos/                    # Sample empowerment journeys and fixtures
├── web/                      # Next.js chat + empowerment dashboard
├── data/                     # Empowerment catalog + fixtures
└── docs/                     # Architecture & design documentation
```

---

## Quick Start

```bash
# Validate imports and run stub runtime
python app.py
```

### Next.js UI

```bash
cd web
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL if backend is remote
pnpm install
pnpm dev
```

The chat experience consumes the FastAPI routes (`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`).

### FastAPI Surface

```bash
uvicorn api.main:app --reload
```
The backend automatically loads `.env.local` / `.env`, so set environment-specific values there. For example:

- `.env.local`: `CATALOG_SOURCE=mock`, `LLM_PROVIDER=openrouter`, `DATABASE_PATH=./tmp/local.db`.
- `.env.dev`: `CATALOG_SOURCE=google_merchant`, `LLM_PROVIDER=gemini`, `GOOGLE_MERCHANT_FEED_PATH=...`.

Switch catalog sources by editing the env file instead of exporting variables manually.

Try `http://localhost:8000/products/search?query=workspace` to verify the feed.

### Catalog Sources

The platform loads products via adapters. Set `CATALOG_SOURCE` to choose the
source (`mock`, `shopify`, `google_shopping`, `google_merchant`). When using Shopify, provide
`SHOPIFY_DOMAIN` and `SHOPIFY_TOKEN` in your environment (see `.env.example`). For Google Merchant, supply `GOOGLE_MERCHANT_FEED_PATH`.

### Environment Strategy

- `.env.local`: Local development (mock catalog, SQLite in `./tmp`, `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`). The backend loads this automatically.
- `.env.dev` or managed secrets: Preview deployments (e.g., Railway backend) using `CATALOG_SOURCE=google_merchant`, `LLM_PROVIDER=gemini`, limited `GOOGLE_API_KEY`.
- Production secrets: Same as dev but with production feeds, telemetry, and prod Gemini credentials.
- When using OpenRouter locally, define `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, and optionally `OPENROUTER_SITE_URL` / `OPENROUTER_APP_NAME` so completions identify your app.

Copy the relevant section from `.env.example` into `.env.local` (or `.env` for dev/prod). The app auto-loads it; you can still override with `export` if needed.


## Testing

```bash
make test   # (falls back to python3 -m pytest)
```

The suite exercises the LLM agents, orchestration services, and conversation API (including clarification workflow and empowerment reasoning). Frontend/Next.js tests are deferred until the UI stabilizes; for now, keep visual verification in the web app.

### Continuous Integration

Use the Makefile targets in your CI pipeline so local and remote runs stay in sync. For example, a GitHub Actions workflow:

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        run: pip install -r requirements.txt ruff
      - name: Lint
        run: make lint
      - name: Test
        run: make test
```

Add additional steps (e.g., `make run-frontend` for smoke tests) as needed for dev/prod branches. Remember to configure secrets for Gemini/OpenRouter keys in the workflow if you extend tests that hit live providers.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/manifesto.md](docs/manifesto.md) | Why this exists — World A vs World B |
| [docs/architecture.md](docs/architecture.md) | How the system is built |
| [docs/agency-layer.md](docs/agency-layer.md) | The four guardrails specification |
| [docs/empowerment_metrics.md](docs/empowerment_metrics.md) | The dual dashboard — what we measure |
| [docs/terminology.md](docs/terminology.md) | Precise definitions for all concepts |
| [docs/sequence-diagram.md](docs/sequence-diagram.md) | End-to-end interaction flow |
| [docs/adapters.md](docs/adapters.md) | Shopify/Google adapter setup |
| [docs/feed_schema.md](docs/feed_schema.md) | RawOffer → Product schema |
| [docs/attribution.md](docs/attribution.md) | AI-aware attribution loop |
| [docs/deployment.md](docs/deployment.md) | Local/HF/FastAPI deployment guide |

---

## Core Concepts

| Concept | Definition |
|---------|------------|
| **CCO** | Contextual Commerce Optimization — the optimization paradigm |
| **AIS** | Augmented Intentionality System — the governing constraints |
| **CCIA** | Context-Conditioned Intent Activation — goal clarification |
| **Empowerment** | The primary optimization objective |
| **Alienation** | What we detect and prevent |

See [docs/terminology.md](docs/terminology.md) for complete definitions.

---

## Architectural Invariants

These rules are non-negotiable:

1. Empowerment logic always outranks commerce logic
2. Memory must exist (even if minimal)
3. Agents orchestrate, modules decide
4. Products are instruments, not objectives
5. Reflection is mandatory feedback, not optional UX

If any are violated, the system collapses back into persuasive AI.

---

## Research Foundation

This implementation operationalizes:

- [The Empowerment Imperative](https://ai-news-hub.performics-labs.com/analysis/empowerment-imperative-agentic-marketing-human-flourishing) — The manifesto for agentic marketing that serves human flourishing
- **Computational Intentionality Theory (CIT)** — Framework treating AI advertising as a Turing-class machine whose objective function determines outcomes (paper forthcoming)

### Google Merchant Center

To load Merchant Center feeds locally set `CATALOG_SOURCE=google_merchant` and
point `GOOGLE_MERCHANT_FEED_PATH` to a JSON file containing feed entries (see
`data/google_merchant_feed.json` for a sample). Each entry must include the
standard Merchant Center fields (`id`, `title`, `description`, `price`,
`availability`, etc.). The adapter validates required fields and converts them
into canonical product representations with confidence metadata so downstream
agents know the data originates from aggregated discovery surfaces.
