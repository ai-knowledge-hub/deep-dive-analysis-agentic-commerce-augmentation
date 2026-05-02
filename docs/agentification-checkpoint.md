# Agentification Checkpoint

Status date: 2026-04-30

This checkpoint is the working reference for the platform pivot from a primarily human-led experimentation lab into an agent-first commerce execution platform with a human control plane.

## Product Direction

The target product is a policy-governed commerce execution surface for a world where humans, teams, and external assistants delegate work to agents.

The platform should serve three actors as first-class users:

- `human`: supervises, steers, approves, and audits execution
- `internal_agent`: platform-owned automation that optimizes, validates, and learns
- `external_agent`: buyer, operator, or partner assistant acting through scoped credentials

The strategic stack is:

`principal -> agent profile -> harness -> skills -> tools -> policy -> execution receipts`

The human UI should become a control plane, not the primary execution engine. The lab remains valuable, but it should sit behind supervision, intervention, and explanation workflows.

## Completed Foundation

The codebase now has the minimum spine for the pivot:

- Principal-aware agent run creation with `principal_type`, `principal_id`, `agent_profile_id`, `harness_id`, `policy_profile_id`, `idempotency_key`, and `trace_id`.
- Machine-principal token resolution for scoped external-agent run creation.
- Agent run/action/event persistence with tool/effect metadata stamped onto proposed and executed work.
- Runtime policy profiles mapped from run modes: `human_approval_required`, `safe_auto`, and `observe`.
- Compatibility from legacy `capability_name` to machine-facing `tool_id`.
- Static skills registry v1 for initial commerce workflows.
- Static tools/capabilities registry v1 for executable runtime capabilities.
- Read API for the runtime registry: `GET /agent-runs/registry`.
- `skill_id` lineage now propagates from registry mapping into planned actions and agent events.
- Runs UI now surfaces the selected run's skills, tools, principal, policy profile, and trace context.
- Operator chat can issue audited steering commands for approve, reject, pause, start, non-mutating focus/explain intents, and structured change-plan recovery proposals.
- Chat-issued commands now have a policy preflight contract with risk level, blockers, warnings, side effects, and rollback guidance.
- Retry commands now create a new proposed retry action with incremented `retry_count` and preserve the original failed action.
- Command events are first-class timeline filters through `event_type=command` and the Agent Runs `Commands (24h)` preset.
- Interventions surfaces command-originated retry/recovery work.
- `change_plan` now creates a proposed recovery action instead of only recording a non-mutating receipt.
- Recovery commands can target a specific allowed capability instead of always falling back to the default recommendation action.
- Proposed recovery actions now persist side-effect metadata and rollback guidance for downstream approval review.
- Recovery proposals now include compensating-action recommendations for high-risk and external-side-effect paths.
- Interventions can now create audited compensating proposals directly from those recommendations.
- Control-plane UX slices exist for Inbox, Runs, Interventions, and Learnings.
- Mock-auth local/E2E mode allows authenticated frontend development without live Clerk state.
- Playwright smoke coverage verifies authenticated control-plane surfaces under mock auth.

## Current Architecture Interpretation

The platform is no longer only a simulation sandbox. It is currently best described as:

- an agent-assisted commerce optimization runtime
- a governed execution control plane
- a lab and validation system that agents can operate through policy-safe tools

The current implementation is still not a full OpenClaw-style autonomous assistant platform. It is becoming a governed substrate that such assistants could call into.

## Source Of Truth Documents

Use these docs together:

- `docs/agentification-checkpoint.md`: current checkpoint and next implementation tracks
- `docs/agent-first-modular-architecture-v1.md`: target architecture
- `docs/chat-led-operator-console-spec.md`: target human control-plane UX
- `docs/ui-control-plane-simplification-plan.md`: UI simplification roadmap
- `docs/agentic-layer.md`: runtime implementation notes

Historical reference:

- `docs/agent-first-migration-slice-rfc.md`: first migration slice; implemented and retained as rationale/history, not the active work plan

## Next Development Tracks

### 1. Skills And Tools Registry v1 Hardening

Current state: static in-code registry exposed through `GET /agent-runs/registry`, with `skill_id` lineage stamped onto new actions and events.

Next steps:

- Add a persistent registry table or versioned config store.
- Add schema validation for tool inputs and outputs.
- Add persistent registry ownership and richer skill selection when multiple skills can use the same tool.
- Add skill/tool version pinning onto runs and actions.
- Add registry diff/audit events when definitions change.

### 2. Agent Chat As Primary Control Interface

Current state: operator chat can explain, navigate execution context, preflight risky commands, issue audited steering commands, propose explicit retry actions, and create structured recovery proposals.

Next steps:

- Add richer recovery templates per capability/effect class as the registry becomes persistent/versioned.
- Add command preflight display before Interventions creates a compensating proposal.

### 3. External Agent API Contracts

Current state: machine-principal run creation exists.

Next steps:

- Define idempotent job APIs for external agents.
- Add dedupe keys and retry-safe responses across more endpoints.
- Add scoped credentials for tool/skill access.
- Add signed execution receipts for completed work.

### 4. Harness Profiles

Current state: `harness_id` is stored but not behavior-defining.

Next steps:

- Define harness profiles for planner mode, retries, fallback order, approval strategy, memory policy, and stopping conditions.
- Bind default harnesses to agent profiles.
- Show harness posture in Runs and Interventions.

### 5. Protocol And Fallback Execution

Current state: ACP/UCP surfaces are still discovery/mock-heavy.

Next steps:

- Replace protocol placeholders with concrete retrieval/execution adapters.
- Define browser/CLI fallback tools with narrow permissions.
- Require policy review for any external side effect.

### 6. Control-Plane UX Cleanup

Current state: control-plane pages exist but the lab is still visually and conceptually heavy.

Next steps:

- Make Inbox/Runs the default path.
- Keep Lab as an advanced workspace.
- Reduce duplicate dashboards.
- Make all risky actions visible through Interventions.

## Next Build Slice

The current implementation slice covers the first command observability and structured recovery pass.

Completed in this slice:

- Timeline observability:
  - `event_type=command` filtering for `operator_command_*`.
  - `Commands (24h)` timeline preset in Agent Runs.
- Interventions integration:
  - Surface command-originated retry/recovery work in Interventions.
  - Group command-originated work by urgency/risk.
- Structured recovery:
  - `change_plan` creates proposed recovery actions instead of only recording a non-mutating receipt.
  - Recovery target capabilities are validated by preflight against the run's allowed capabilities.
  - Proposed recovery actions carry persisted side effects and rollback guidance.
- Chat command controls:
  - Operator chat now exposes step and cancel commands through the same preflight path.
  - Operator chat exposes direct `change_plan` recovery proposal controls.
  - Command responses are summarized in the chat thread with resulting run/action state.
  - Command outcome summaries include artifact-specific inspection guidance for metrics, variants, validation jobs, copy revisions, hypotheses, snapshots, and failures.
- Retry strategies:
  - `same_action` retries the failed capability with copied inputs.
  - `last_safe_checkpoint` retries the failed capability with checkpoint intent stamped into inputs.
  - `create_recovery_action` creates a targeted recovery proposal, defaulting to `recommend_next_action` when available.
- Rollback guidance:
  - Recovery/retry proposals persist capability side effects and rollback guidance on the action row.
  - `action_recovery_proposed` and `action_retry_proposed` events carry rollback guidance in anchors for Interventions visibility.
  - Operator chat includes rollback guidance in command outcomes.
- Compensating actions:
  - Recovery/retry proposals can persist recommended compensating follow-ups.
  - External-side-effect proposals recommend `review_validation_readiness` when allowed.
  - High-risk proposals recommend readiness review and/or policy recommendation when allowed.
  - Interventions and operator chat surface the first compensating recommendation.
  - Interventions can create a compensating `change_plan` proposal through the audited command endpoint.
- Verification:
  - Backend tests for command event filtering and recovery action creation.
  - Frontend tests for command timeline preset and Interventions visibility.

Next build should deepen this slice:

- Add Interventions-side command preflight display before creating compensating proposals.
- Keep mock-auth Playwright smoke green.
