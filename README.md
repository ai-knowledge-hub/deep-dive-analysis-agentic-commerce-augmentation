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
