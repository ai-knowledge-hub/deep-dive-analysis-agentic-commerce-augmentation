# Agent-First Modular Architecture v1

This document defines the next architecture step for the platform as it pivots from a primarily human-operated commerce lab into an agent-first execution fabric with a human control plane.

It is intentionally grounded in the current codebase, not a greenfield rewrite.

## Why This Pivot Exists

Today the product is strongest as a:

- human-led experimentation and validation lab
- governed operator workflow for agent-assisted execution
- simulation and learning environment for discoverability improvement

That is still valuable, but it is not the center of gravity of the agentic market anymore.

The target world is different:

- each human or team may have an external assistant operating on their behalf
- external agents will collaborate through protocols where possible
- external agents will fall back to tools, browser actions, CLI integrations, and explicit skills where protocols do not exist
- enterprise buyers will still demand governance, safety, auditability, and scoped autonomy

The platform therefore needs to become:

1. a machine-first commerce execution surface
2. a policy-governed agent runtime
3. a human control plane for supervision, intervention, and learning

## Design Principles

1. Keep the current operator runtime and control surfaces, but demote them from "primary product" to "control plane".
2. Treat external agents as first-class principals, not as disguised humans carrying `client_id`.
3. Separate reusable execution building blocks cleanly:
   - tools
   - skills
   - harnesses
   - policies
4. Make all side effects replay-safe, idempotent, and auditable.
5. Preserve strong human override for risky capabilities, but default low-risk work to safe automation.

## Current State Summary

The codebase already contains good starting points:

- request-scoped route/service composition
- a centralized capability runtime in `application/services/agent_runtime/`
- basic policy enforcement and execution budgets
- an emerging harness package in `application/agents/harness/`
- operator UI and agent-run event timelines

The main limitations are structural:

- identity is mostly `client_id` plus optional `user_id`
- run semantics are still operator-first and `plan_only` by default
- tool/capability boundaries are still narrow and app-internal
- skills are not first-class objects
- Layer 2 remains protocol-ready but mostly mock-first
- human UX exposes too much lab detail for an eventual control-plane role

## Target Model

The target stack should be:

`principal -> agent profile -> harness -> skills -> tools -> policy -> execution receipts`

### 1. Principals

A principal is the actor on whose authority a run executes.

Add a first-class principal model across runs, sessions, events, and actions:

- `principal_type`: `human`, `internal_agent`, `external_agent`
- `principal_id`
- `principal_org_id`
- `delegated_by_principal_id` (optional)
- `agent_profile_id` (optional)
- `auth_method`
- `scopes`

This replaces the current implicit model where tenancy mostly flows through `client_id`.

### 2. Agent Profiles

An agent profile is the stable description of an agent's operating posture.

Suggested fields:

- `id`
- `name`
- `owner_principal_id`
- `tenant_id`
- `default_harness_id`
- `policy_profile_id`
- `allowed_skill_ids`
- `allowed_tool_ids`
- `default_execution_mode`
- `risk_tier`
- `channel_type` (`api`, `protocol`, `browser`, `cli`, `internal`)

Examples:

- `acme-growth-optimizer`
- `external-buyer-assistant`
- `internal-validation-agent`

### 3. Harnesses

A harness defines the outer execution loop.

It is responsible for:

- planning
- decomposition
- retry strategy
- approval strategy
- escalation behavior
- fallback ordering
- memory/read-write rules
- stopping conditions

Harnesses should be explicit configuration objects, not buried in agent classes.

Suggested fields:

- `id`
- `name`
- `planner_mode`
- `retry_policy`
- `approval_mode`
- `max_concurrency`
- `tool_selection_strategy`
- `skill_selection_strategy`
- `failure_escalation_strategy`
- `memory_policy`
- `observation_policy`
- `trace_level`

Examples:

- `human_supervised_lab`
- `safe_autonomy_b2b`
- `external_agent_collab_first`
- `browser_fallback_executor`

### 4. Skills

A skill is a reusable operational playbook.

This should follow the OpenClaw idea closely, but adapted to enterprise commerce execution.

A skill is not a raw function. It is a bounded execution module with:

- purpose
- entry criteria
- required inputs
- allowed tools
- success criteria
- stopping conditions
- risk class
- approval expectations
- operator-facing explanation

Suggested `skill_spec` shape:

```yaml
id: optimize-product-representation
name: Optimize Product Representation
description: Improve product copy and structured representation for agentic retrieval surfaces.
version: v1
intent_tags:
  - optimization
  - discoverability
required_inputs:
  - product_id
  - brand_id
allowed_tools:
  - product.read
  - brand.read
  - representation.optimize
  - validation.request
  - evidence.ingest
risk_class: write_low_risk
approval_mode: policy_driven
success_criteria:
  - optimized copy produced
  - validation job submitted
  - result persisted to run artifacts
stop_conditions:
  - missing product context
  - policy block
  - validation provider unavailable
operator_summary_template: >
  Optimized representation for product {product_id} and requested validation.
```

Skills should live in versioned specs plus optional `SKILL.md` instructions where a model needs procedural guidance.

### 5. Tools

A tool is a narrow, typed effectful adapter.

Tools should be the only layer that touches side effects directly.

Examples:

- `catalog.search`
- `product.read`
- `brand.read`
- `validation.request`
- `validation.result.read`
- `simulation.run`
- `evidence.ingest`
- `protocol.acp.search`
- `protocol.ucp.search`
- `browser.open`
- `browser.extract`
- `cli.exec_scoped`

Suggested `tool_spec` shape:

```yaml
id: validation.request
version: v1
kind: internal_api
effect_class: write_low_risk
idempotent: true
requires_approval: policy_driven
input_schema: validation_request_v1
output_schema: validation_job_v1
auth_scope:
  - validation:write
policy_tags:
  - external_cost
  - async_job
receipts:
  - job_id
  - request_hash
  - tenant_id
```

Tool rules:

- narrow contract
- typed inputs/outputs
- idempotent where possible
- explicit auth scopes
- policy tags for risk and cost
- emit execution receipts

### 6. Policy Profiles

The current runtime policy model is a good base, but it should become profile-driven rather than mostly action-local.

Suggested policy profiles:

- `observe`
- `safe_auto`
- `full_auto_guarded`
- `human_approval_required`

Each profile should define:

- allowed effect classes
- approval thresholds
- cost budgets
- rate limits
- protocol trust posture
- browser/CLI fallback permissions
- escalation rules

This shifts the platform from:

- `plan_only` default

to:

- "what autonomy profile is this principal allowed to use?"

## Recommended Domain Model Changes

### New Core Tables

Add or introduce equivalents for:

- `principals`
- `agent_profiles`
- `harness_profiles`
- `skill_specs`
- `tool_specs`
- `policy_profiles`
- `execution_receipts`
- `principal_credentials`

### Existing Table Changes

Extend existing agent/runtime and conversation-oriented tables with:

- `principal_type`
- `principal_id`
- `agent_profile_id`
- `harness_id`
- `policy_profile_id`
- `idempotency_key`
- `request_id`
- `trace_id`
- `parent_run_id`
- `root_run_id`
- `delegation_depth`

For actions and events add:

- `tool_id`
- `skill_id`
- `effect_class`
- `approval_reason`
- `receipt_id`
- `retry_count`
- `dedupe_key`

For sessions/messages move away from a binary `speaker in ('user', 'agent')` assumption and support:

- `actor_type`
- `actor_id`
- `actor_role`

## API Contract Changes

The external API should become explicitly machine-oriented.

### Principles

- all mutating operations should be async
- all writes should accept idempotency keys
- all jobs should emit durable run/action/event ids
- callbacks and connector ingests should be signed and replay-safe

### Suggested External API Pattern

#### Start a run

`POST /v1/agent-runs`

Request:

```json
{
  "principal_token": "...",
  "agent_profile_id": "external-buyer-assistant",
  "harness_id": "safe_autonomy_b2b",
  "policy_profile_id": "safe_auto",
  "objective": {
    "type": "commerce_task",
    "goal": "find and evaluate ergonomic desk options"
  },
  "context": {
    "tenant_id": "acme",
    "brand_id": "brand_123"
  },
  "idempotency_key": "req_123"
}
```

Response:

```json
{
  "run_id": "run_123",
  "status": "accepted",
  "trace_id": "trace_123"
}
```

#### Poll run state

`GET /v1/agent-runs/{run_id}`

#### List actions/events

`GET /v1/agent-runs/{run_id}/events`

#### Approve blocked action

`POST /v1/agent-actions/{action_id}/decision`

#### Submit observed outcome

`POST /v1/observations`

This pattern maps naturally onto the existing agent runtime routes while making the caller an agent, not an operator UI.

## How Skills and Tools Map to the Current Codebase

This migration can be incremental.

### Keep and evolve

- `application/services/agent_runtime/runtime/service.py`
  - keep as the execution kernel
  - extend it to operate on tools and skills, not just current capability names

- `application/services/agent_runtime/policy.py`
  - keep as policy enforcement core
  - extend to policy profiles, effect classes, principal scopes, and approval thresholds

- `application/services/agent_runtime/registry/contracts.py`
  - evolve from capability registry into tool registry plus compatibility shims

- `application/agents/harness/`
  - expand into real harness definitions and execution strategies

- `api/routes/agent_runs.py`
  - keep as the first machine-facing surface
  - add versioned external contracts and principal auth

### Refactor or replace

- `application/agents/layer1_agent.py`
  - refactor into skill-backed orchestration modules
  - likely becomes a collection of `evidence.*` and `optimization.*` skills

- `application/agents/layer2_agent.py`
  - convert from mock-first placeholder into protocol skill layer plus protocol tools
  - separate discovery skill from transport/tool implementation

- `api/utils/tenancy.py`
  - replace parameter-trust tenancy with authenticated principal claims

- conversation-centric message assumptions
  - generalize actor model so external agents become first-class participants

## OpenClaw-Inspired Pieces Worth Adopting

The local OpenClaw codebase points to three ideas worth importing directly:

### 1. Skills as procedural operating modules

OpenClaw skills are not just metadata; they contain execution guidance, constraints, and workflow expectations.

We should adopt:

- `SKILL.md` as a durable operator/model instruction artifact
- explicit requirements and install prerequisites
- versioned, reviewable skill definitions

We should not adopt blindly:

- a personal-assistant-first surface model
- unconstrained tool growth without enterprise policy overlays

### 2. Control plane versus product separation

OpenClaw is right that the gateway is the control plane, not the product.

For this platform:

- the execution fabric is the product
- the web app becomes the operator control plane

### 3. Execution policy around system tools

OpenClaw's execution policy layering is a strong pattern for browser/CLI fallback.

We should adopt:

- explicit allowlists
- shell-wrapper scrutiny
- approval-on-miss behavior
- effect-based security classes

This will matter once agents use browsers, CLIs, and connector tools as real fallback paths.

## AutoHarness Direction

An AutoHarness-style direction is promising, but it should be sequenced carefully.

The correct order is:

1. formalize tool contracts
2. formalize skill specs
3. formalize harness profiles
4. collect execution traces and outcomes
5. evaluate harness variants offline
6. only then explore automatic harness synthesis or adaptation

Do not start with self-modifying harnesses in production.

The first implementation should be:

- human-authored harness profiles
- trace capture
- offline replay/evaluation
- scorecards for latency, success, safety, intervention rate, and cost

Then the platform can support:

- harness recommendation
- harness search
- bounded harness generation in sandboxed environments

## UX Simplification: Human Control Plane

If the machine surface becomes primary, the web app should simplify heavily.

Recommended top-level operator surfaces:

### 1. Inbox

What needs human attention right now:

- blocked approvals
- failed runs
- policy exceptions
- drift alerts
- stuck integrations

### 2. Runs

A clean timeline view:

- objective
- current state
- selected skills
- tool invocations
- approvals
- receipts
- outcomes

### 3. Interventions

Focused interface for:

- approve
- reject
- pause
- reroute harness
- downgrade autonomy profile
- retry with different skill/tool

### 4. Learnings

A compact view of:

- new evidence
- updated beliefs
- calibration shifts
- protocol coverage changes
- skill/harness performance trends

Everything else should become secondary tabs or advanced drill-downs.

The current lab UX is too dense to remain the default surface once operators are mainly supervising autonomous runs.

## Delivery Plan

### Phase 0: RFC and schema alignment

Deliverables:

- this architecture document
- principal model RFC
- tool/skill/harness schema RFCs
- policy profile taxonomy

### Phase 1: Identity and contracts

Deliverables:

- principal authentication
- scoped machine credentials
- idempotency keys on writes
- trace ids and receipts
- backward-compatible route shims

### Phase 2: Tool and skill modularization

Deliverables:

- tool registry v1
- skill registry v1
- first commerce skills
- compatibility layer from old capabilities to new tools/skills

### Phase 3: Safe autonomy

Deliverables:

- `safe_auto` default for approved profiles
- effect-class-aware policy engine
- exception-driven human intervention queue

### Phase 4: Protocol and fallback execution

Deliverables:

- real ACP/UCP connectors where available
- browser and CLI fallback tools with strict policy controls
- signed execution receipts

### Phase 5: Harness intelligence

Deliverables:

- harness analytics
- harness A/B evaluation
- offline replay and optimization
- bounded AutoHarness experimentation

## Concrete First Build Slice

If we want the smallest high-leverage slice, it should be:

1. introduce `principal_type`, `principal_id`, `agent_profile_id` on agent runs and events
2. add `policy_profile_id` and replace implicit `plan_only` posture with explicit autonomy profile
3. define `tool_spec` and convert current capability registry into a tool registry shim
4. define 3 to 5 initial `skill_spec`s for commerce workflows
5. simplify the web app into Inbox, Runs, Interventions, Learnings

Suggested first skills:

- `discover-protocol-candidates`
- `optimize-product-representation`
- `request-validation-and-ingest-result`
- `triage-failed-run`
- `run-safe-browser-fallback-check`

## Success Metrics

Track these as architecture KPIs:

- percent of runs completed without human intervention
- intervention rate by skill and policy profile
- mean time to safe completion
- protocol-first success rate versus browser/CLI fallback rate
- replay success rate under idempotent retry
- cost per successful run
- safety incident count by effect class

## Decision

The platform should pivot to an agent-first modular architecture built around:

- first-class principals
- machine auth
- tools as typed effectful adapters
- skills as reusable operational playbooks
- harnesses as explicit execution loops
- policy profiles as autonomy boundaries
- a simplified human control plane

This path keeps the strongest parts of the current system, adopts the right lessons from OpenClaw, and creates a safe path toward more autonomous and eventually AutoHarness-style operation.
