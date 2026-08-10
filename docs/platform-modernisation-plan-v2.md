# Platform Modernisation Plan v2

Status: canonical execution plan
Last updated: 2026-08-03

## Purpose

This document is the source of truth for moving the current agent-assisted
commerce platform to a chat-first, dynamically orchestrated, safety-governed
system. It reconciles the existing agentification, UX, learning-loop, and
cleanup plans into one delivery sequence.

The repository is not being treated as a greenfield rewrite. Existing domain
logic, governed execution, policy, audit, belief, and memory capabilities are
assets to preserve. Static orchestration, duplicated chat models, oversized
product surfaces, and implicit lifecycle rules are the primary areas to evolve.

## North Star

Build an agentic commerce-optimisation platform where a user states an outcome
in chat; the system turns it into a governed, durable, dynamically composed
workflow; delegates bounded work to specialist agents; updates scoped beliefs
and memory from evidence; and exposes risk, approvals, provenance, performance,
and recovery through a structured control plane.

The product has two intentional interaction modes:

1. **Chat** is the default workspace for goals, explanations, progress,
   recommendations, results, and proposed actions.
2. **Control plane** is the structured source of truth for runs,
   interventions, insights, audit, administration, and recovery.

Lab remains an advanced compatibility surface during migration. It is not the
target product shell.

## Verified Starting Point

Baseline verified on 2026-08-03:

- Python source: 316 files, approximately 48,724 lines.
- Frontend source: 185 TypeScript/TSX/CSS files, approximately 48,966 lines.
- FastAPI surface: 153 route handlers.
- Frontend: 16 application page routes.
- Data history: 42 SQLite migrations.
- Agent registry: 14 executable capabilities and 7 static skill
  specifications.
- Backend verification: 281 tests passed, 1 skipped.
- Frontend verification: 45 test files and 107 tests passed.
- ESLint: no warnings or errors.
- TypeScript: strict no-emit check passed.
- Architecture checks: no cycles or complexity violations.
- Production Next.js build: passed.

The complete frontend gate is:

```bash
make web-verify
```

The backend and repository gate is:

```bash
make lint
make arch-check
make bloat-check
make script-entrypoint-check
make test
```

## Current Capability Assessment

### Preserve and strengthen

- Pure domain logic under `domain/`.
- Application and infrastructure separation.
- Agent run, action, and immutable event persistence.
- Capability/tool contracts and registry fingerprints.
- Principal, profile, harness, policy, budget, and effect-class concepts.
- Approval, command preflight, retry, compensation, and receipt primitives.
- Run locks, action claims, heartbeat, and bounded worker ticks.
- Tenant-scoped world state, belief revisions, calibration, and memory
  artifacts.
- Inbox, Runs, Interventions, and Insights read-model concepts.
- Existing API and integration tests as compatibility protection.

### Evolve

- The static initial planner into a versioned workflow planner.
- The sequential action worker into a durable task scheduler.
- Static skill metadata into executable, versioned operational modules.
- Implicit status strings into central transition contracts.
- Separate Lab and operator chat implementations into one contextual
  conversation and command gateway.
- Page-owned data fetching into shared read models and workflow projections.
- SQLite deployment into either an explicitly constrained single-node beta or
  PostgreSQL plus a durable queue before concurrent multi-tenant execution.

### Retire only after parity

- Dashboard-first `/` experience.
- `New chat` routing into the advanced Lab.
- Canned-only operator chat.
- Legacy overview and lab workflows that become redundant after chat and
  control-plane parity.
- Compatibility fields and route shims after callers have migrated.

## Confirmed Architecture Gaps

### Chat

The repository currently has two different conversation models:

- product-discovery chat in Lab
- predefined operator prompts and command controls in Runs

There is no single free-form, execution-aware operator conversation. Chat is
therefore adjacent to the product rather than its primary shell.

### Workflow orchestration

The planner currently derives a fixed ordered action queue from allowed
capabilities. The worker claims and executes approved actions sequentially.

The runtime does not yet model:

- workflow nodes or dependency edges
- runtime-created tasks
- fan-out and join policies
- task attempts and checkpoint recovery
- parent/child agent assignments
- result aggregation
- workflow revision and bounded replanning

`root_run_id` and `parent_run_id` are persisted but are not yet used to execute
delegation.

### Skills and agents

Skills currently group tool identifiers and provide descriptive selection and
risk metadata. They are not executable workflow definitions. There is no
durable subagent lifecycle, isolated context capsule, delegated authority
contract, or worker result schema.

### State and safety

Run and action lifecycles are implemented across services using status strings
and conditional logic. The allowed transitions and safety constraints are not
defined in one enforceable domain contract. This is insufficient for parallel
execution, approvals, retries, timeouts, joins, and compensation.

## Target Runtime Model

The target execution path is:

```text
chat
  -> conversation and command gateway
  -> workflow planner
  -> policy and safety preflight
  -> durable workflow orchestrator
  -> task scheduler
  -> isolated specialist workers
  -> typed tools and domain modules
  -> evidence, belief, and governed memory updates
  -> workflow projections
  -> chat and control-plane views
```

The runtime is a coordinated set of state models, not one state machine:

| Entity | Required model |
| --- | --- |
| workflow | Event-sourced hierarchical lifecycle over a dynamic DAG |
| task | Durable finite-state machine with leases and terminal outcomes |
| task attempt | Append-only execution and retry record |
| agent assignment | Bounded worker lifecycle and authority envelope |
| action | Governed effect lifecycle with approval and compensation |
| approval | Independent requested/approved/rejected/expired lifecycle |
| belief | Versioned prior, evidence, posterior, and confidence state |
| memory artifact | Candidate, validated, promoted, contradicted, retired lifecycle |

Workflow edges support explicit `all`, `any`, and `quorum` joins. Cycles are
allowed only through named, budgeted controllers such as evaluator-optimizer or
observe-update-replan. Bayesian belief state remains separate from workflow
checkpoint state so replay stays deterministic.

## Safety Constraints

The architecture applies a system-theoretic control model: system safety is not
inferred from component reliability alone. Constraints and feedback must cover
the interactions between operator, orchestrator, policy, workers, tools,
external systems, memory, and operational management.

Initial non-negotiable constraints:

- A child agent cannot receive more authority than its parent.
- Retrieved or user-supplied content cannot grant permissions or alter policy.
- External writes require idempotency, a durable receipt, and reconciliation.
- Production publication requires policy authorization and the configured
  observed-evidence threshold.
- Memory promotion requires provenance, tenant scope, quality, support, and
  contradiction checks.
- Parallel workers return isolated results; only the coordinator commits shared
  state.
- Every loop has depth, action, time, cost, and token limits.
- Tenant, connector, and workflow failures are isolated by quotas and
  concurrency bulkheads.
- Every unsafe or failed action has an inspectable recovery or compensation
  path.

STPA work in Phase 1 will derive system losses, hazards, unsafe control actions,
causal scenarios, constraints, feedback requirements, and verification tests.

## Delivery Sequence

### Phase 0: Trustworthy baseline

Objectives:

- restore reproducible dependency installation
- make lint, TypeScript, tests, architecture checks, and production build green
- establish one command for frontend release verification
- capture the executable repository inventory
- make this document the canonical modernisation plan

Exit gate:

- `make web-verify` passes
- backend and repository gates pass
- current capability and risk inventory is recorded
- no product architecture work depends on an undocumented legacy plan

Status: completed on 2026-08-03.

### Phase 1: Contracts and safety model

Deliverables:

- workflow, task, attempt, delegation, approval, checkpoint, and result schemas
- central run/action/workflow transition contracts
- versioned event taxonomy and idempotency rules
- separation contract for execution state, conversation state, belief state,
  and memory state
- STPA control structure and first hazard analysis
- security threat model covering prompt injection, excessive agency, memory
  poisoning, inter-agent communication, cascading failure, and repudiation
- architecture decision record comparing an internal kernel, LangGraph-style
  graph execution, and Temporal-style durable execution against repository
  requirements

Exit gate:

- all allowed transitions are executable tests
- all initial unsafe control actions map to a preventative or detective control
- a framework decision can be made from a working vertical spike

### Phase 2: Chat-first vertical slice

Deliverables:

- `/` becomes the real conversation workspace
- one conversation and command gateway replaces the two chat models
- typed intents for explain, navigate, propose, approve, pause, retry, and cancel
- structured plan, progress, evidence, approval, and result artifacts in chat
- control-plane deep links remain visible and auditable
- one existing sequential agent run can be created and supervised end to end

Exit gate:

- an operator completes one commerce-optimisation objective without entering Lab
- every chat mutation maps to a visible command, preflight, and event receipt

### Phase 3: Durable workflow kernel

Deliverables:

- workflow runs, tasks, edges, attempts, checkpoints, commands, and projections
- pause/resume, retry, timeout, cancellation, recovery, and compensation
- crash recovery without repeating committed side effects
- existing agent runs/actions/events adapted as compatibility projections
- production persistence and queue topology decision implemented

Exit gate:

- a workflow resumes after forced process termination
- duplicate delivery cannot duplicate an external or internal committed effect

### Phase 4: Bounded parallel subagents

Deliverables:

- versioned specialist role templates
- isolated context capsules and result schemas
- authority non-expansion, optional narrowing, tool allowlists, budgets, and
  delegation depth
- dynamic fan-out and deterministic join policies
- coordinator validation before shared-state mutation
- read/recommend parallelism before write-capable delegation

Exit gate:

- independent tasks execute concurrently and recover independently
- synthesized results preserve complete provenance and tenant isolation

### Phase 5: Hardening and simplification

Deliverables:

- STPA, threat-model, red-team, chaos, replay, load, and tenant-isolation gates
- workflow and agent quality evaluations
- progressive reduction of oversized source hotspots
- chat/control-plane usability testing against the new product model
- retirement of duplicated Lab and legacy dashboard flows after parity

Exit gate:

- no open P0/P1 safety, security, recovery, or primary-loop usability finding

## Beta Scope

Included:

- chat-created governed workflows
- sequential and bounded parallel execution
- explanation, provenance, approval, pause, retry, cancel, and recovery
- belief updates and governed memory promotion
- automatic read-only and approved low-risk work

Excluded until a later release:

- autonomous production publishing
- checkout or payment execution
- unrestricted browser or CLI access
- recursive subagent spawning
- self-modifying policies or workflow definitions
- unreviewed memory promotion
- open-ended peer-to-peer agent messaging

## Change Strategy

Use vertical, reversible slices:

1. Define and test a contract.
2. Adapt the existing runtime behind it.
3. Add one end-to-end path.
4. Add projections for chat and the control plane.
5. Prove recovery, policy, tenancy, and observability.
6. Remove the superseded path only after parity.

Do not begin with a wholesale frontend or backend rewrite. The current runtime,
policy, event, registry, belief, and memory foundations should be evolved behind
stable contracts.

## Immediate Next Slice

Phase 1 begins with three small, reviewable changes:

1. Add a domain-level workflow lifecycle contract and transition tests.
2. Add the workflow/task/delegation schema ADR without choosing a framework.
3. Produce the first STPA control structure and unsafe-control-action table for
   `plan -> approve -> execute -> observe -> update belief`.

Progress:

- Slice 1 now has a framework-independent domain workflow lifecycle contract,
  including an exhaustive executable transition matrix and terminal-state
  invariants.
- Slice 2 now has an accepted logical schema ADR for workflows, immutable graph
  revisions, tasks, attempts, delegation, results, checkpoints, events, and the
  compatibility path from the current agent runtime. Framework and persistence
  choices remain intentionally deferred.

No dynamic planner, subagent, or chat redesign should land before these three
artifacts agree on state, authority, effects, and failure semantics.
