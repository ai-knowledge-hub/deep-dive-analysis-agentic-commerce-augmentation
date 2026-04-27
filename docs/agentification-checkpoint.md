# Agentification Checkpoint

Status date: 2026-04-26

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
- Runs UI now surfaces the selected run's skills, tools, principal, policy profile, and trace context.
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
- `docs/agent-first-migration-slice-rfc.md`: first migration slice; now mostly implemented
- `docs/chat-led-operator-console-spec.md`: target human control-plane UX
- `docs/ui-control-plane-simplification-plan.md`: UI simplification roadmap
- `docs/agentic-layer.md`: runtime implementation notes

## Next Development Tracks

### 1. Skills And Tools Registry v1 Hardening

Current state: static in-code registry exposed through `GET /agent-runs/registry`.

Next steps:

- Add a persistent registry table or versioned config store.
- Add schema validation for tool inputs and outputs.
- Add `skill_id` assignment when planners propose actions.
- Add skill/tool version pinning onto runs and actions.
- Add registry diff/audit events when definitions change.

### 2. Agent Chat As Primary Control Interface

Current state: operator chat can explain and navigate execution context.

Next steps:

- Add chat-issued steering commands: explain, focus, pause, approve, reject, retry, change plan.
- Keep commands routed through policy and existing action/run APIs.
- Add command receipts to event history.
- Add undo/rollback guidance where side effects cannot be reversed.

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

## Near-Term Recommendation

The next implementation slice should be `skill_id` propagation:

1. Map proposed actions to the skill that owns their tool.
2. Persist `skill_id` on `agent_actions` and `agent_events`.
3. Show skill lineage in Runs and Interventions.
4. Add tests that verify actions/events carry `tool_id`, `skill_id`, `effect_class`, and principal metadata.

That slice turns the registry from a visible catalog into a real execution lineage mechanism.
