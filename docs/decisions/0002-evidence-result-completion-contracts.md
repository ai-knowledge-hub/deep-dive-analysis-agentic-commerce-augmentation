# ADR 0002: Evidence, Result, and Completion Contracts

- Status: accepted
- Date: 2026-09-08
- Decision owners: workflow kernel and agent runtime
- Depends on: ADR 0001 and the exact approval/effect boundary delivered in Slice 5

## Context

The current sequential runtime can authorize an exact effect, retain immutable
effect-start evidence, validate provider receipts, reconcile uncertain effects,
and restore its run projection. Those controls prove that a particular effect
was permitted and what durable provider outcome was observed. They do not prove
that an objective has enough current evidence, that a returned task result is
acceptable, or that the workflow is complete.

Several existing paths derive `completed` from action status, stopping
conditions, job counts, or a UI projection. Existing `domain/evidence` values
are useful commerce data transfer objects but do not carry the workflow,
attempt, authority, freshness, receipt, or completeness semantics needed by a
durable agent workflow. If those representations become completion authority,
the system can report success while evidence is partial, stale, unavailable,
cross-scoped, contradictory, or still awaiting an external receipt.

This ADR defines the framework-independent Slice 6a domain boundary. Slice 6b
adds its append-only SQLite ledgers and trusted host issuance path. Coordinator
lifecycle integration, legacy projection migration, and APIs follow in later
Slice 6 increments.

## Decision

Adopt four separate immutable contracts:

```text
provider or tool observation
  -> EvidenceRecord
  -> coordinator-validated TaskResult
  -> CompletionCriteria (independent authority)
  -> CompletionAuthoritySnapshot (host-read independent oracle)
  -> CompletionDecision
  -> CompletionProjection (explicit cursor and lag)
```

No earlier object grants the authority of a later object:

- A tool call or provider receipt is an observation, not a result.
- A returned payload is not accepted until coordinator validation is recorded.
- An accepted result satisfies only the requirements named by an independently
  versioned completion-criteria snapshot.
- Worker-submitted criteria and accepted-result labels are proposals until they
  match a host-read authority snapshot. That snapshot independently pins the
  criteria, publishing/evaluation authorities, and every required task's input
  and result schema. Attempt, assignment, coordinator authority, and accepted-
  result digest attestations exist only after a result is actually accepted.
- A `complete` decision is authoritative only for its exact tenant, workflow,
  graph revision, objective, criteria hash, accepted results, and evidence.
- A projection is a view. When its event cursor trails the authoritative
  decision cursor, it reports `stale` rather than displaying terminal success.

Schema v1 contract identifiers are:

| Object | Contract identifier |
| --- | --- |
| Evidence | `workflow.evidence` |
| Task result | `workflow.task-result` |
| Completion criteria | `workflow.completion-criteria` |
| Completion decision | `workflow.completion-decision` |

All use schema version `1.0`, reject omitted and unknown serialized fields,
use canonical UTC timestamps and deterministic JSON, and hash complete payloads
with SHA-256. Domain containers and leaf values are closed exact types; custom
primitive subclasses and mutable timezone implementations cannot enter the
hashed object graph.

## Responsibility and Authority

| Claim | Proposer | Verifier or attester | Authority | May authorize completion? |
| --- | --- | --- | --- | --- |
| Raw output | Tool, model, or provider | Source adapter | External source for its own observation | No |
| Evidence provenance and receipt | Adapter | Provider or deterministic receipt verifier | Named source/version | No |
| Task-result content and coverage claim | Worker | Workflow coordinator | Versioned result schema and coordinator authority | No |
| Objective requirements | Product/policy owner | Contract publication process | Immutable criteria snapshot and authority hash | Yes, as the evaluation oracle |
| Completion decision | Deterministic evaluator | Workflow commit boundary | Host-read authority snapshot plus exact criteria, accepted results, and evidence | Yes |
| Operator-visible status | Projection worker | Cursor comparison | Completion decision event | No; it displays authority |

The model may select evidence, explain gaps, propose retries, or recommend a
conclusion. It cannot attest source identity, accept its own task result, remove
a completion requirement, or turn a projection into completion authority.

## Evidence Contract

`EvidenceRecord` retains:

- evidence, tenant, workflow, graph-revision, task, attempt, and optional action
  identity;
- availability as `available` or `unavailable`;
- a content hash for available observations;
- source type, source identity/version, immutable source-contract hash,
  producer principal, capability, and tool provenance;
- receipt state as `not_required`, `pending`, `verified`, `rejected`, or
  `uncertain`, plus its exact receipt identity when applicable;
- observation time, validity boundary, record time, or a normalized
  unavailability reason.

Freshness is evaluated at the completion decision time. It is not frozen into
a mutable `fresh` flag. Available evidence expires at `valid_until`; criteria
may impose a shorter maximum age. Unavailable evidence carries no fabricated
content, observation time, validity period, or receipt.

An evidence record deliberately does not contain a global completeness flag.
Completeness is meaningful only relative to independent requirements.

## Result Contract

`TaskResult` binds its payload and exact evidence-set digest to the tenant,
workflow, revision, task, attempt, optional assignment, immutable task-input
hash, producer, and result-schema identity/version/content hash.
Outcomes are:

- `succeeded`: a payload exists and every declared coverage claim is satisfied;
- `partial`: a payload exists and at least one declared requirement is missing,
  unavailable, or contradictory;
- `failed`: the attempt produced a normalized failure;
- `canceled`: cancellation is the terminal attempt outcome.

Validation states are `pending`, `accepted`, or `rejected`. Accepted and
rejected results identify the coordinator authority and validation time.
Acceptance means the result is a valid historical account of its attempt; an
accepted `failed` or `partial` result still cannot satisfy a successful task.

Coverage claims reference named criteria requirements and evidence already in
the result evidence set. They remain claims until the completion evaluator
resolves them against the independently supplied criteria and evidence records.
Rejected and superseded attempt results remain audit evidence but cannot become
inputs to completion.

Result evidence is also causally ordered. An available observation must occur
no later than result creation; a result cannot retrospectively claim an
observation that did not yet exist. Coordinator validation, whether acceptance
or rejection, must occur no earlier than the durable recording time of every
cited evidence record. Equality at either boundary is valid. This permits a
source observation and result to be ingested together while preventing a
coordinator attestation from depending on evidence absent from durable host
state at validation time.

## Completion Criteria and Decision

`CompletionCriteria` is the independent oracle. It pins:

- tenant, workflow, graph revision, and objective;
- criteria identity/version and publishing-authority hash;
- the complete required task set; and
- evidence requirements, including owning task, minimum item count, maximum
  age, receipt requirement, and permitted source types.

Every evidence requirement belongs to a required task. Removing a claim from a
result does not remove the requirement. Changing requirements, their source
policy, or the required task set creates a new criteria version and hash.

The evaluator does not accept a caller-supplied criteria digest or evaluation
authority as proof. Its separate `CompletionAuthoritySnapshot` must be loaded
from the host's authoritative workflow, criteria, and coordinator state. It
pins the exact criteria digest and authority hash plus one task definition for
every required task. Accepted-result attestations are a separate optional set;
their absence represents a genuinely missing result rather than invalid host
state. There is intentionally no worker-payload parser for this host object.
Slice 6b persists and issues this snapshot only from host-read contracts and
accepted durable results.

The deterministic evaluator fails closed unless:

1. Every supplied evidence and result matches the criteria tenant, workflow,
   and graph revision.
2. Every required task has exactly one accepted, successful result.
3. Every member of a result's evidence set, cited or not, belongs to that exact
   task and attempt.
4. The result's evidence-set digest matches the canonical content of every
   referenced evidence record; same-ID content substitution fails closed.
5. Every available evidence observation predates or equals result creation,
   and every coordinator-validated result postdates or equals durable recording
   of all evidence it cites.
6. The evidence source is permitted, the minimum count is met using distinct
   source observations, the observation is current under both validity and
   maximum-age rules, and any required receipt is verified. Receipt-bearing
   records sharing one receipt within the same source type, source identity,
   and source version are rejected as duplicates even when their evidence IDs
   differ; locally scoped receipt values may repeat across source namespaces.
7. No required coverage is missing, unavailable, contradictory, stale, or
   unverified.

The resulting `CompletionDecision` records accepted result IDs, evidence IDs,
every blocker category, evaluation time, and the authoritative workflow event
sequence. A `complete` decision cannot carry blockers. An `incomplete` decision
must expose at least one unsatisfied requirement, stale or unverified evidence,
or failed/missing task.

## Projection Contract

`CompletionProjection` binds to the decision digest and separately records the
decision event sequence, the independently read current workflow-stream
sequence, and the projected sequence. Neither a stale decision nor a stale
projection can display terminal completion. A cursor cannot lead the current
authoritative stream.

Chat and control-plane consumers must eventually expose the cursor, lag, stale
state, missing requirements, partial failures, and receipt blockers. They must
not infer completion from action, attempt, job, receipt, or run projections.

## Invariants

1. Evidence, results, criteria, and decisions are tenant and workflow scoped.
2. Graph revision is part of every completion-relevant identity.
3. Evidence used by a result belongs to the exact task attempt.
4. A result cannot cite evidence outside its immutable evidence set, and its
   evidence-set digest is independently recomputed before completion.
5. Workers cannot validate their own output unless separately authorized as the
   coordinator under a future explicit policy.
6. Only accepted successful results satisfy required tasks.
7. The criteria snapshot, not submitted result claims, owns required coverage.
8. Freshness is evaluated at decision time against source validity and criteria
   maximum age.
9. Receipt-required evidence is incomplete until its receipt is verified.
10. Multiple accepted results for one required task are ambiguous and fail
    closed until coordinator supersession resolves them.
11. A completion decision cannot move evidence or results across tenants,
    workflows, revisions, tasks, or attempts.
12. Projection lag is visible and cannot be labeled as terminal completion.
13. Completion does not itself authorize an external effect, belief update, or
    memory promotion; each retains its own policy boundary.
14. Submitted criteria, authority labels, accepted-result labels, task inputs,
    result schemas, assignments, and attempts cannot define their own expected
    values; completion must match the host-read authority snapshot.
15. Multiple records of one source observation cannot inflate an evidence
    cardinality requirement.
16. A result cannot cite an observation made after result creation, and a
    coordinator cannot validate a result before all cited evidence is durably
    recorded.

## Failure-Space Baseline

| Dimension | Required partitions for Slice 6 |
| --- | --- |
| Scope | exact, wrong tenant, wrong workflow, wrong revision, wrong task/attempt |
| Evidence | current, stale, unavailable, contradictory, missing, wrong source |
| Receipt | not required, pending, verified, rejected, uncertain |
| Result | pending, accepted, rejected; succeeded, partial, failed, canceled |
| Relationship | missing edge, coordinated deletion, valid substitution, duplicate |
| Time | observation before/at/after result creation; record before/at/after validation; within validity, at expiry, after expiry, late arrival |
| Concurrency | duplicate result, competing accepted attempts, replan during evaluation |
| Projection | current, lagging, leading, decision-digest mismatch |
| Version | supported, unknown, old/new producer-consumer skew |
| Representation | canonical, omitted/unknown field, hostile leaf subtype |

Slice 6a tests cover the pure-domain portions of this space. Slice 6b adds
restart, idempotency, migration, immutable-ledger, relationship, corruption,
and host-issuance coverage. Coordinator commit concurrency and API projection
behavior remain acceptance requirements for Slices 6c–6d.

## Representative Scenarios

### Complete current evidence

The provider returns an observation with verified receipt provenance. The
coordinator validates one successful task result referencing that evidence.
The evaluator resolves it against the exact criteria snapshot, finds every
required task and evidence requirement satisfied, and emits `complete`. A
current projection displays completion.

### Partial-success laundering

A tool succeeds but one required source is missing. The worker omits the
requirement from its coverage claims. The criteria still names it, so evaluation
emits `incomplete` and the missing requirement remains operator-visible.

### Late or stale evidence

A structurally valid accepted result refers to evidence whose source validity
or criteria maximum age has expired. Evaluation records the evidence and
requirement blockers. The agent may propose a bounded refresh; it cannot reuse
the stale observation as current truth.

### Cross-scope substitution

A result or evidence record from another tenant, workflow, revision, task, or
attempt is well formed. Scope and relationship validation reject the evaluation
rather than converting the substitution into an incomplete but persistable
decision.

### Projection delay

An authoritative completion event commits while the read projection trails by
one event. The view reports `stale` and its lag, not `complete`. Replaying the
event makes the projection current without changing the completion decision.

## Consequences

- Completion becomes explainable and falsifiable rather than a convenient run
  status.
- The contract adds artifacts and storage requirements, but separates source
  observation, coordinator judgment, policy criteria, and UI representation.
- Exact graph revision binding means replanning requires reevaluation under the
  new active criteria; a prior decision remains historical evidence.
- Freshness and missing coverage become first-class operator states, increasing
  honest incompleteness while preventing false terminal success.
- Provider adapters remain extensible through source types, but an unknown
  source is non-executable until a criteria version permits it.

## Deferred Work

- Slice 6c: coordinator validation, atomic completion commit, task/workflow
  lifecycle integration, replanning and cancellation concurrency.
- Slice 6d: API and UI projections, projection repair, metrics, mutation tests,
  and composed sequential-runtime verification.
- The full task, attempt, assignment, and result transition matrices remain part
  of the durable workflow-kernel delivery.
- Contradiction grouping and resolution authority beyond explicit coverage
  status remain part of evidence and learning governance.
- Dynamic fan-out, parallel workers, deterministic joins, and subagent context
  capsules remain out of scope until the sequential compatibility spike.

## Slice 6b implementation record

As of 2026-09-12, SQLite migration
`shared/db/migrations/050_workflow_outcome_ledger.sql` stores
append-only command receipts, evidence, results, completion contracts,
host-issued authority snapshots, deterministic decisions, and their exact
input bindings. Application ports remain storage-agnostic. Reads reconstruct
canonical domain values and fail on digest, scope, relationship, or denormalized
column disagreement. This ledger does not reinterpret or mutate the current
`agent_runs.status`; lifecycle integration remains Slice 6c.

Privileged outcome writes are not exposed through the general `AppDeps`
container. The SQLite adapter must be constructed with an exact host authority
policy, and it rechecks command authority for coordinator-validated results,
criteria publication, snapshot issuance, and completion decisions at the
transaction boundary. Normal worker composition therefore cannot obtain an
unbound authority writer.

Migration 050 is an expand-only migration: the previous application version
ignores the new tables, so application rollback does not require dropping
evidence. Once outcome artifacts exist, their workflow row is intentionally
protected by `ON DELETE RESTRICT`; rollback procedures must retain the ledger
and must not restore destructive run deletion. SQLite serializes each artifact,
its command receipt, and relationship bindings with `BEGIN IMMEDIATE`.

A future PostgreSQL adapter must preserve the same port and canonical payloads,
digests, uniqueness keys, foreign-key relationships, immutable-write guards,
and transaction boundaries. PostgreSQL row or advisory locking may replace
SQLite's single-writer lock, but it may not weaken exact idempotency, trusted
snapshot issuance, or read-time reconstruction checks.

## Acceptance Criteria

- Canonical round-trip fixtures and stable digests exist for all authoritative
  Slice 6a artifacts.
- Unknown/omitted fields, hostile leaf subtypes, mutable timezones, invalid
  lifecycle combinations, and relationship substitutions fail closed.
- Removing required coverage from a result cannot shrink independent criteria.
- Evidence observed after result creation or recorded after coordinator
  validation cannot be persisted as support or produce `complete`.
- Missing, stale, unavailable, contradictory, partial, failed, canceled,
  unverified, duplicate, and cross-scope states cannot produce `complete`.
- A lagging projection cannot display completion.
- Architecture, lint, bloat, documentation, safety, security, and diff gates
  remain green.
