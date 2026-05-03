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
- Static tools/capabilities registry v1 for executable runtime capabilities, with summaries, input/output schema metadata, required receipt fields, side-effect notes, owner/steward metadata, and operator review checklists.
- Persistent registry ownership source for tool owner/steward metadata, seeded from registry defaults and included in registry fingerprints.
- Operator-driven registry ownership updates through `PATCH /agent-runs/registry/ownership/{tool_id}`, producing a new auditable registry release when ownership changes.
- Read API for the runtime registry: `GET /agent-runs/registry`, including registry version, deterministic fingerprint metadata, and persisted registry snapshot metadata for drift detection.
- Read APIs for registry release management: `GET /agent-runs/registry/releases` for active/retired releases, `GET /agent-runs/registry/releases/{fingerprint}` for a persisted release payload plus related audit events, and `GET /agent-runs/registry/audit` for recent fingerprint transition events and diff summaries.
- Scoped historical registry-pin backfill: `POST /agent-runs/registry/backfill-pins`, with dry-run default, fills missing run/action registry pins for one client.
- Registry pin backfill application writes `registry_pin_backfill_applied` audit events with per-client matched/updated counts.
- Registry fingerprint transitions now create audit events with coarse diff summaries across skills, tools, capabilities, policy profiles, and tool-skill mappings.
- Runtime policy now validates registry-declared tool input types before execution, and runtime receipt checks validate registry-declared output types and required receipt fields after execution.
- Agent actions now pin `registry_version`, `registry_fingerprint`, `tool_version`, and `skill_version` so execution receipts remain interpretable after registry evolution.
- Agent runs now pin the active `registry_version` and `registry_fingerprint` at creation time so the whole run has a stable registry context before action planning.
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
- Interventions can now preflight, confirm, and create audited compensating proposals directly from those recommendations.
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

Current state: static in-code registry exposed through `GET /agent-runs/registry`, with each observed registry contract persisted as an immutable snapshot keyed by fingerprint. One registry snapshot is explicitly active; previous active snapshots are retired on fingerprint transitions. Tool ownership metadata is now seeded into a persistent registry ownership source and folded back into the registry payload so owner/steward changes can become auditable registry changes instead of hidden code-only metadata. Operators can update owner/steward metadata from the Runs control plane via `PATCH /agent-runs/registry/ownership/{tool_id}`; the endpoint supports dry-run preflight, requires confirmation before mutation, rejects no-op approvals, emits signed approval receipts, verifies approval receipts through `POST /agent-runs/registry/approval-receipts/verify`, and successful confirmed changes produce a new active registry fingerprint plus transition/approval audit events. Shared-tool skill selection is now deterministic: the registry exposes candidate skills and default skill per tool, while runtime action creation can honor an allowed/preferred skill when commands provide one. Operator chat recovery controls can now pass a preferred skill for shared-tool recovery and change-plan proposals. `GET /agent-runs/registry/releases` exposes active/retired release metadata, and `GET /agent-runs/registry/releases/{fingerprint}` exposes a persisted release payload plus related audit events for drill-down. Registry fingerprint transitions create audit events with diff summaries so registry drift is explainable after deployment, and `GET /agent-runs/registry/audit` exposes that release trail to operators. `skill_id` lineage is stamped onto new actions and events. Registry specs now include summaries, input/output schema metadata, required receipt fields, owner/steward metadata, side-effect metadata, review checklists, and deterministic registry fingerprints. Runtime validates registry-declared input and output contracts around execution, the Runs UI uses registry metadata for selected-action explanations, new runs pin registry context, new actions pin registry/tool/skill/fingerprint context, and the Runs UI can preview/apply client-scoped backfill for missing pins on older records with audit events for applied backfills.

Next steps:

- Expand required output receipt fields as more capabilities can guarantee stable IDs.
- Add an operator-facing receipt verifier panel before this becomes production-facing.

### 2. Agent Chat As Primary Control Interface

Current state: operator chat can explain, navigate execution context, preflight risky commands, issue audited steering commands, propose explicit retry actions, and create structured recovery proposals.

Next steps:

- Add richer recovery templates per capability/effect class as the registry becomes persistent/versioned.
- Consider promoting compensating recommendation creation into a reusable control-plane component.

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

## Current Build Slice

The current implementation slice is Registry Hardening v1.

Completed in this slice:

- Registry metadata:
  - Tool and capability specs now expose summaries, input schemas, output schemas, side effects, and operator review checklists.
  - Default tool inputs are reflected into schema metadata so operators and API clients can see defaulted fields.
  - Tool and capability specs now expose `owner_principal_id` and `steward_team`.
  - The registry endpoint now exposes `registry_version`, `registry_fingerprint`, and `registry_hash_algorithm` for deterministic drift detection.
- Version pinning:
  - New runs persist `registry_version` and `registry_fingerprint`.
  - New action proposals persist `registry_version`, `registry_fingerprint`, `tool_version`, and `skill_version`.
  - Agent Runs selected-action detail shows the pinned registry/tool/skill versions.
- Persistence:
  - The registry endpoint now records the current registry payload in `agent_registry_versions`, keyed by deterministic fingerprint.
  - Registry snapshots now use explicit active/retired release status instead of relying on latest-observed ordering.
  - Registry releases are available through a compact read endpoint and Agent Runs release inventory panel.
  - Registry release details expose the persisted payload and fingerprint-specific audit events for operator drill-down.
  - Tool owner/steward metadata is seeded into `agent_registry_tool_ownership` and returned from the registry payload with ownership source.
  - Tool owner/steward metadata can be updated through a scoped registry ownership endpoint; ownership updates require dry-run preflight plus explicit confirmation, reject no-op approvals, create a new registry release fingerprint, and persist signed approval receipts through the registry audit trail.
  - Registry payload exposes `skill_selection_by_tool` so shared tools have explicit candidate/default skill lineage.
  - Operator chat can choose a preferred skill for shared-tool recovery and change-plan proposals, passing that skill lineage into command-created actions.
  - Registry fingerprint changes create `agent_registry_audit_events` rows with diff summaries.
  - Historical run/action registry pins can be backfilled per client with dry-run preview from the Agent Runs registry panel, and applied backfills are recorded as registry audit events.
  - Agent Runs shows the active registry source, fingerprint, and recent registry release trail.
- Policy enforcement:
  - Registry-declared input schemas are validated before tool execution.
  - Registry-declared output schemas and required receipt fields are validated after capability execution.
  - Invalid schema inputs are caught by runtime policy handling, mark the action/run failed, and preserve an auditable failure path.
  - Invalid output receipts mark the action/run failed before the malformed receipt is persisted as successful.
- Control-plane UI:
  - Agent Runs selected-action detail now prefers registry-provided summaries, side effects, and review checklists over hardcoded fallback explanations.
  - Agent Runs selected-action detail shows registry owner, steward, and ownership source metadata, with a gated ownership edit form and approval receipt confirmation for the selected tool.
  - Agent Runs shows the active registry version and short fingerprint.
- Verification:
  - Backend tests cover registry metadata exposure and invalid registry input failure handling.
  - Frontend tests cover registry-driven action explanation and review checklist rendering.

## Next Build Slice

The next implementation slice should finish Registry Hardening v1 release management and ownership migration.

Initial scope:

- Expand required output receipt fields as more capabilities can guarantee stable IDs.
- Add an operator-facing receipt verifier panel.
- Keep mock-auth Playwright smoke green.
