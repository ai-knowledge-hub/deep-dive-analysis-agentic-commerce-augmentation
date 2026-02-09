# Inspiration

LLM shopping changed how people ask for products. Queries are now goal- and context-rich, not just keyword strings.
We wanted to build a practical system for teams to test discoverability improvements without pretending lab scores are guaranteed production outcomes.

That led to **Intent Loop Commerce: LLM Discoverability Lab**: a validation-first loop for simulation, experimentation, and evidence-grounded iteration.

## What it does

Intent Loop Commerce helps teams optimize product copy for LLM-driven discovery by running a structured closed loop:

1. Build query batteries (`bottom_up`, `top_down`, `hybrid`).
2. Create and test copy variants in controlled experiments.
3. Review run outcomes and aggregate metrics.
4. Validate with two signals:
   - synthetic validation (in-app BYOK, provider run, manual fallback),
   - observed reality validation (manual observed checks).
5. Generate next variants from weighted loop evidence (`validation > experiment > simulation`).

The lab also supports cold-start variant generation and derives behavioral audience segments from recent session/analytics events to condition top-down/hybrid query generation.

## How we built it

- **Backend:** FastAPI service architecture with scoped repositories and loop orchestration.
- **Frontend:** Next.js + TypeScript with step-based UX for simulation, experiments, and validation.
- **Validation integration:** Provider-run orchestration (OpenAI MCP path implemented), callback verification, TTL, and replay protection.
- **Learning loop:** Beliefs, memory artifacts, calibration signals, and explicit evidence weighting.
- **Operational controls:** Multi-tenant admin setup, canonical intent spec, model gateway (BYOK), and history/audit surfaces.

## Challenges we ran into

- Avoiding overconfidence from synthetic metrics and keeping observed validation central.
- Making a complex, multi-step lab intuitive without requiring extensive onboarding.
- Balancing automation with user control in lab mode.
- Evolving quickly while keeping type and architecture consistency.
- Designing provider integration flows that are secure now and extensible later.

## Accomplishments that we're proud of

- Delivered an end-to-end experiment flow with explicit validation checkpoint.
- Implemented closed-loop variant generation and cold-start generation in the same UX.
- Added provider-run validation contracts with callback security controls.
- Improved UX hierarchy across core modules for clearer next actions.
- Added session-derived audience segment conditioning for query generation, plus fallback behavior when session data is sparse.
- Produced complete docs for workflows, user guidance, external integrations, and experiment deep dive.

## What we learned

1. Signal tiers matter: synthetic is screening, observed is grounding.
2. Workflow clarity materially affects experimentation quality.
3. Reliability controls (fallbacks, gating, provenance) build trust faster than aggressive claims.
4. Strong context contracts (canonical intent + audience data) are critical for better generation.
5. Iteration quality depends as much on UX and data plumbing as on model quality.

## What's next for Intent Loop Commerce: LLM Discoverability Lab

- Native session-data connectors (e.g., GA4/warehouse ingestion) for richer behavioral segmentation.
- Segment quality/drift analytics and automatic refresh policies.
- Complete Gemini provider-run execution path.
- Further automation in lab mode with explicit approval checkpoints.
- Unified outcome snapshoting across runs, metrics, and validation.
- Production hardening: scalability, observability, and governance/security controls.
