# Agent-First Migration Slice RFC

Status: **Implemented as the first pivot foundation. Historical reference only.**

Implementation notes:
- Principal-aware agent run creation is implemented.
- Machine-principal token resolution is implemented for run creation.
- Runtime actions/events carry `tool_id`, effect class, and principal metadata.
- Initial static skill specs are implemented.
- The runtime registry is exposed through `GET /agent-runs/registry`.
- The Runs UI surfaces skills/tools for the selected run.

For the current checkpoint and follow-up tracks, see [docs/agentification-checkpoint.md](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/docs/agentification-checkpoint.md).

Do not use this RFC as the active backlog. It is retained to explain why the first agent-first data/runtime slice was shaped the way it was.

This RFC defines the first implementation slice for the agent-first modular architecture described in [docs/agent-first-modular-architecture-v1.md](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/docs/agent-first-modular-architecture-v1.md).

The goal of this slice is not to complete the pivot. The goal is to introduce the minimum structural changes that unblock the pivot safely.

## Scope

This slice covers four things:

1. first-class execution identity on agent runtime records
2. explicit autonomy posture via policy profiles
3. a compatibility path from today's capability registry to a future tool registry
4. the first skill specifications for commerce execution

This slice is intentionally additive and backward-compatible.

## Why This Slice First

The current system already has a strong runtime core:

- `agent_runs`
- `agent_actions`
- `agent_events`
- policy enforcement
- execution locks and heartbeats

What it does not yet have is a stable way to answer:

- who is acting?
- under what authority?
- with what autonomy profile?
- using which reusable operational module?

Without those answers, the rest of the agent-first architecture will stay conceptual.

## Current Baseline

The current persistence layer gives us:

- tenant scope on `agent_runs.client_id`
- optional human linkage through `user_id` in route payloads
- app-internal capability execution through the runtime registry
- binary conversation turns with `speaker in ('user', 'agent')`

Relevant files:

- [shared/db/migrations/023_agent_runtime.sql](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/shared/db/migrations/023_agent_runtime.sql)
- [shared/db/migrations/026_agent_events.sql](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/shared/db/migrations/026_agent_events.sql)
- [shared/db/schema.sql](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/shared/db/schema.sql)
- [api/routes/agent_runs.py](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/api/routes/agent_runs.py)
- [application/services/agent_runtime/runtime.py](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/application/services/agent_runtime/runtime.py)
- [application/services/agent_runtime/policy.py](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/application/services/agent_runtime/policy.py)

## Slice Goals

By the end of this slice, the platform should be able to:

1. persist the acting principal on runs, actions, and events
2. distinguish a human operator from an internal agent or external agent
3. record the policy profile governing a run
4. attach an agent profile and harness id to a run
5. begin mapping current capabilities into future tool ids
6. define a small stable set of initial `skill_spec`s

## Decision Summary

### We will add

- `principal_type`
- `principal_id`
- `agent_profile_id`
- `harness_id`
- `policy_profile_id`
- `tool_id`
- `skill_id`
- `effect_class`
- `idempotency_key`
- `trace_id`

### We will not do in this slice

- full machine auth rollout
- full protocol transport implementation
- browser and CLI tool execution
- generalized actor migration for all conversation/session tables
- removal of `client_id`-based scoping

Those remain follow-up phases.

## Data Model Changes

### 1. New lookup tables

Introduce these new tables:

#### `principals`

Purpose:

- canonical actor identity for humans and agents

Suggested columns:

- `id TEXT PRIMARY KEY`
- `principal_type TEXT NOT NULL CHECK (principal_type IN ('human', 'internal_agent', 'external_agent'))`
- `tenant_id TEXT`
- `display_name TEXT`
- `status TEXT NOT NULL DEFAULT 'active'`
- `metadata_json TEXT`
- `created_at TEXT DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT DEFAULT CURRENT_TIMESTAMP`

#### `agent_profiles`

Purpose:

- stable operating identity and default execution posture for an agent

Suggested columns:

- `id TEXT PRIMARY KEY`
- `principal_id TEXT NOT NULL`
- `tenant_id TEXT`
- `name TEXT NOT NULL`
- `default_harness_id TEXT`
- `default_policy_profile_id TEXT`
- `risk_tier TEXT`
- `channel_type TEXT`
- `metadata_json TEXT`
- `created_at TEXT DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT DEFAULT CURRENT_TIMESTAMP`

#### `policy_profiles`

Purpose:

- explicit autonomy posture reused across runs

Suggested columns:

- `id TEXT PRIMARY KEY`
- `name TEXT NOT NULL`
- `effect_classes_json TEXT NOT NULL`
- `approval_rules_json TEXT NOT NULL`
- `budget_defaults_json TEXT NOT NULL`
- `fallback_rules_json TEXT`
- `metadata_json TEXT`
- `created_at TEXT DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT DEFAULT CURRENT_TIMESTAMP`

These tables can be introduced without affecting current app behavior.

### 2. Extend `agent_runs`

Add:

- `principal_type TEXT`
- `principal_id TEXT`
- `agent_profile_id TEXT`
- `harness_id TEXT`
- `policy_profile_id TEXT`
- `idempotency_key TEXT`
- `trace_id TEXT`
- `root_run_id TEXT`
- `parent_run_id TEXT`

Notes:

- keep existing `client_id` as the tenancy anchor in this slice
- `run_mode` remains for compatibility
- `policy_profile_id` becomes the future source of truth for autonomy posture

Recommended backfill:

- `principal_type = 'human'` for all existing runs
- `principal_id = user_id` when known at route level; otherwise a generated tenant operator principal can be used later
- `policy_profile_id = 'human_approval_required'` for existing runs

### 3. Extend `agent_actions`

Add:

- `tool_id TEXT`
- `skill_id TEXT`
- `effect_class TEXT`
- `receipt_id TEXT`
- `retry_count INTEGER DEFAULT 0`
- `dedupe_key TEXT`

Notes:

- `capability_name` remains in place for compatibility
- in this slice, `tool_id` will be a shimmed translation from `capability_name`

### 4. Extend `agent_events`

Add:

- `principal_type TEXT`
- `principal_id TEXT`
- `tool_id TEXT`
- `skill_id TEXT`
- `effect_class TEXT`
- `trace_id TEXT`

This lets the event stream evolve from operator lifecycle logging into a true multi-actor execution audit trail.

### 5. Conversation actor model

Do not migrate conversation tables fully in this slice.

Instead, record the follow-up requirement:

- `turns.speaker` is too narrow for an agent-first platform
- future migration should introduce `actor_type`, `actor_id`, and `actor_role`

For now, keep conversation compatibility intact.

## API Contract Changes

### `POST /agent-runs`

Extend request shape with optional fields:

```json
{
  "principal_type": "external_agent",
  "principal_id": "principal_ext_assistant_123",
  "agent_profile_id": "external-buyer-assistant",
  "harness_id": "safe_autonomy_b2b",
  "policy_profile_id": "safe_auto",
  "idempotency_key": "req_123"
}
```

Compatibility rules:

- if omitted, preserve current behavior
- default `principal_type` to `human`
- default `policy_profile_id` from `run_mode`

Suggested mapping:

- `plan_only` -> `human_approval_required`
- `auto_execute_safe` -> `safe_auto`

### Route behavior in this slice

Keep existing route shapes and validation patterns, but:

- persist the new identity and policy fields
- stamp `trace_id` on run creation
- carry principal metadata into action and event creation

## Runtime and Registry Changes

### Capability registry compatibility shim

Do not replace the current capability registry yet.

Instead, add a translation layer:

- existing `capability_name` remains executable
- runtime resolves `tool_id` from `capability_name`
- policy engine can begin evaluating both fields

Suggested initial mapping examples:

- `run_variant` -> `experiment.run_variant`
- `request_validation` -> `validation.request`
- `publish_copy_revision` -> `copy.publish_revision`

This allows the system to evolve toward a tool registry without breaking existing tests and route logic.

### Policy engine changes

Extend `PolicyEnforcer` inputs to understand:

- `policy_profile_id`
- `principal_type`
- `tool_id`
- `effect_class`

In this slice, policy evaluation may continue to rely primarily on existing capability allow-lists and budgets, but it should start accepting effect classes and policy profile metadata.

## Initial Skill Set

The first skill set should be small and tightly tied to existing workflows.

### Skill 1: `discover-protocol-candidates`

Purpose:

- find ACP/UCP-ready product candidates or identify missing protocol fields

Likely tool dependencies:

- `catalog.search`
- `protocol.acp.search`
- `protocol.ucp.search`
- `product.read`

Maps to today:

- Layer 2 discovery and protocol readiness logic

### Skill 2: `optimize-product-representation`

Purpose:

- improve product representation for discoverability and downstream retrieval

Likely tool dependencies:

- `product.read`
- `brand.read`
- `representation.optimize`
- `copy.revise_draft`

Maps to today:

- optimization and evidence-backed representation work

### Skill 3: `request-validation-and-ingest-result`

Purpose:

- trigger validation, wait for completion, and ingest results into the learning loop

Likely tool dependencies:

- `validation.request`
- `validation.result.read`
- `evidence.ingest`

Maps to today:

- validation service plus evidence flow

### Skill 4: `triage-failed-run`

Purpose:

- inspect a blocked or failed run and recommend or apply the safest recovery path

Likely tool dependencies:

- `run.read`
- `event.read`
- `policy.inspect`
- `run.retry_safe`

Maps to today:

- operator investigation that is currently manual

### Skill 5: `run-safe-browser-fallback-check`

Purpose:

- verify critical platform state when protocol or internal APIs are insufficient

Likely tool dependencies:

- `browser.open`
- `browser.extract`
- `browser.assert`

Maps to today:

- future fallback path, not immediate implementation

## Example Migration Plan

### Migration A: add core identity and policy tables

Create:

- `principals`
- `agent_profiles`
- `policy_profiles`

Seed:

- `human_approval_required`
- `safe_auto`
- `observe`

### Migration B: extend runtime tables

Alter:

- `agent_runs`
- `agent_actions`
- `agent_events`

Backfill:

- `principal_type = 'human'`
- `policy_profile_id = 'human_approval_required'` where null

### Migration C: repository and port updates

Update:

- [application/ports/deps.py](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/application/ports/deps.py)
- runtime repositories under `infrastructure/db/agent/`
- route request/response models in [api/routes/agent_runs.py](/Users/dessigeorgieva/Desktop/projects/deep-dive-analysis-agentic-commerce-augmentation/api/routes/agent_runs.py)

### Migration D: tool-registry shim

Add:

- capability-to-tool translation helper
- `tool_id` stamping in actions/events

### Migration E: seed initial skill specs

Add:

- initial `skill_spec` store or static registry
- 3 to 5 seed skill definitions for commerce flows

## Out of Scope Risks to Watch

These are not blockers for this slice, but they should remain visible:

1. `client_id` is still the effective trust root in many routes.
2. Conversation/session persistence still assumes a human-chat model.
3. Existing UI still reflects lab complexity instead of control-plane simplicity.
4. Real machine auth and credential scoping remain future work.
5. Protocol execution is still discovery-heavy and transport-light.

## Acceptance Criteria

This slice is complete when:

1. a run can be created with `principal_type`, `principal_id`, `agent_profile_id`, `harness_id`, and `policy_profile_id`
2. those fields persist and appear in run detail responses
3. created actions and events carry `tool_id` and principal metadata
4. old callers continue to work without supplying the new fields
5. at least 3 initial skill specs are defined in code or seed data
6. tests cover compatibility and new-field persistence

## Recommended Implementation Order

1. add DB migrations for principals, policy profiles, and runtime table extensions
2. update repositories and dependency protocols
3. extend `AgentRunCreateRequest` and route handlers
4. add capability-to-tool translation shim
5. seed policy profiles and initial skill specs
6. add targeted tests for creation, listing, and event stamping

## Proposed Follow-Up RFCs

After this slice, the next RFCs should be:

1. machine authentication and scoped credentials
2. skill registry and `SKILL.md` execution model
3. harness profile execution model
4. operator control-plane UX simplification
5. protocol transport and browser/CLI fallback policy

## Recommendation

Approve this slice as the first implementation milestone for the pivot.

It is small enough to ship safely, but foundational enough that the rest of the agent-first architecture can build on it without rework.
