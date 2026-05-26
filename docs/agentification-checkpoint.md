# Agentification Checkpoint

Status date: 2026-05-06

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
- External-agent job facade with idempotent create/status contracts through `POST /external-agent/jobs` and `GET /external-agent/jobs/{job_id}`, plus signed latest-status receipts and scoped linked-run event reads.
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
- Recovery proposals now apply capability-specific templates so proposed actions carry safer default inputs, source-action context, and template IDs.
- Interventions can now preflight, confirm, and create audited compensating proposals directly from those recommendations.
- Compensating proposal command construction and UI rendering are now reusable control-plane primitives instead of Interventions-only inline logic.
- Control-plane UX slices exist for Inbox, Runs, Interventions, and Learnings.
- Primary control-plane pages now use the flattened visual language from `docs/ui-style-direction.md`; `/lab` is retained as an advanced bench with matching surface primitives.
- `docs/operator-experience.md` is now the canonical operator/user guide, superseding the older lab-first guide in `docs/history/`.
- Mock-auth local/E2E mode allows authenticated frontend development without live Clerk state.
- Playwright smoke coverage verifies authenticated control-plane surfaces under mock auth.
- Agent runtime source has been reorganized into responsibility-based subpackages: `capabilities/`, `commands/`, `registry/`, and `runtime/`.
- Command routes now delegate command orchestration to `application/services/agent_runtime/commands/service.py`; architecture checks prevent command routes from re-importing low-level command internals.
- Cleanup guardrails now include tighter bloat caps for split backend surfaces and script-entrypoint checks for removed wrapper scripts.

## Current Architecture Interpretation

The platform is no longer only a simulation sandbox. It is currently best described as:

- an agent-assisted commerce optimization runtime
- a governed execution control plane
- a lab and validation system that agents can operate through policy-safe tools

The current implementation is still not a full OpenClaw-style autonomous assistant platform. It is becoming a governed substrate that such assistants could call into.

## Source Of Truth Documents

Use these docs together:

- `docs/agentification-checkpoint.md`: current checkpoint and next implementation tracks
- `docs/README.md`: documentation index and active/historical status map
- `docs/codebase-cleanup-and-modularisation-plan.md`: cleanup and modularisation sequence
- `docs/agent-first-modular-architecture-v1.md`: target architecture
- `docs/agent-capability-map.md`: narrative-to-agent/tool capability map
- `docs/external-agent-job-contracts.md`: machine-facing external-agent job API contract
- `docs/chat-led-operator-console-spec.md`: target human control-plane UX
- `docs/operator-experience.md`: current operator/user guide
- `docs/ui-control-plane-simplification-plan.md`: UI simplification roadmap
- `docs/agentic-layer.md`: runtime implementation notes

Historical reference:

- `docs/history/agent-first-migration-slice-rfc.md`: first migration slice; implemented and retained as rationale/history, not the active work plan

## Next Development Tracks

### 1. Skills And Tools Registry v1 Hardening

Current state: static in-code registry exposed through `GET /agent-runs/registry`, with each observed registry contract persisted as an immutable snapshot keyed by fingerprint. One registry snapshot is explicitly active; previous active snapshots are retired on fingerprint transitions. Tool ownership metadata is now seeded into a persistent registry ownership source and folded back into the registry payload so owner/steward changes can become auditable registry changes instead of hidden code-only metadata. Operators can update owner/steward metadata from the Runs control plane via `PATCH /agent-runs/registry/ownership/{tool_id}`; the endpoint supports dry-run preflight, requires confirmation before mutation, rejects no-op approvals, emits signed approval receipts, verifies approval receipts through `POST /agent-runs/registry/approval-receipts/verify`, and successful confirmed changes produce a new active registry fingerprint plus transition/approval audit events. Shared-tool skill selection is now deterministic: the registry exposes candidate skills and default skill per tool, while runtime action creation can honor an allowed/preferred skill when commands provide one. Recovery templates are now exposed in the runtime registry, and operator chat previews the selected recovery path before command submission. `GET /agent-runs/registry/releases` exposes active/retired release metadata, and `GET /agent-runs/registry/releases/{fingerprint}` exposes a persisted release payload plus related audit events for drill-down, including concrete release diff rows and operator-triggered receipt verification for signed ownership approvals. Registry fingerprint transitions create audit events with diff summaries so registry drift is explainable after deployment, and `GET /agent-runs/registry/audit` exposes that release trail to operators. `skill_id` lineage is stamped onto new actions and events. Registry specs now include summaries, input/output schema metadata, required receipt fields, owner/steward metadata, side-effect metadata, review checklists, and deterministic registry fingerprints. Runtime validates registry-declared input and output contracts around execution, including stable metric/variant/posterior receipt IDs where capabilities can guarantee them. The Runs UI uses registry metadata for selected-action explanations, new runs pin registry context, new actions pin registry/tool/skill/fingerprint context, and the Runs UI can preview/apply client-scoped backfill for missing pins on older records with audit events for applied backfills.

Remaining:

- No immediate registry-hardening blocker remains before the next platform slice.
- Future registry work should be incremental: richer schema semantics, registry migration tooling, and production-grade registry authoring workflows.

### 2. Agent Chat As Primary Control Interface

Current state: operator chat can explain, navigate execution context, preflight risky commands, issue audited steering commands, propose explicit retry actions, and create structured recovery proposals. Recovery proposals now carry capability-specific template context; external validation recovery defaults to `auto_run=false` so provider work is not duplicated before operator review. Runtime registry recovery templates are visible in operator chat as preview guidance before command submission. Compensating proposal controls now have shared command-builder and rendering primitives ready for reuse by other recovery surfaces.

Remaining:

- Reuse the shared compensating proposal control from additional recovery surfaces where compensating recommendations are shown.
- Continue reducing control-plane chat complexity only when active files start growing again.

### 3. External Agent API Contracts

Current state: machine-principal run creation exists, and the first external-agent job facade creates scoped, idempotent jobs linked to agent runs. External agents can read scoped job status, signed latest-status receipts, historical receipt lists, linked run events, and a normalized job activity projection. Protocol discovery and protocol readiness activity now expose receipt-backed `domain_summary` payloads for machine callers and operator supervision.

Next steps:

- Add richer domain-specific activity summaries beyond protocol readiness and discovery.
- Add scoped credentials for tool/skill access.
- Add retry-safe responses across more external-agent endpoints.

### 4. Harness Profiles

Current state: `harness_id` is now behavior-defining for run creation. Harness profiles are seeded into persistent registry tables, active persisted profiles are preferred over static defaults, agent profile IDs resolve to default harnesses, and run creation rejects harness/run-mode/policy mismatches before any plan is seeded. Harnesses also declare `allowed_effect_classes`; run creation rejects requested capabilities whose planned effect class is outside the harness boundary. This makes `observe_only` genuinely read/recommend-only while policy profiles still govern auto-execution and approval behavior. Planner mode now shapes initial planning: `inspect_and_recommend` keeps only read/recommend proposals, while `bounded_single_or_workflow` honors single-tool and max-initial-action objective constraints. Runtime stopping conditions now affect run status for the implemented conditions: `external_side_effect_required` pauses before pending external/high-risk actions, `budget_exhausted` pauses when action/variant/cost budgets are consumed, `policy_block` pauses when policy blocks an action, `recommendation_produced` completes observe/recommendation runs, `all_actions_completed` completes runs once all actions are executed or rejected, and `all_actions_decided` completes operator-supervised runs once all actions are approved or rejected. Memory policy is now enforced for `no_mutation`: learning/memory mutation capabilities such as `update_posterior_and_decisions` are rejected at plan creation and again before execution. Operators can update harness profiles through the guarded registry admin flow with dry-run preflight, confirmation, registry fingerprinting, and audit events.

Next steps:

- Persist agent-profile-to-harness default mappings after the profile model grows beyond the built-in defaults.
- Continue expanding memory policy coverage and remaining stopping conditions beyond the first enforced guards.

### 5. Protocol And Fallback Execution

Current state: ACP/UCP surfaces are still discovery/mock-heavy, but the first
read-only execution-adapter spine now exists. `check_protocol_readiness` runs
through `protocol.readiness.v1`, emits a structured adapter receipt, and pins
that receipt into run-event anchors for audit/replay. Execution adapters are
now registry-declared with channel type, permission scope, effect class,
side-effect posture, and allowed capabilities. `discover_protocol_candidates`
now runs through `protocol.discovery.v1`, returning read-only ACP/UCP candidate
discovery results with the same receipt/audit posture. UCP readiness now accepts
the current `2026-04-08` discovery profile shape alongside the older bundled
`2026-01-11` schema fixture, including service transports, capability registry,
payment handlers, signing keys, HTTPS endpoint checks, and structural validation
when no local current-version schema bundle is present. ACP readiness now tracks
the current `2026-04-17` beta surface for checkout capability negotiation,
payment handlers, and delegate-payment posture. UCP candidate discovery can now
use a guarded live `2026-04-08` REST Catalog Search path when a brand opts in
with `ucp.live_discovery` metadata and the merchant host is allowlisted; it
falls back to local metadata-backed discovery otherwise. ACP candidate discovery
can now use a guarded live product-feed path for opted-in brands, parsing
JSON/JSONL/CSV feed records, honoring search eligibility flags, and normalizing
records into read-only protocol candidates before falling back to local metadata.
Discovery candidates now expose `discovery_source`, and adapter receipts include
`source_counts` so live retrieval versus local fallback is auditable. Discovery
summaries and receipts now also include `readiness_summary`, a compact
market-research signal for ready, warning, and blocked candidates, protocol and
source mix, live versus local evidence, top blockers/warnings, and a 0-100
readiness score. The runtime
registry now also declares non-executable checkout, delegated-payment, and browser
fallback readiness boundaries as `status=planned`, `contract_intent=readiness_boundary`,
and no allowed executable capabilities. These contracts exist to support
merchant/protocol readiness intelligence, not real transactions. They publish the
required `external_write_execution` receipt contract as a guardrail for any
future implementation review, including approval linkage, idempotency, external
operation identifiers, request/response fingerprints, verification status,
adapter-specific evidence, and run-event linkage requirements.

Next steps:

- Extend concrete retrieval behind `protocol.discovery.v1` beyond the guarded
  UCP REST Catalog Search and ACP product-feed paths to additional protocol
  surfaces where real merchant endpoints are available.
- Keep checkout, payment, and browser fallback work in readiness-intelligence
  mode unless the product direction explicitly changes.
- Add bundled current-version UCP schema snapshots if strict offline validation
  is needed beyond the structural checks.
- Add browser/CLI fallback readiness probes only behind narrow permission
  policies.
- Require policy review for any external side effect.

### 6. Control-Plane UX Cleanup

Current state: control-plane pages exist and the primary loop now uses a flatter supervision style. Lab remains available as an advanced bench.

Next steps:

- Continue reducing older lab/admin route density where it creates real user confusion.
- Keep Inbox/Runs as the default path and Lab as an advanced workspace.
- Reduce duplicate dashboards and avoid reintroducing card-heavy layouts.
- Make all risky actions visible through Interventions.

## Completed Recent Build Slices

### Registry Hardening v1

Completed:

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
  - Registry-declared output schemas and required receipt fields are validated after capability execution, including stable `metric_id`, `variant_id`, and posterior `new_metric_id` receipts where available.
  - Invalid schema inputs are caught by runtime policy handling, mark the action/run failed, and preserve an auditable failure path.
  - Invalid output receipts mark the action/run failed before the malformed receipt is persisted as successful.
- Control-plane UI:
  - Agent Runs selected-action detail now prefers registry-provided summaries, side effects, and review checklists over hardcoded fallback explanations.
  - Agent Runs selected-action detail shows registry owner, steward, and ownership source metadata, with a gated ownership edit form and approval receipt confirmation for the selected tool.
  - Agent Runs release details can verify signed registry ownership approval receipts against the backend signature/audit verifier.
  - Agent Runs release details show concrete release diff rows for structural registry changes, pin backfills, and signed ownership approvals.
  - Agent Runs shows the active registry version and short fingerprint.
  - Interventions now uses shared compensating proposal command helpers and a reusable proposal control component for preflight, confirmation, and command issuance UI.
- Verification:
  - Backend tests cover registry metadata exposure and invalid registry input failure handling.
  - Frontend tests cover registry-driven action explanation and review checklist rendering.

### Cleanup And Backend Modularisation

Completed:

- Historical/human-led docs were moved under `docs/history/` and marked as non-current.
- Root script wrappers were removed after Makefile/docs/CI references moved to canonical script modules.
- Frontend control-plane surfaces were split into smaller components where it reduced active development friction.
- Backend agent-run routes were split by responsibility across registry, control, command, and read surfaces.
- Agent runtime internals were reorganized into package directories:
  - `application/services/agent_runtime/capabilities/`
  - `application/services/agent_runtime/commands/`
  - `application/services/agent_runtime/registry/`
  - `application/services/agent_runtime/runtime/`
- Command orchestration now lives in `application/services/agent_runtime/commands/service.py`, leaving command routes as HTTP adapters.
- Architecture and bloat guardrails now protect the new route/service boundaries.

### Harness Profiles v1

Completed:

- Runtime registry now exposes concrete harness profiles with planner mode, retry strategy, fallback order, approval strategy, memory policy, stopping conditions, default run mode, and default policy profile.
- Harness profiles are seeded into `agent_registry_harness_profiles`; registry payloads and fingerprints now prefer active persisted profiles while falling back to static defaults.
- Agent profile IDs now resolve to persisted default mappings during run creation; buyer-assistant external agents default to `safe_autonomy_b2b` unless an operator-persisted profile override says otherwise.
- Runtime registry payloads now expose `agent_profile_defaults`, and the active registry fingerprint includes these mappings alongside tools, skills, policy profiles, and harness profiles.
- Harnesses now enforce compatible `run_mode` and `policy_profile_id` combinations before a run/action plan is created.
- External-agent jobs inherit the authenticated agent profile's default harness when the caller does not specify one.
- Agent Runs shows the active harness posture beside the selected run's skills/tools contract.
- Retry and change-plan recovery commands now use harness retry/fallback posture when the operator does not explicitly choose a strategy.
- Backend harness profile edits are guarded by preflight, explicit confirmation, admin-only apply, registry release creation, and `registry_harness_profile_updated` audit events.
- Agent profile default edits are guarded by preflight, explicit confirmation, admin-only apply, registry release creation, and `registry_agent_profile_default_updated` audit events.
- Agent Runs exposes guarded editing for both the selected run's harness posture and active agent-profile default mapping.
- Agent profile default editing now includes risk tier and channel type so operators can inspect and adjust execution posture metadata from the Runs registry panel.
- Harness profile editing now covers the full execution posture exposed by the registry: name, description, default run mode, default policy, allowed modes/policies, planner mode, retry strategy, fallback order, approval strategy, memory policy, and stopping conditions.
- Agent Runs now lets operators save a local registry-write bearer credential, and frontend registry mutation helpers attach it only to protected registry apply calls.
- Guarded registry apply flows now show explicit risk/effect/confirmation posture, field-level change previews, rollback guidance, and applied audit/release metadata for harness and agent-profile updates.
- Backend tests cover harness defaulting, persisted agent-profile defaults, guarded profile edits, mismatch rejection, registry exposure, external-agent job inheritance, checkpoint retry defaulting, and fallback recovery selection.

## What Is Left To Build

### Priority 1: External Agent Job API Contracts

Goal: make external assistants first-class callers, not UI-shaped API consumers.

Build:

- Idempotent job creation and status APIs for external agents.
- Stable job ids, dedupe keys, retry-safe responses, and replay-safe error contracts.
- Scoped machine credentials for tool/skill access.
- Signed execution receipts for completed or failed work.
- Contract tests for duplicate submission, retry after timeout, and unauthorized tool access.

### Priority 2: Harness Profiles

Goal: continue hardening harnesses beyond the static v1 behavior-defining layer.

Build:

- Production token issuance/rotation UX for registry-write credentials, replacing local paste-in credentials with a managed operator flow.
- Signed receipt support for harness/profile posture approvals if these changes need the same cryptographic receipt treatment as ownership approvals.

### Priority 3: Real Protocol And Fallback Execution Adapters

Goal: let agents act through real commerce/protocol/tool surfaces, not only mocks and internal lab tools.

Build:

- Replace mock-first discovery behind the read-only protocol adapter spine with
  concrete ACP/UCP retrieval where available.
- Add strict schema snapshots for active UCP versions once the upstream schema
  set stabilizes enough for local offline validation.
- Add side-effecting protocol execution adapters only after governed approval
  and external-write receipts are in place.
- Narrow browser/CLI fallback adapters with explicit permission scopes.
- Policy review gates for all external side effects.
- Execution receipts that link provider/job/browser/CLI evidence back to run events.

### Priority 4: Control-Plane UX Simplification

Goal: make the product feel like an agent supervision cockpit, not a dense lab dashboard.

Build:

- Make Inbox/Runs the default operator path.
- Keep Lab as an advanced workspace.
- Reduce duplicate dashboards and overlapping navigation.
- Route all risky work through Interventions.
- Keep `docs/operator-experience.md` current as the concise control-plane user guide.

### Priority 5: Continued Source Hygiene

Goal: keep the codebase cheap for humans and coding agents to reason about.

Build:

- Continue splitting only active hotspots that slow current development.
- Keep docs index and checkpoint current after each PR.
- Remove obsolete docs when the active checkpoint fully supersedes them.
- Tighten bloat and architecture caps after each modularisation slice.
