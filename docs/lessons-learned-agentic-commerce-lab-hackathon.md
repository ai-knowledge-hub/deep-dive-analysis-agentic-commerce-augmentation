# From Assumptions to Signal

## Building an Agentic Commerce Lab in 3 Weeks

## The Problem

AI-mediated shopping changed how people ask for products. Queries now include goals, constraints, and context, not only keywords. Product teams need a way to test whether copy can better match those intent narratives.

Our initial hypothesis was simple:

> Better intent alignment in the lab should improve product discoverability in AI shopping surfaces.

The hard part was turning that into a system that is useful without pretending we can directly predict closed ranking models.

## What We Built

A validation-first lab with two connected workflows:

- **Manual workflow:** Chat → Alignment → Evidence → Simulation.
- **Lab workflow:** Hypothesis → Query battery → Variants → Runs → Metrics → Recommendations.

Core capabilities:

- Intent-aware simulation for product-copy testing.
- Query battery generation (top-down, bottom-up, hybrid).
- Variant testing and run history.
- Synthetic validation signal (LLM judge screening).
- Observed reality signal (manual validation logs).
- Canonical intent spec + normalization to stabilize bottom-up generation.
- Multi-tenant scope and history controls.
- Loop maintenance jobs for memory/belief maintenance.

## What We Changed During Build

We shipped iteratively and pivoted multiple times as assumptions failed.

### Pivot 1: From ranking claims to validation-first claims

We stopped framing outputs as ranking prediction and reframed the product as a lab for controlled discoverability testing plus validation.

### Pivot 2: From score certainty to robust signals

We reduced reliance on absolute synthetic scores and moved to more robust comparative signals and explicit validation status.

### Pivot 3: From free-form inputs to canonical context

Bottom-up generation quality improved only after we introduced canonical intent specs, gating, and rejection diagnostics.

### Pivot 4: From feature sprawl to workflow clarity

We reorganized UX around execution order and history utility so users can understand what happened and what to do next.

## Demo Flow (What Judges Can Evaluate Quickly)

1. Select tenant/product scope.
2. Generate query battery.
3. Create experiment and variants.
4. Run tests and inspect run history.
5. Review metrics and orchestrator recommendation.
6. Log synthetic and/or observed validation.
7. Show loop updates via history + maintenance controls.

This demonstrates end-to-end loop behavior, not isolated screens.

## Technical Moat

The moat is not one prompt. It is loop discipline:

- Structured intent context contract.
- Rejection-aware generation and acceptance metrics.
- Distinct synthetic vs observed validation channels.
- Tenant-scoped memory + history.
- Repeatable maintenance pipeline for belief/memory refresh.

## What We Learned

1. **Signal tiers matter:** synthetic and observed signals must be separated.
2. **Input quality dominates output quality:** canonical spec quality is foundational.
3. **UX order affects model outcomes:** bad flow causes bad experiments.
4. **Scope correctness is non-negotiable:** tenant isolation and state hygiene are core quality gates.
5. **Honesty improves product quality:** explicit uncertainty beats false precision.

## Current Limits

- We do not claim direct ranking control in external shopping systems.
- Observed validation is still partially manual.
- Full cross-platform attribution remains an open measurement problem.

## Why This Is a Good Hackathon Build

This project demonstrates more than model wiring:

- It operationalizes an emerging commerce problem.
- It includes real product decisions under uncertainty.
- It shows technical iteration with architecture and UX pivots.
- It balances ambition with defensible claims.

In short: we built a realistic agentic-commerce lab that learns in a loop and makes better decisions over time.
