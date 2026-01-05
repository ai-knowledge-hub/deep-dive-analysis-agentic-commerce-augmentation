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
├── agents/                   # Façade agents (orchestration only)
├── attribution/              # AI-aware measurement scaffolding
├── evaluation/               # Representation A/B testing harness
├── api/                      # Thin FastAPI interface
├── demos/                    # Gemini/ChatGPT/Gradio demos
├── ui/                       # Demo UI components
├── data/                     # Empowerment catalog + fixtures
└── docs/                     # Architecture & design documentation
```

---

## Quick Start

```bash
# Validate imports and run stub runtime
python app.py
```

### Gradio Demo

```bash
cp .env.example .env   # configure CATALOG_SOURCE and credentials
uv venv venv && source venv/bin/activate
uv pip install -r requirements.txt
python -m demos.gradio.app
```

The interface surfaces clarifications/guardrails so you can see how data
confidence affects recommendations. Change `CATALOG_SOURCE` to switch between
mock, Shopify, Google Shopping, or Google Merchant feeds.

### FastAPI Surface

```bash
export CATALOG_SOURCE=google_merchant
export GOOGLE_MERCHANT_FEED_PATH=/absolute/path/to/google_merchant_feed.json  # required when using google_merchant
uvicorn api.main:app --reload --port 8000
```

Check `http://localhost:8000/products/search?query=workspace` to verify the feed.
If you don’t have Shopify or Google credentials/feeds yet, keep
`CATALOG_SOURCE=mock` so the API/Gradio demo can run with the bundled fixture.

### Gradio Demo

```bash
cp .env.example .env   # set CATALOG_SOURCE, Shopify/Google credentials as needed
uv venv venv && source venv/bin/activate
uv pip install -r requirements.txt
python -m demos.gradio.app
```

The UI displays clarifications and guardrail status so you can see how data quality
affects the empowerment objective. Switch `CATALOG_SOURCE` (mock, shopify,
google_shopping, google_merchant) via `.env` to test each feed.

### FastAPI Surface

```bash
export CATALOG_SOURCE=google_merchant
export GOOGLE_MERCHANT_FEED_PATH=/absolute/path/to/google_merchant_feed.json
uvicorn api.main:app --reload
```

Try `http://localhost:8000/products/search?query=workspace` to verify the feed.

### Catalog Sources

The platform loads products via adapters. Set `CATALOG_SOURCE` to choose the
source (`mock`, `shopify`, `google_shopping`). When using Shopify, provide
`SHOPIFY_DOMAIN` and `SHOPIFY_TOKEN` in your environment (see `.env.example`).

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
