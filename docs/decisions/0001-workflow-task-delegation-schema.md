# ADR 0001: Workflow, Task, and Delegation Schema

Status: accepted for the Phase 1 contract; persistence implementation deferred
Date: 2026-08-06
Owners: platform architecture and agent runtime

## Context

The current runtime persists `agent_runs`, ordered `agent_actions`, and
append-only `agent_events`. It supports policy checks, approvals, locks,
heartbeats, retries, receipts, registry pins, and operator commands. It does
not yet represent a dynamic workflow graph, independently retryable tasks,
task attempts, joins, checkpoints, or bounded agent assignments.

`agent_runs.root_run_id` and `agent_runs.parent_run_id` express lineage but do
not provide delegation semantics. `agent_actions.sequence` creates a fixed
queue, but it cannot represent dependencies, fan-out, joins, or runtime graph
revision. Status changes are also distributed across services.

Phase 1 needs a logical schema that defines these concepts before the platform
selects an internal, LangGraph-style, or Temporal-style execution engine. This
ADR defines the portable contract. It does not add database tables or choose a
workflow framework.

The workflow lifecycle is governed by
`domain/workflow/lifecycle.py`. The schema below must not permit adapters to
bypass that transition contract.

The approval lifecycle and canonical authorization fingerprint are governed by
`domain/workflow/approval.py` and
`domain/workflow/approval_serialization.py`. Database rows, events, APIs, and
framework adapters are projections of that domain contract; they do not define
alternate approval semantics.

## Decision

Adopt a framework-neutral, event-sourced workflow model with relational
projections. The canonical execution hierarchy is:

```text
workflow
  -> immutable graph revision
  -> task
  -> task attempt
  -> optional agent assignment
  -> typed result and governed action references
```

The following distinctions are mandatory:

- A **workflow** owns the objective, lifecycle, graph revisions, policy pins,
  and aggregate budgets.
- A **task** is a schedulable unit of work in a workflow graph.
- A **task attempt** is one leased execution of a task. Retries append attempts
  rather than overwriting execution history.
- An **agent assignment** is a bounded delegation of one task with
  non-expanding authority, isolated context, and an explicit result contract.
- An **action** remains a governed effect. A task may propose or execute an
  action, but task status never substitutes for action approval or receipt
  state.
- A **workflow event** is the append-only source of lifecycle truth.
  Relational rows are query and scheduling projections rebuilt from events.

## Aggregate and identity rules

Every durable record carries `tenant_id`. Identifiers are opaque strings; the
logical contract does not require UUID, ULID, or database-generated keys.

Every workflow carries:

- `root_workflow_id` for the top-level objective
- `parent_workflow_id` when a child workflow is explicitly created
- `principal_id` for the authority under which it operates
- an immutable `authority_envelope` and canonical `authority_hash`
- `trace_id` for cross-service correlation
- `registry_version` and `registry_fingerprint` for reproducibility
- `policy_profile_id`, `harness_id`, and `agent_profile_id` pins
- a tenant-scoped `idempotency_key` and immutable request hash

Child workflows and assignments cannot change tenant or root workflow. A
delegated principal cannot gain authority through hierarchy creation. A root
workflow envelope is the intersection of principal scopes, agent-profile
allowlists, harness limits, policy limits, and registry-declared tool/effect
constraints. A child workflow envelope must be a subset-or-equal set of its
parent workflow envelope and, when created by an assignment, that assignment
envelope. Its budget must be component-wise no greater than the parent's
unreserved remaining budget. The canonical hashes make the authority checks
replayable.

## Logical records

The types below are logical contracts. Concrete SQL types and payload-storage
thresholds are deferred to the persistence decision.

### `workflow_runs`

| Field | Contract |
| --- | --- |
| `id` | Stable workflow identity. |
| `tenant_id` | Mandatory isolation boundary. |
| `root_workflow_id` | Self for roots; inherited by descendants. |
| `parent_workflow_id` | Nullable direct parent. |
| `objective` | Typed objective payload or immutable payload reference. |
| `objective_hash` | Canonical hash used for replay and idempotency. |
| `status` | Value from the domain `WorkflowStatus` contract. |
| `active_revision` | Current immutable graph revision number. |
| `principal_id` | Principal whose authority governs execution. |
| `authority_envelope` | Immutable skills, tools, effects, resources, scopes, and delegation limits. |
| `authority_hash` | Canonical hash of the authority envelope. |
| `agent_profile_id` | Optional pinned operating profile. |
| `harness_id` | Pinned execution-loop policy. |
| `policy_profile_id` | Pinned effect and approval policy. |
| `registry_version` | Pinned registry version. |
| `registry_fingerprint` | Pinned registry content hash. |
| `budget_envelope` | Time, cost, token, action, depth, and concurrency limits. |
| `idempotency_key` | Unique with tenant and principal. |
| `request_hash` | Detects conflicting reuse of an idempotency key. |
| `trace_id` | End-to-end correlation identifier. |
| `conversation_id` | Optional reference only; conversation is not execution state. |
| `version` | Optimistic concurrency version. |
| `created_at`, `updated_at`, `terminal_at` | Lifecycle timestamps. |

Required uniqueness:

- `(tenant_id, principal_id, idempotency_key)`
- `(tenant_id, id)`

### `workflow_revisions`

A workflow graph is never edited in place. Planning or bounded replanning
appends a revision.

| Field | Contract |
| --- | --- |
| `workflow_id`, `tenant_id` | Owning aggregate. |
| `revision` | Monotonic integer unique within the workflow. |
| `parent_revision` | Previous revision, if any. |
| `reason` | Initial plan, operator change, recovery, or bounded replan. |
| `planner_contract_version` | Planner input/output contract pin. |
| `graph_hash` | Canonical hash of tasks, edges, joins, and controllers. |
| `created_by_principal_id` | Human or agent responsible for the revision. |
| `created_event_id` | Event that committed the revision. |
| `created_at` | Commit timestamp. |

Tasks already executing retain their original revision. New scheduling reads
the active revision. A revision cannot remove evidence of previously scheduled
or completed work.

### `workflow_tasks`

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id` | Stable task identity and scope. |
| `introduced_in_revision` | First graph revision containing the task. |
| `task_key` | Planner-stable key unique within a workflow. |
| `parent_task_id` | Optional decomposition lineage. |
| `task_type` | Typed handler or coordinator contract identifier. |
| `status` | Task lifecycle value defined by the later task-state contract. |
| `effect_class` | `read`, `recommend`, or governed write class. |
| `skill_id`, `skill_version` | Optional skill contract pin. |
| `tool_id`, `tool_version` | Optional tool contract pin. |
| `input_ref`, `input_hash` | Immutable task input or reference. |
| `result_schema_id`, `result_schema_version` | Required output contract. |
| `approval_requirement` | Policy-derived requirement reference, not approval state. |
| `retry_policy` | Maximum attempts, backoff, and retryable error classes. |
| `timeout_policy` | Schedule-to-start and execution limits. |
| `priority` | Scheduler hint within tenant quotas. |
| `not_before`, `deadline_at` | Optional scheduling boundaries. |
| `version` | Optimistic concurrency version. |
| `created_at`, `updated_at`, `terminal_at` | Lifecycle timestamps. |

Tasks are not reused across workflows. Replanning may supersede an unstarted
task, but cannot delete it or rewrite its attempts.

### `workflow_revision_tasks`

Each revision stores a complete task-membership snapshot. The scheduler derives
the active task set only from rows for `workflow_runs.active_revision`; it does
not infer membership from task creation time.

| Field | Contract |
| --- | --- |
| `tenant_id`, `workflow_id`, `revision`, `task_id` | Revision-scoped membership identity. |
| `disposition` | `active`, `removed`, or `superseded`. |
| `superseded_by_task_id` | Required when disposition is `superseded`. |
| `reason` | Planner, operator, policy, or recovery explanation for a change. |
| `recorded_event_id` | Event that committed this membership decision. |

Every task known to the workflow has one membership row in every later
revision. Retained tasks remain `active`; newly added tasks enter as `active`;
removed unstarted tasks are `removed`; replacement records use `superseded`
and point to the new task. Started or terminal tasks cannot be removed or
superseded, and remain present for dependency and provenance evaluation. The
unique key is `(tenant_id, workflow_id, revision, task_id)`.

### `workflow_edges`

| Field | Contract |
| --- | --- |
| `tenant_id`, `workflow_id`, `revision` | Graph scope. |
| `from_task_id`, `to_task_id` | Dependency direction. |
| `condition` | Typed predicate over predecessor terminal results. |
| `join_group_id` | Groups incoming edges for one join decision. |
| `join_policy` | `all`, `any`, or `quorum`. |
| `quorum` | Required only for a quorum join. |

Ordinary graph revisions are acyclic. A cycle is valid only through a named,
budgeted controller task whose contract defines iteration limits, stopping
conditions, and the checkpoint boundary.

### `task_attempts`

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id`, `task_id` | Attempt identity and scope. |
| `attempt_number` | Monotonic and unique per task. |
| `status` | Append-only attempt lifecycle projection. |
| `worker_id` | Worker that owns the current or historical lease. |
| `lease_token_hash` | Hash of the active lease token; never expose the token. |
| `lease_acquired_at`, `lease_expires_at`, `heartbeat_at` | Lease evidence. |
| `input_hash` | Must match the task input used for this attempt. |
| `result_id` | Typed result reference after success. |
| `action_id` | Optional governed action produced or executed. |
| `receipt_id` | Optional committed-effect receipt. |
| `error_code`, `error_detail_ref` | Normalized failure information. |
| `started_at`, `finished_at` | Attempt timing. |

Only one unexpired attempt lease may exist per task. A retry creates the next
attempt number. A committed receipt prevents redelivery from repeating the
effect even when an attempt result event is delivered more than once.

### `agent_assignments`

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id`, `task_id` | Assignment identity and scope. |
| `parent_assignment_id` | Optional delegation lineage. |
| `assigner_principal_id` | Authority that delegated the task. |
| `assignee_principal_id` | Internal or external worker principal. |
| `agent_profile_id` | Versioned specialist role/profile. |
| `status` | Proposed, accepted, running, returned, failed, expired, or revoked. |
| `delegation_depth` | Root assignment is zero; bounded by workflow budget. |
| `authority_envelope` | Allowed skills, tools, effects, resources, and scopes. |
| `authority_hash` | Canonical envelope hash for audit and replay. |
| `context_capsule_ref`, `context_capsule_hash` | Isolated, immutable task context. |
| `budget_envelope` | Assignment-local limits, component-wise no greater than unreserved remaining parent budget. |
| `result_schema_id`, `result_schema_version` | Required return contract. |
| `expires_at`, `created_at`, `updated_at` | Assignment lifetime. |

An assignment is valid only when:

- its authority is subset-or-equal to its parent assignment or workflow authority
- each budget dimension is no greater than the unreserved remaining parent budget
- its delegation depth is below the workflow maximum
- its context capsule contains data allowed for the assignee and tenant
- its result schema is known before execution

Equality is legal for both authority and budget. An adapter may narrow either
envelope, but must not require artificial narrowing when a task needs the
parent's already-minimal authority or all remaining budget. Accepting an
assignment atomically reserves its budget against the parent; allocating the
entire remainder therefore leaves no capacity for sibling assignments rather
than allowing oversubscription. This contract uses **non-expansion**, not
strict-set attenuation, as the portable safety rule.

Assignments do not write shared workflow, belief, or memory state directly.
They return isolated results for coordinator validation.

### `approval_envelopes`

An approval is an immutable, versioned authorization snapshot for one exact
effect. It is not a boolean attribute of a task or action. The normative v1
contract is `workflow.approval-envelope` schema `1.0`.

| Field | Contract |
| --- | --- |
| `approval_id`, `schema_version` | Stable approval identity and exact schema contract. |
| `tenant_id` | Mandatory isolation boundary. |
| `principal_type`, `principal_id` | Principal requesting the governed effect. |
| `workflow_id`, `active_graph_revision` | Exact workflow plan that requested authorization. |
| `task_id`, `action_id` | Exact schedulable unit and governed action. |
| `capability_id`, `tool_id`, `effect_class` | Registry and risk identity of the effect. |
| `native_target` | Optional provider, resource type, resource ID, and parent resource ID. |
| `input_hash`, `payload_hash` | Exact normalized task input and effect payload. |
| `evidence_digest` | Exact evidence set presented for the decision. |
| `authority_hash` | Immutable workflow/delegation authority used for admission. |
| `registry_version`, `registry_fingerprint` | Exact capability registry contract and content. |
| `harness_id`, `harness_version` | Exact execution harness contract. |
| `policy_profile_id`, `policy_version` | Exact approval/effect policy contract. |
| `effect_idempotency_key` | Identity used to reconcile or deduplicate this exact effect. |
| `status` | `requested`, `approved`, `rejected`, `expired`, `revoked`, `superseded`, or `fulfilled`. |
| `requested_at`, `decided_at`, `expires_at`, `transitioned_at` | Request lifetime and current-snapshot timestamps. |
| `approving_authority` | Decision maker's principal type/ID and authoritative source/version. |
| `revocation_reference`, `supersession_reference` | Required evidence for the corresponding terminal outcome. |
| `fulfillment_receipt_id` | Required committed-effect evidence for `fulfilled`. |

All listed fields are part of the canonical serialization. Schema v1 rejects
unknown and omitted fields, uses canonical UTC timestamps and deterministic
JSON, and hashes the complete snapshot with SHA-256. Adding, removing, or
reinterpreting a field requires a new schema version; an adapter cannot ignore
an unfamiliar authority field and continue fail-open. Schema-v1 domain value
objects are closed exact types rather than subclass extension points; adapters
must cross the canonical parser boundary instead of injecting polymorphic state.
Identifiers, hashes, enum encodings, revision numbers, mapping keys, and mapping
containers use exact built-in leaf types. Accepted timestamps use built-in
fixed-offset timezone values and are normalized immediately to built-in UTC;
custom `datetime` or `tzinfo` behavior is rejected before comparison or hashing.

The complete lifecycle is:

| Source | Permitted targets |
| --- | --- |
| `requested` | `approved`, `rejected`, `expired`, `superseded` |
| `approved` | `expired`, `revoked`, `superseded`, `fulfilled` |
| `rejected`, `expired`, `revoked`, `superseded`, `fulfilled` | None |

Approval and rejection require an identified approving authority and must occur
before expiry. Revocation requires a previously approved grant. Supersession
identifies its replacement, and fulfillment identifies its effect receipt.
Expiration prevents any new admission or execution authorization. A fulfillment
receipt may be recorded after expiry only to reconcile an effect that began
under the same, then-valid approval and the same `effect_idempotency_key`; it
reports an outcome and does not authorize new work. A retry with the same
effect identity reconciles the prior outcome, while a different identity needs
a new approval.

Approval persistence and runtime checks are delivered in the following slices.
They must persist each immutable lifecycle snapshot or an equivalent append-only
event plus projection, compare the exact envelope fingerprint at admission and
immediately before effect commit, and preserve the approving authority and all
terminal evidence. The domain contract rejects direct self-supersession.
Persistence must additionally require the replacement approval to exist in the
same tenant and compatible workflow/effect scope, and must reject cycles across
the complete supersession chain.

Slice 1.5c persists this contract through three separate records. An
`approval_records` row is the current, rebuildable projection; immutable
`approval_events` retain every canonical lifecycle snapshot; and immutable
`approval_commands` deduplicate operator intent independently of event
identity. A command receipt, one or more snapshots, the legacy action-status
projection, and the control-plane audit events commit in one SQLite transaction
guarded by `BEGIN IMMEDIATE`, approval-sequence compare-and-swap, and an exact
source action-status comparison. Identical command receipts are resolved before
lifecycle checks, but a new command cannot return an executing, executed,
failed, or rejected action to an executable state. Database triggers reject
updates or deletion of event and command history. Reads compare the projection
and canonical digest to the append-only event tail before using it. Supersession
validates replacement existence, compatible scope, every traversed projection
against its immutable event tail, and the complete cycle-free chain while the
same write lock is held. Each governed action owns one approval lineage;
reapproval after amendment, expiry, rejection, revocation, or supersession uses
a replacement action and a new envelope rather than resurrecting the old
action.

The compatibility API currently resolves approving authority only from verified
bearer claims. Request parameters and tenant membership may locate compatibility
data but do not authenticate a human and cannot populate the authority record.
Human session approval remains fail-closed until a verified session or token
contract is available. Legacy action `approved` and `rejected` values are
written only after the corresponding durable decision commits; they remain
projections and cannot authorize execution.

Slice 1.5d consumes this ledger through a two-check runtime boundary. Before the
first approval snapshot is written, the fingerprinted registry contract applies
its defaults and field canonicalizers to produce one persisted executable payload
under the approval transaction. Governed execution consumes those frozen values
without further transformation. Capability, tool,
effect, version, registry, harness, and policy identity come from the
fingerprinted registry record rather than the mutable action. Admission loads
the authoritative projection and append-only tail, verifies the pinned digest
and active lifecycle, and rebuilds every binding dimension against those
independent authorities. Immediately before a governed capability call, a
`BEGIN IMMEDIATE` transaction repeats the history, expiry, action state,
approval pin, source-snapshot, executable run-status, current lease-token, and
lease-expiry checks. It reserves count-based action and variant budgets and
commits one single-use `approval_effect_executions` identity in the same write.
The transaction is the cancellation, lease, budget, revocation, and effect
linearization point: a conflicting control-plane write committed first prevents
execution; an effect-start committed first is the durable reservation and
prevents later revocation from pretending the effect never began. The start row
immutably snapshots the then-valid approval, normalized executable inputs, and
complete fingerprinted capability contract. Started or uncertain effects
reconcile from that snapshot rather than mutable run/action projections or
present-time expiry. Both normal and recovery completion independently verify
the frozen output schema, canonical output hash, and tenant-scoped provider-job
provenance bound to the exact action, approval, effect key, and effect-execution
row before a receipt can fulfill the approval. Frozen in-app `auto_run=true`
inputs additionally require a completed job and durable matching result; queued
job evidence is sufficient only when the approved payload does not require the
provider run. The requested model is immutable, must match the effect-start
inputs, drives in-app provider execution, and—not a mutable observed model—is
the result-model reconciliation oracle. Completion audit authority is also
derived from the frozen binding rather than mutable run/action projections.
Migration 045 upgrades databases that already applied the original migration
044, and migration 046 reconstructs immutable requested models from effect-start
snapshots for databases that already applied 045. Legacy starts lacking a
reconstructable snapshot remain uncertain and require operator handling rather
than inferred authorization. An unexpected error after the effect-start commit
also moves the effect to `uncertain` and the action/run to `failed`, preserving a
recoverable receipt-reconciliation path instead of a stranded execution.
That path is exposed through the authenticated, tenant-scoped
`reconcile_effect` operator command. The command accepts only workflow/action
identity, discovers the unique validation job bound to the immutable effect
start, verifies it through the normal receipt contract, and projects the
result idempotently without re-invoking the capability. A canceled run retains
its terminal control-plane state even when its late external outcome is recorded.
Run-projection recovery compares the observed run state and complete
status-relevant action snapshot under the database write lock. If concurrent
replanning changes either, recovery reloads and re-derives the projection rather
than committing a stale terminal status. Conversely, `change_plan` and `retry`
reject terminal runs at preflight and recheck that boundary under the action
insert write lock. A command whose stale preflight races reconciliation cannot
append work after completion; continuing a terminal workflow requires a new run.
The same guarded insert allocates `MAX(sequence) + 1` only after acquiring the
database write lock. Concurrent `change_plan` and `retry` commands therefore
serialize sequence allocation and cannot lose a valid recovery request to a
uniqueness collision. For retries, that transaction also allocates the next
retry ordinal for the source action and strategy and derives the final effect
idempotency key from it. Concurrent retries consequently remain distinct
authorized effects instead of sharing a single-use identity.
Successful completion atomically records the
effect receipt, marks the approval fulfilled, updates the compatibility action
projection, and appends linked audit events. Low-risk sequential actions retain
their existing path; versioned beta capability blocks are checked before this
approval boundary and remain in force.

### `task_results`

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id`, `task_id`, `attempt_id` | Provenance chain. |
| `assignment_id` | Nullable assignment that produced the result. |
| `schema_id`, `schema_version` | Typed result contract. |
| `payload_ref`, `payload_hash` | Immutable result or content-addressed reference. |
| `provenance` | Tool, model, source, registry, and evidence references. |
| `validation_status` | Pending, accepted, or rejected by the coordinator. |
| `validated_by`, `validated_at` | Coordinator validation evidence. |
| `created_at` | Result timestamp. |

Accepted results may become inputs to later tasks. Rejected results remain in
the audit history and cannot mutate shared state.

### `workflow_checkpoints`

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id` | Checkpoint identity and scope. |
| `event_sequence` | Last event included in the checkpoint. |
| `graph_revision` | Active revision at the checkpoint. |
| `projection_ref`, `projection_hash` | Rebuildable execution projection. |
| `committed_receipt_ids` | Effects that must never be repeated. |
| `safe_resume` | Whether scheduling may resume from this boundary. |
| `created_at` | Checkpoint timestamp. |

A checkpoint accelerates recovery but is not the source of truth. Replay starts
from the checkpoint only after verifying its hash, event cursor, and receipts.

### `workflow_commands`

Command deduplication is separate from event identity. One accepted command may
atomically append several ordered events.

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id` | Command identity and aggregate scope. |
| `command_type`, `command_version` | Versioned command contract. |
| `principal_id` | Actor requesting the command. |
| `idempotency_key`, `request_hash` | Dedupe key and canonical request fingerprint. |
| `expected_workflow_version` | Optimistic concurrency precondition. |
| `status` | Received, committed, rejected, or failed. |
| `first_event_sequence`, `last_event_sequence` | Inclusive committed event range. |
| `result_ref`, `error_code` | Stable replay response or normalized rejection. |
| `received_at`, `completed_at` | Command processing timestamps. |

The unique command constraint is
`(tenant_id, workflow_id, idempotency_key)`. Reusing a key with the same request
hash returns the recorded result; reusing it with a different hash is rejected.
The command record and all resulting workflow events commit in one transaction
or through an equivalent atomic durable-execution boundary.

### `workflow_events`

| Field | Contract |
| --- | --- |
| `id`, `tenant_id`, `workflow_id` | Event identity and aggregate scope. |
| `sequence` | Gap-free, monotonic sequence within a workflow. |
| `event_type`, `event_version` | Versioned event taxonomy. |
| `entity_type`, `entity_id` | Workflow, revision, task, attempt, assignment, approval, or result. |
| `causation_id`, `correlation_id`, `trace_id` | Causal and operational lineage. |
| `principal_id` | Actor responsible for the event. |
| `command_id` | Producing command; several events may share it. |
| `event_index` | Zero-based event order within the producing command. |
| `payload`, `payload_hash` | Immutable event data. |
| `occurred_at`, `recorded_at` | Domain and storage timestamps. |

The unique constraints are `(tenant_id, workflow_id, sequence)` and
`(tenant_id, workflow_id, command_id, event_index)`. Command idempotency lives
in `workflow_commands`, so a command can commit a revision, its task membership,
and a lifecycle transition as separate events. Events are never updated or
deleted by runtime code.

## State separation contract

Execution, conversation, belief, and memory are separate aggregates:

| State | Owned here | Permitted relationship |
| --- | --- | --- |
| Workflow execution | Yes | Canonical workflow/task/attempt events and projections. |
| Conversation | No | Store only `conversation_id` and command/artifact references. |
| Belief | No | Tasks consume a versioned prior and propose evidence/posterior updates. |
| Memory | No | Tasks propose candidates; memory policy validates promotion separately. |

Workflow replay must not depend on the current mutable conversation, belief,
or memory projection. Inputs record the exact versions or immutable hashes used
at execution time.

## Safety and concurrency invariants

1. All writes are tenant-scoped, including reads used before a write.
2. Workflow transitions pass through the domain lifecycle contract.
3. Graph revisions, revision membership, and events are append-only.
4. Scheduling uses the complete membership snapshot for the active revision.
5. Scheduler claims use compare-and-swap or equivalent transactional leases.
6. Only one live lease exists per task; stale workers cannot commit results.
7. External and internal committed effects require a dedupe key and receipt.
8. Commands deduplicate independently and may atomically emit multiple events.
9. Approval is an independent exact-effect lifecycle; task or action state
   cannot imply authority, and all envelope dimensions must match at admission
   and pre-effect commit.
10. Child authority is subset-or-equal to parent authority, and every child
    budget dimension is no greater than unreserved remaining parent budget.
11. Parallel workers return results; a coordinator validates before shared-state
   mutation.
12. Every controller loop has explicit iteration, time, cost, token, and action
    bounds.
13. Terminal workflow and task outcomes are immutable.
14. Projection versions are optimistic-concurrency guarded and rebuildable from
    events.

## Compatibility with the current runtime

The migration must preserve current APIs while the new kernel is introduced:

| Current model | Target relationship |
| --- | --- |
| `agent_runs` | Compatibility projection over one `workflow_run`. |
| `agent_runs.root_run_id` / `parent_run_id` | Seed workflow hierarchy only; they do not grant delegation authority. |
| principal, profile, harness, policy, and registry limits | Intersect into the immutable workflow authority envelope. |
| `agent_actions` | Governed action records linked from tasks/attempts, not replaced by task rows. |
| `agent_actions.sequence` | Initial linear graph ordering during the compatibility phase. |
| `agent_events` | Existing control-plane projection fed from versioned workflow events. |
| operator and machine commands | Populate command-deduplication records before emitting workflow events. |
| run locks and heartbeats | Evolve into workflow scheduler and task-attempt leases. |
| registry/tool/skill pins | Copied to workflow and task contracts. |
| legacy action status `approved` / `rejected` | Decision projection hint only; it cannot construct an approval envelope or grant authority. |
| legacy action execution statuses | Do not map to approval status; execution and authorization remain independent. |
| approval and compensating guidance | Migrate to independent approval snapshots linked to governed actions; preserve existing API fields as projections during compatibility. |

The first vertical spike should represent an existing sequential run as a
workflow with one immutable revision and one task per ordered action. It should
dual-project events to the existing control-plane read model. No current API is
removed until chat and control-plane parity are proven.

During that migration, one current `agent_run` maps to one workflow at graph
revision `1`. Ordered actions receive deterministic workflow task identities.
Existing explicit `approved` and `rejected` action values may seed read-model
decision history, but no historical record becomes executable authority until
its tenant, workflow/revision, task/action, effect, payload, evidence, authority,
registry, harness, policy, target, idempotency, lifetime, and approving-authority
fields have been established under the versioned envelope contract.

## Framework portability requirements

Any internal kernel, LangGraph-style adapter, or Temporal-style adapter must
demonstrate that it can:

- preserve the domain lifecycle and event sequence
- persist immutable graph revisions and runtime-created tasks
- enforce tenant-scoped idempotency and authority non-expansion
- preserve exact approval-envelope serialization, lifecycle, and fingerprints
- expose task attempts and leases without hiding retry history
- represent `all`, `any`, and `quorum` joins deterministically
- checkpoint and recover without replaying committed effects
- project existing agent-run APIs and control-plane views
- export complete event and result history without proprietary serialization

Framework-native state may optimize execution, but it cannot become the only
copy of domain events, receipts, approvals, or authority decisions.

## Consequences

Positive:

- Dynamic planning and bounded parallelism share one explicit model.
- Retry and recovery history becomes inspectable instead of overwriting state.
- Delegation has enforceable authority, budget, context, and result boundaries.
- Existing action governance remains intact.
- Framework evaluation can use repository-specific acceptance criteria.

Costs:

- Dual projections are required during migration.
- Events, attempts, results, and checkpoints increase storage volume.
- Scheduler and coordinator transactions require stronger concurrency semantics
  than the current single-process SQLite path.
- Schema and event-version migration tooling becomes a platform responsibility.

## Deferred decisions

This ADR intentionally does not decide:

- internal kernel versus LangGraph-style versus Temporal-style execution
- SQLite-constrained beta versus PostgreSQL and durable queue topology
- physical JSON versus blob/object payload storage thresholds
- the full task, attempt, assignment, and result transition matrices
- event transport and outbox implementation
- exact identifier format

Those decisions require the Phase 1 vertical spike, STPA controls, and measured
recovery/concurrency behavior.

## Validation criteria

Slice 2 is complete when reviewers can trace every target concept to a logical
record, every current runtime primitive to a compatibility path, and every
delegated execution to an authority, budget, context, result, and provenance
boundary—without relying on a particular workflow framework.

The Slice 1.5b amendment is complete when the executable approval contract has
an exhaustive transition matrix, stable canonical serialization and digest,
fail-closed schema parsing, temporal and authority validation, and explicit
legacy compatibility without persistence or runtime-enforcement coupling.

The Slice 1.5c amendment is complete when approval requests and decisions
survive restart, identical command retries return their immutable receipt,
conflicting key reuse and stale concurrent decisions fail closed, every event
names its envelope digest and authority, supersession is scope-compatible and
acyclic under the commit lock, projection rollback cannot hide immutable graph
history, terminal actions cannot be resurrected, and approval authority comes
only from verified claims. It does not make any approval executable; Slice 1.5d
owns admission and pre-effect checks.

The Slice 1.5d amendment is complete when status alone cannot authorize a
governed effect; tenant, principal, action, capability/tool/effect identity and
version, payload, evidence, authority, revision, registry, harness, policy,
expiry, revocation, and supersession are revalidated at admission and under the
pre-effect write lock; each approval/effect identity is single use; both
revocation race orders are deterministic; uncertain outcomes reconcile without
blind re-execution; and receipt, fulfillment, action, and audit projections
commit as one outcome. SEC-06/CTRL-03 are executable, while independent beta
release prerequisites remain blocked.
