# ADR 0001: Workflow, Task, and Delegation Schema

Status: accepted; Slices 7a-7d implemented and patterns adopted by ADR 0003
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
selects which first-party orchestration patterns to adopt. This ADR defines the
portable contract. ADR 0003 now adopts the graph-state projection and durable-
history integrity patterns that extend it without choosing a workflow vendor.

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

ADR 0002 refines this logical record into the normative
`workflow.task-result` schema and defines the associated evidence, independent
completion-criteria, completion-decision, and projection contracts. The fields
below remain the persistence target; adapters must preserve the stronger ADR
0002 scope, freshness, receipt, coverage, and authority semantics.

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

Slice 7a implements that boundary as a non-authoritative SQLite shadow in
migration 053. A current `agent_run` is compiled into one immutable
`workflow_compatibility_run`, revision `1`, an explicit complete
revision-to-task membership set, and linear `all` edges. Task identifiers equal
their source action identifiers so the already-deployed completion contracts
retain their task identity. Source `agent_events` are imported idempotently into
a gap-free compatibility event stream with their source identity and payload
digest preserved. Runtime and action lifecycle values remain authoritative in
`agent_runs` and `agent_actions`; compatibility views expose them without
rewriting immutable structure.

The shadow is deliberately not an execution or authorization boundary.
Creation invokes projection best-effort after the existing plan is durable. A
projection failure is recorded when possible but cannot prevent the legacy run
from being created or scheduled. Identical replay is duplicate-safe; restart
reconstructs the same revision; a changed action set is reported as structural
drift and never appended silently to revision `1`. Later slices own continuous
event dual-write, task attempts, scheduling from the workflow model, and any
framework selection.

Slice 7a's structural read oracle is intentionally named
`structure_and_event_ids_current`: it verifies the independently recompiled
revision/task graph, exact linear edge set, source event identities, canonical
event contents, and projection cardinalities. It does **not** claim approval,
accepted-result, effect-receipt, or completion-decision equivalence. Those
governed semantics remain authoritative in their existing ledgers.

Slice 7b represents them independently without making the compatibility shadow
an authority. Immutable semantic artifacts are admitted only when a
database-level source guard proves their exact tenant, workflow, revision,
task, attempt, source identity, canonical payload, digest, and timestamp against
the approval, outcome, effect, or completion ledger. Evidence and decision
relationships are separate artifacts so missing links cannot be hidden inside
an aggregate count. Before first backfill, the projector independently
reconstructs approval histories, effect-start/receipt provenance, and every
completion decision bundle; a reduced or corrupted source relationship set
therefore cannot certify itself. Governed action and effect-start references
independently pin required approval membership. Provider-job artifacts contain
only immutable request and effect-binding identity; mutable execution status
and provider-observed model remain live operational state, not immutable parity
evidence. Executed-action and fulfilled-approval receipts independently pin
required effect bundles. The monotonic completion cursor pins a gap-free
lifecycle history, and every lifecycle event must resolve its exact decision
and command. The mutable semantic status is only a reconciliation cursor: reads
recompute the entire artifact set and require the
same live run, action, revision, criteria, and event-cursor fence as the
authoritative completion reader before returning
`governed_semantic_parity=true`. Structural currency and semantic parity remain
separate signals, and non-governed, stale, or partially governed runs never
claim semantic equivalence.

Slice 7c keeps the immutable compatibility event stream current at source-write
time. New sequential runs persist their complete ordered action set and create
revision 1 before the first `agent_events` row. A database trigger then derives
the canonical compatibility payload, digest, scope, source row order, event
sequence, principal, trace, and timestamp inside the transaction that inserted
the authoritative event. A projection conflict aborts that source statement;
callers that already own approval, effect, or completion transactions retain
their existing commit boundary. SQLite write serialization plus the workflow
event uniqueness constraints provide gap-free compatibility ordering for the
current single-node runtime; this does not claim distributed scheduling or
parallel-worker readiness.

Current writers mark new runs as requiring the transactional projection before
the run row commits, so a concurrent event writer fails closed until revision 1
exists. The column defaults off for old-writer compatibility; inserting the
first reconciled compatibility run turns it on permanently for that workflow.
A database monotonicity guard rejects any attempt to clear that fence, and a
compatibility shadow independently keeps the fence mandatory. Event update
guards inspect both the old and new run scope, so an unfenced legacy event
cannot be reassigned into a fenced workflow. For fenced runs, source event
update, deletion, and replacement are rejected as well, so the immutable shadow
cannot be orphaned or made to certify a rewritten source identity after commit.
Source-run deletion and identity replacement are likewise rejected as soon as
the projection fence is set or a compatibility shadow exists, including the
creation interval after revision 1 is committed but before the first source
event is written. The source run's primary identity and tenant scope are also
immutable across that boundary, including rejected empty plans with no action
or event foreign-key children. A retained compatibility shadow also reserves
its source run identity independently, so neither update nor fresh insertion
can attach unrelated source provenance after corruption or partial migration.

The production writer inventory for this boundary is:

- the standalone `agent_events.create_agent_event` adapter used by initial-plan,
  command-preflight, recovery, runtime-audit, and runtime-failure services;
- approval/effect audit inserts in `approval_persistence` and
  `approval_ledger`, which participate in their existing `BEGIN IMMEDIATE`
  transactions;
- completion-decision and completion-projection-repair audit inserts in the
  workflow outcome persistence modules, which participate in their existing
  lifecycle or repair transactions.

The trigger is the common enforcement point for both adapter and direct SQL
writers, so no nested transaction or duplicated event canonicalizer is needed.
Runs without a compatibility shadow are treated as pre-Slice-7c legacy or
interrupted-migration candidates and remain visible to bounded oldest-first
reconciliation. Reconciliation imports their existing events idempotently and
also remains the repair path for detected drift. The compatibility stream is
still a non-authoritative projection: approval, effect, completion, scheduling,
and API authority remain in their established ledgers and sequential runtime.

During that migration, one current `agent_run` maps to one workflow at graph
revision `1`. Ordered actions receive deterministic workflow task identities.
Existing explicit `approved` and `rejected` action values may seed read-model
decision history, but no historical record becomes executable authority until
its tenant, workflow/revision, task/action, effect, payload, evidence, authority,
registry, harness, policy, target, idempotency, lifetime, and approving-authority
fields have been established under the versioned envelope contract.

## Framework portability requirements

The internal sequential kernel and every first-party graph-state or
durable-history strategy must demonstrate that it can:

- preserve the domain lifecycle and event sequence
- persist immutable graph revisions and runtime-created tasks
- enforce tenant-scoped idempotency and authority non-expansion
- preserve exact approval-envelope serialization, lifecycle, and fingerprints
- expose task attempts and leases without hiding retry history
- represent `all`, `any`, and `quorum` joins deterministically
- checkpoint and recover without replaying committed effects
- project existing agent-run APIs and control-plane views
- export complete event and result history without proprietary serialization

Strategy-native state may optimize execution, but it cannot become the only
copy of domain events, receipts, approvals, or authority decisions. LangGraph
and Temporal may inform the design patterns, but their packages, SDKs,
runtimes, services, persistence formats, and framework-native serialized state
are not platform dependencies.

The initial Slice 7d.2a graph-state candidate implements this boundary as a
deterministic projection and command-routing guard over the isolated portable
SQLite evidence. Exact platform-owned graph definitions name nodes, node
types, closed condition and reducer identities, state versions, the active
node, and the portable event cursor. Conditions execute against each verified
event, and deterministic reducer outputs are canonical evidence in the graph
state hash rather than descriptive labels. The definition digest includes the
canonical syntax digest of every self-contained reducer implementation. A
reducer must expose exactly `(event_type, payload, target)` with no defaults,
keyword-only parameters, or variadics, preventing external configuration from
being captured outside that digest. Changing executable reducer behavior
requires a new persisted pin even when a developer forgets to change its
version label. Each workflow also stores one
immutable definition ID, state version, and exact definition hash. Route
admission, checkpointing, and restoration fail closed if that pin is missing
or differs, including when a new definition reuses the old ID and version.
Route admission reconstructs its node from independently verified portable
history and never accepts a caller-provided graph projection as authority.
Restoration reconstructs graph state from verified commands, events, receipts,
and checkpoints through a new connection; no live graph object or graph-native
serialization is authoritative or required.

The initial Slice 7d.2b durable-history candidate adds a platform-owned
decision journal over the same portable SQLite evidence. Each workflow pins an
exact strategy ID, state version, record-contract version, and canonical
implementation digest. That definition digest also pins the complete evaluated
workflow-lifecycle transition matrix and the portability operation/command
schema implementation, so changing an imported semantic dependency invalidates
the existing workflow pin even when its version label is unchanged. The journal
appends a gap-free SHA-256 chain for four recoverable boundaries: command
admission, effect-receipt persistence, event commit, and command-receipt
persistence. Every record binds the exact portable evidence digest and command
identity. Projection verifies the entire chain and requires unique, exact
coverage of independently replayed portable history; journal records cannot
create lifecycle, authority, approval, effect, or receipt facts. The accepted
record count and head hash are stored independently of the record chain.
Verification also requires admission before later phases for each command and
event/command-receipt phases in authoritative event order, so recomputing
hashes cannot legitimize a permutation. Every record also binds a gap-free
transaction-batch sequence. A batch contains one command and one contiguous
segment of its causal phases. The ordinary SQLite writer commits a completed
non-effect command, its event, and its command receipt as one batch.
If a pre-event crash durably stages only admission, later recovery records that
admission and the atomic event/receipt pair as separate batches, allowing valid
lifecycle work between them without erasing the real commit boundaries. Effect
commands likewise retain separately visible admission and effect-receipt
boundaries because provider execution and reconciliation can span database
commits. Batch validity is not sufficient authority by itself: verification
replays committed lifecycle, attempt, fencing, and effect state in journal
order and checks each command's prerequisites at its admission boundary. A
separately rehashed batch therefore cannot admit assignment before the start
event that makes the workflow running.

Creation inserts the workflow identity, exact strategy pin, and zero-record
head in one `BEGIN IMMEDIATE` transaction. A failure at any point rolls back all
three records; retry can create the workflow instead of encountering an
immutable, permanently unpinned identity.

Slice 7d.3 makes dynamic topology part of the same portable authority boundary.
Creation pins an immutable initial graph-revision snapshot. A
`commit_graph_revision` command may append only the exact next child revision,
and the committed event binds the canonical tasks, edges, joins, parent, and
topology digest. Existing task definitions, edges, and joins cannot be removed
or rewritten. Competing children therefore cannot both become active, and a
stale command cannot schedule against a later revision. SQLite stores the
initial topology and command-carried candidate revisions as immutable canonical
JSON; the active revision is reconstructed from committed events rather than a
mutable workflow-row flag.

Task outcomes are separate attempt-bound commands. They require the current
worker, attempt, fence, live lease, workflow lifecycle, and active graph
revision; success additionally binds a result digest. Cancellation and lease
replacement reject late outcomes. A task receives at most one authoritative
outcome in this benchmark contract. Join state is never adapter-owned:
`all`, `any`, and `quorum` are recomputed from the active revision and exact
outcome evidence as `waiting`, `satisfied`, or `impossible`. Assignment to a
joined task is legal only when every join targeting it is satisfied. Graph-state
and durable-history records remain projections and cannot invent membership,
outcomes, join satisfaction, or revisions.

Revision advancement does not erase an effect already observed by the
independent provider oracle. If execution occurred under an earlier active
revision but the process failed before its receipt or event commit, retry of
that exact command may cross the later revision fence only to persist the
matching provider receipt and append an `effect_reconciled` event. Portable
replay admits that stale revision solely for this reconciled event and still
requires the prior attempt assignment, exact command digest, execution
provenance, effect receipt, tenant, workflow, task, worker, and fence. A stale
effect without provider execution remains rejected before any external call.

Crash recovery opens a fresh connection, verifies the portable checkpoint and
external effect ledger first, requires the immutable strategy pin, then appends
only journal phases already proven by that evidence. An executed effect without
a receipt remains owned by the independent provider oracle and pending command,
so reconciliation cannot call the provider again merely to repair the journal.
Lease reassignment, fencing, pause, cancellation, and late delivery continue to
use the shared lifecycle rather than strategy-local rules. The candidate has no
Temporal SDK, service, payload, or persisted serialization dependency.

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

ADR 0003 decides which graph-state and durable-history patterns should extend
the future kernel. This ADR continues to defer:

- SQLite-constrained beta versus PostgreSQL and durable queue topology
- physical JSON versus blob/object payload storage thresholds
- the full task, attempt, assignment, and result transition matrices
- event transport and outbox implementation
- exact identifier format

Those decisions require Phase 3 production-topology evidence and the existing
STPA, security, portability, and recovery contracts; the completed Phase 1
spike is evidence for their invariants, not a production deployment result.

## Phase 2.1 operator-conversation projection contract

The first production operator-conversation increment is a read-only projection
over one authorized workflow run. It does not introduce a third execution
model, scheduler, command format, or completion authority.

- Browser requests pass through the same-origin authenticated web BFF, which
  replaces request identity and signs a short-lived assertion bound to the
  exact tenant, user, and run. Direct API clients may instead present a signed,
  expiring human-principal bearer token. Tenant and user authority come only
  from verified claims; optional request selectors must exactly match them.
  Revision, cursor, lifecycle, or completion claims are rejected.
- Each operator session is scoped to one tenant, authenticated identity, and
  run. Conversation persistence stores references and answer evidence only;
  workflow reconstruction never reads mutable conversation state.
- A server-built snapshot pins the active graph revision, ordered action and
  event projection, approval/effect receipts, linked experiment evidence,
  completion decision/projection, completeness, cursor, and a canonical
  digest. The answer retains this as-of snapshot even when a post-reasoning
  fence read observes newer execution state.
- Bounded experiment collections are read with an extra-row probe and expose
  source-specific completeness. Missing links, failed reads, truncation, and
  contradictory experiment/variant identities are distinguishable states and
  become operator warnings rather than disappearing behind a current freshness
  label. Bounded completion evidence exposes its truncation, observed count,
  and whether additional records exist.
- Action-linked validation jobs expose requested and included counts. Missing
  tenant-scoped records, dependency failures, and contradictory job/action
  identities are distinct fail-closed completeness states and warnings. The
  governed effect-completion transaction writes the verified validation-job
  identity to both the typed outputs and canonical action link. For records
  produced before that dual representation, an output-only link is accepted
  only when it matches the succeeded effect's tenant, action, approval,
  idempotency key, execution identity, and receipt. A retry or change-plan
  action never inherits this result identity: the prior job is preserved under
  source recovery context and the new action's canonical link is populated
  only by that action's independently verified receipt transaction.
- Compatibility `agent_runs.status` is lifecycle context, not completion
  authority. Only a current verified completion decision may support a
  completion statement; missing, stale, or corrupt completion evidence produces
  an explicit unavailable warning.
- The reasoning boundary accepts only a closed intent and identifiers from the
  server-created fact catalog. Generated prose and retrieved execution text are
  untrusted and cannot alter facts, authority, navigation targets, or commands.
- Intent admission adds mandatory server-owned fact categories even when model
  selection omits them. Objective, event, metric and baseline comparison,
  validation, completion-evidence, and recommendation facts retain typed record
  provenance and resolved in-scope navigation links.
- Mutation language receives a read-only refusal and a server-created deep link
  to the governed Interventions surface. The conversation service has no
  dependency on the command gateway.

This contract is the shared gateway seam for later `/` and Lab convergence.
Later write-capable chat must map intent to an exact command envelope and pass
the existing preflight, approval, authority, idempotency, and receipt controls;
it must not weaken this read-model boundary.

## Phase 2.2 conversational pause command contract

The first write-capable operator-conversation increment is deliberately one
closed command: pause the selected run. Natural-language text selects that
intent but never supplies command parameters, tenant, principal, run identity,
revision, policy, or authority.

- Proposal creation is non-mutating with respect to workflow execution. The
  durable proposal binds the authenticated human, tenant, run, active revision,
  source lifecycle, snapshot digest and cursor, latest event identity, policy,
  harness, registry pins, exact preflight digest, expiry, idempotency key, and
  canonical proposal digest.
- Confirmation is a second user action and a second authenticated request. The
  browser BFF uses a command-only secret and assertion audience; the Phase 2.1
  read assertion cannot authorize this boundary. Analysts can read the run but
  only owner, admin, and operator roles can confirm.
- The host reloads the immutable proposal and independently reconstructs the
  current snapshot and preflight. After `BEGIN IMMEDIATE`, it reconstructs the
  complete server-owned snapshot and preflight a second time on the same
  per-thread connection, and compares their digests before changing state.
  Actions, approvals, effects, linked validation evidence, experiment evidence,
  and completion projections therefore share the final transaction fence with
  lifecycle, revision, pins, and the event head.
- The pause status, `operator_command_pause`, `run_paused`, optional
  `run_stopping_condition_met`, and immutable command receipt are one atomic
  outcome. Any event/projection/receipt failure rolls back the run update.
  Concurrent or repeated exact confirmations converge on one receipt and one
  command/lifecycle event set.
- The receipt says `control_plane_paused` and
  `runtime_propagation_not_certified`. This slice does not close SEC-17 or claim
  that an already in-flight worker, connector, or external operation has
  acknowledged interruption.
- A tenant-and-run-scoped authenticated read model verifies immutable proposal
  columns and receipt digests on every load. Stable cursor pagination reports
  total, included, and remaining evidence rather than silently truncating the
  ledger. Runs can load older pages; a run-scoped Interventions link fetches the
  exact run outside the bounded queue and pages its command projection. Thus a
  later answer, navigation, reload, or queue-window change cannot hide a pending
  proposal or its exact receipt identity.

Other conversational mutations require their own closed typed contracts rather
than model-authored executable payloads.

## Phase 2.3a conversational resume command contract

- `resume_run` selects a host-owned `resume` command with v2 proposal and receipt
  contracts. Source status must be `paused`; source `run_mode` and predicted
  outcome are immutable. The sequential start mapping is `plan_only -> planned`
  or `auto_execute_safe -> running`. It does not add a portable lifecycle edge.
- A separate explicit confirmation binds command type, proposal ID/digest,
  tenant, human, run, and idempotency. The final write lock fences membership,
  principal activity, lifecycle, revision, full control inputs, approvals,
  effects, linked validation, completion evidence, pins, live registry and
  preflight. Exact committed retries are recognized before stale-state checks.
- New resume proposals and final admission require a successful scoped
  completion-authority read. Reader integrity errors and missing views block
  admission even when repeated failures produce an unchanged snapshot digest.
  A verified legacy view with no completion decision remains compatible;
  explanatory reads retain warnings and committed receipts remain replayable.
- Busy runs, executing actions, started or uncertain effects, current harness
  stops, and unresolved recorded stops other than an exact operator-pause marker
  are ineligible. Bounded control-event reads fail closed when they cannot
  establish the relevant stopping history.
- A compatibility `run_started` or `run_resumed` event does not resolve earlier
  stopping conditions. Only a later clear event in the same run naming the
  exact stopping-event ID resolves that marker. Starts cannot bypass the
  bounded history completeness check.
- The status, `operator_command_resume`, `run_resumed`, exact optional
  `run_stopping_condition_cleared`, and receipt commit together. No capability
  runs here; no approval, budget, policy, mode, attempt, or effect is rewritten.
  A succeeded effect remains succeeded and governed pre-effect checks still
  apply to subsequent scheduling.
- Receipt acknowledgement is `control_plane_resume_eligible`, with the recorded
  `run_mode`, outcome status, and `runtime_propagation_not_certified`. This is
  neither completion evidence nor worker acknowledgement; SEC-17 remains planned.
- Additive migration 057 preserves immutable v1 pause records and exposes mixed
  v1/v2 history through the existing scoped cursor projection. Old pause-only
  readers remain valid, though they cannot display resume records.

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


## Phase 2.3b conversational cancel command contract

- `cancel_run` selects only a host-owned v3 `cancel` proposal and receipt.
  Existing v1 pause and v2 resume contracts retain their exact digest shapes.
- Admission is restricted to canonical created/planning/planned/running/paused
  runs in plan_only/auto_execute_safe modes. The sole target is `canceled`, as
  permitted by the canonical lifecycle. Terminal and unknown sources fail closed.
- The proposal binds authenticated tenant/human/run, revision, mode, governing
  pins, private control-state digest, preflight, event head, expiry, and identity.
  The dedicated command assertion binds that exact proposal and command type.
- Completion verification must succeed at proposal creation and final admission;
  verified legacy evidence remains compatible. Missing or corrupt evidence fails
  closed. Final admission runs under SQLite BEGIN IMMEDIATE and rechecks live
  membership, principal, registry, all fenced evidence, and quiescence.
- A runtime lock, executing action, started/uncertain effect, or incomplete
  bounded action state prevents this quiescent cancellation path. Existing stop
  markers remain unresolved: cancellation creates no stop-clear event.
- Status, human command audit, run_canceled lifecycle audit, required workflow
  event projection, and immutable receipt commit atomically. No capability runs.
  Exact receipt replay precedes new admission and cannot revive the run.
- Migration 059 makes v3 receipt-backed cancellation terminal at persistence,
  including legacy runs without completion governance. Background reconciliation
  and planning activation use conditional status transitions and reread the run
  when a concurrent control action wins; they cannot revive a canceled run or
  replace its terminal status with a planning failure.
- The v3 receipt acknowledges `control_plane_canceled`, preserves the source mode,
  records the terminal target, and declares `runtime_propagation_not_certified`.
  It certifies neither worker interruption nor external-effect reversal.
- Mode, revision, approvals, budgets, attempts, pending actions, completed effects,
  and evidence remain intact. Further work requires a new authorized run.
- Migration 058 is additive for v1/v2 evidence and introduces separate v3 scoped
  paginated views for all three contracts. Old readers retain their original
  tables and v1/v2 views, excluding v3 rows they cannot deserialize. Deploy the migration and backend before the new UI.


## Phase 2.4a conversational exact action review

- One proposed action per immutable v4 approve/reject proposal. Eligible run
  states are planned/running/paused, using plan_only/auto_execute_safe. Terminal,
  unknown, executing and already decided sources cannot receive a new decision.
- The host resolves an exact action ID or sequence; a unique pending action may
  be selected automatically. Ambiguous, batch and combined execute requests do
  not create proposals. Model output cannot select a mutating intent or grant
  authority. Proposal preparation and normalization are read-only.
- The proposal binds full private state and exact normalized inputs, effect and
  registry identity, policy/harness pins, evidence, revision and pending approval
  identity/sequence/digest. An existing request must match rebuilt current
  binding, verified immutable history and an unexpired lifetime.
- Browser confirmation verifies schema-v2 `operator-action-review-api` assertions
  from `operator-action-review-web-bff`, signed with the server-only command
  secret and bound to human, tenant, run, action, decision, proposal and digest.
  Its approval authority is recorded as `operator-action-review-bff` /
  `operator-command-signing-secret:v2`. Direct human bearer authority keeps the
  existing source/version. Neither read nor lifecycle-control assertions can
  cross this exact approval boundary.
- The conversational adapter owns BEGIN IMMEDIATE; the existing approval adapter
  joins through a savepoint and commits only its owned transaction. Approval
  command, canonical envelope history, compatibility action, approval audit,
  required workflow projection, operator audit and v4 receipt commit together.
  Inner rejection preserves caller ownership; outer failure rolls back both
  ledgers. Confirmation leaves run status, mode, budgets and stops unchanged.
- The v4 receipt names action, approval command, approval ID, envelope digest and
  sequence, exact decision, unchanged run status and attributable audit IDs.
  It acknowledges only `exact_action_decision_recorded`; capability execution,
  worker continuation and completion are separate facts.
- Exact replay checks current human access under the lock before inspecting new
  eligibility. Cancellation, later execution or revocation does not erase a
  historical decision receipt. Replay grants no fresh execution authority.
- Migration 060 adds separate v4 history views; previous views exclude contracts
  previous readers cannot deserialize. Existing approval and command identities
  remain intact. Existing beta blocks are not relaxed by chat confirmation.


## Phase 2.5a conversational retry compatibility

The current sequential adapter appends one proposed action for an exact failed
source, using only the same-action strategy and a distinct effect identity.
Immutable v5 proposals pin full private state and normalized inputs; explicit
human confirmation revalidates current authority and eligibility under the
write lock. Sequence and retry ordinal allocation, child action, human audit
and workflow events, and receipt form one transaction. The child inherits no
approval, outcome or result link. Existing exact approval and pre-effect
controls govern execution, with no budget or authority expansion. The same
pre-effect write transaction checks the complete related retry family before
reserving a new effect. A started, uncertain or succeeded related effect blocks
roots, descendants and prequeued siblings, even with distinct fresh approvals
and effect keys. Immutable v5 receipts retain source/child membership when
action keys change; legacy keys and committed effect identities remain linked.
Exact effect replay still requests reconciliation and never invokes the provider.

A verified receipt permits status derivation to hold its exact source failure
while that child is proposed, approved or executing. Other failures and stopping
conditions remain effective. The hold is released when the child is finished,
failed or rejected; historical failure evidence and required completion task
membership are never rewritten. This is action retry compatibility, not an
independent task-attempt replacement or a goal-completion rule. Terminal runs
and any related source-family committed effect require separate recovery. A receipt
acknowledges only `retry_action_proposed`, with execution, propagation and
completion remaining separately verified facts. Migration 061 adds v5 views
without rewriting older command contracts; older workers lack the receipt hold and pre-effect family fence.

## Phase 2.5b conversational effect reconciliation compatibility

Conversational reconciliation records a historical outcome under the frozen
then-valid effect-start authority. It never grants fresh execution permission or
consults current mutable capability semantics to reinterpret that effect.
Validation auto-run requires the exact completed job and matching durable result;
non-auto-run preserves bound job-creation semantics. Lab promotion requires its
validated, exact governed receipt. Action failure is a projection, not proof that
an effect did not happen. Legacy starts without reconstructable authority remain
quarantined.

The v6 proposal pins human/tenant/run/action/execution, original approval and
start digests, full evidence digest, current private control state and freshness.
A schema-v4 confirmation assertion carries action and execution identity in a
separate audience. The final `BEGIN IMMEDIATE` rechecks access, lease, bounded
complete state and independent evidence, then composes effect fulfillment,
action/link, projection, two human audits and immutable receipt in one owned
transaction. Existing effect-completion, run-projection and event adapters join
through savepoints while retaining standalone commit ownership.

There is at most one conversational receipt per execution. Competing proposals
cannot both record it. Delivery of the winning proposal returns its immutable
receipt after checking current access, independently of subsequent expiry or
mutable projection changes. When background recovery commits first, stale
confirmation returns conflict and a fresh proposal can acknowledge the existing
success without duplicating effect fulfillment. Canceled/completed/paused states
and event-specific unresolved stopping markers are preserved; recording success
is not an objective completion decision. New conversational recovery does not
infer legacy objective completion from the executed action set. The existing
authenticated direct recovery path retains its compatibility behavior.
Acknowledging an already-succeeded effect with a consistent executed action
preserves the current run record, including progress from later actions and
diagnostics. Its historical frozen next state is used for first-time recovery,
not reapplied by an acknowledgement.

Additive migration 062 retains the previous five history contracts and cursors.
This sequential-runtime adapter does not add task attempts, compensation,
provider polling, automatic execution or a distributed workflow kernel.
