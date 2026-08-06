# Documentation Index

Status: current
Last updated: 2026-08-03

Use this index to avoid treating historical planning notes as active product or architecture guidance.

## Current Docs

- `platform-modernisation-plan-v2.md`: canonical product, architecture, safety,
  and delivery plan for the chat-first dynamic-workflow migration.
- `agentification-checkpoint.md`: current execution checkpoint and next build tracks.
- `agent-first-modular-architecture-v1.md`: target agent-first architecture.
- `agent-capability-map.md`: narrative-to-agent/tool capability map for functionality and UX planning.
- `external-agent-job-contracts.md`: machine-facing external-agent job API contract.
- `codebase-cleanup-and-modularisation-plan.md`: completed cleanup sequence and
  ongoing source-modularisation reference; subordinate to the v2 plan.
- `agentic-layer.md`: current runtime implementation notes.
- `operator-experience.md`: current operator/user guide for the agentic control plane.
- `usability-simplification-gate.md`: product-language and progressive-disclosure gate for hiding internal complexity.
- `user-testing-plan.md`: practical usability testing plan for validating the control-plane loop before the next major platform slice.
- `ux-flow-schema.md`: compact schema of UX modes, routing, and operator/agent flow.
- `ui-control-plane-simplification-plan.md`: current UI simplification roadmap.
- `ui-style-direction.md`: visual style rules for the flattened control-plane UI.
- `decisions/README.md`: architecture decision record index, including the
  framework-neutral workflow, task, and delegation schema contract.

## Reference Docs

- `app-architecture.md`: backend/frontend architecture overview.
- `architecture-learning-loop.md`: learning-loop design reference.
- `external-integrations.md`: integration notes.
- `chat-led-operator-console-spec.md`: reference spec for chat-led control-plane interaction; use `operator-experience.md` and `agentification-checkpoint.md` for current implementation direction.
- `deployment.md`: deployment and environment guidance.
- `terminology.md`: glossary and naming conventions.
- `debug/incidents-fixed.md`: fixed incidents log.
- `debug/open-risks.md`: active risk log.

## Historical Docs

These may contain useful context, but should not be treated as the current implementation plan without checking `agentification-checkpoint.md` first.

- `history/README.md`: historical documentation index.
- `history/agent-first-migration-slice-rfc.md`: implemented migration-slice rationale.
- `history/app-workflows.md`: older workflow map with some still-useful API notes.
- `history/experiment-flow-detailed.md`: lab-era experiment flow detail.
- `history/user-guide-complete.md`: older human-led user guide, superseded by `operator-experience.md`.
- `history/pitch-deck.html`: presentation artifact, not engineering guidance.
