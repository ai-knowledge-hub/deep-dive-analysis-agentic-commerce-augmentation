# ADR 0003: Workflow Orchestration Pattern Adoption

- Status: accepted
- Date: 2026-09-23
- Decision owners: platform architecture, workflow kernel, and agent runtime
- Depends on: ADR 0001, ADR 0002, and `workflow-portability.v3`
- Evidence: Issues #142, #144, #148, and #150

## Decision summary

Adopt a first-party, evidence-led orchestration kernel composed from the tested
patterns rather than selecting one adapter or importing a workflow framework.

The production authority target is the framework-neutral workflow contract:
versioned commands, events, graph revisions, task attempts, accepted results,
checkpoints, approval decisions, effect starts and receipts, completion
decisions, and immutable strategy pins. Two derived strategies may optimize
that authority without replacing it:

1. **Graph-state projection.** Rebuild task readiness, conditional routing,
   active topology, and deterministic join state from verified portable
   evidence. Its state hash and cursor are diagnostic and admission inputs only
   after independent reconstruction.
2. **Durable decision journal.** Record inspectable command phases,
   transaction batches, evidence digests, and a separately persisted chain
   head. It detects incomplete or reordered recovery history and reconciles
   only tails already proven by authoritative evidence.

The current sequential SQLite runtime remains the execution compatibility
path through Phase 2. This ADR does not promote the benchmark adapters into a
production scheduler, enable parallel workers, or select a production database
and queue topology.

This is the smallest coherent design because it preserves one owner for every
consequential fact while retaining the useful scheduling and recovery
properties demonstrated by both candidate strategies. A single selected
adapter would either make a projection authoritative or discard independently
useful patterns.

## Context

ADR 0001 deliberately deferred orchestration-pattern selection until a working
vertical spike could exercise repository-specific correctness criteria. Slices
7d.1 through 7d.3 now provide four adapters over one portable contract:

- an in-memory internal-kernel baseline;
- an isolated durable SQLite baseline;
- a graph-state strategy over the SQLite authority boundary; and
- a durable-history strategy over the same boundary.

All adapters run the same deterministic lifecycle, lease, fencing, effect,
crash, restart, graph-expansion, task-outcome, and join scenarios. The test
harness, logical clock, effect sink, provider-execution ledger, and receipt
ledger remain independent of adapter state. LangGraph and Temporal informed the
research vocabulary only; no package, SDK, runtime, service, persistence
format, or framework-native state from either is present.

The decision must also fit the deployed platform. Today the production
sequential runtime, approval ledger, effect ledger, completion ledger, and
compatibility workflow shadow already own established authority. Replacing
them in one migration would create two competing truths and an unsafe rollback
boundary.

## Scope and evidence boundary

In scope:

- the authority relationship among portable workflow evidence, graph-state
  projections, durable-history projections, checkpoints, and external effects;
- patterns to carry into the Phase 3 durable workflow kernel;
- the supported Phase 2 deployment envelope;
- migration, cutover, compatibility, and rollback constraints; and
- the Phase 1 architecture-decision exit gate.

Out of scope:

- production task scheduling, fan-out, parallel workers, or delegation;
- PostgreSQL, queue, or event-transport selection;
- final task, attempt, assignment, and result transition matrices;
- physical payload-storage thresholds;
- a chat product implementation; and
- any vendor workflow dependency.

The evidence boundary is deliberately local and deterministic. It covers the
portable contract, the four first-party adapters, the schema-v4 operational
measurement, the current sequential compatibility path, and the accepted
safety and security contracts. It does not prove distributed scheduling,
multi-node failover, noisy-neighbour isolation, or production-scale latency.

## Measured evidence

A fresh five-sample run on 2026-09-23 used Python 3.11.12 and SQLite 3.51.3.
Every adapter completed the dynamic-join, effect, checkpoint, and fresh-restore
scenario with graph revision 2, one satisfied join, seven canonical commands,
seven events, seven command receipts, one effect receipt, and two checkpoints.
No candidate required an additional package or external service.
The complete focused portability portfolio passed 171 tests against the same
contract and independent effect oracles.

| Adapter | Correctness | Median cold start | Median recovery | Database bytes | Incremental source lines |
| --- | --- | ---: | ---: | ---: | ---: |
| Internal kernel | Pass | 44,167 ns | 980,625 ns | 0 | 844 |
| SQLite portable store | Pass | 2,664,917 ns | 5,041,459 ns | 143,360 | 1,191 |
| Graph-state strategy | Pass | 3,671,375 ns | 7,432,042 ns | 143,360 | 797 |
| Durable-history strategy | Pass | 12,476,209 ns | 18,567,458 ns | 151,552 | 1,199 |

These values compare one bounded local run; they are not service-level
objectives. Correctness gates dominate latency. The measurements show that the
patterns are operationally feasible without hiding their relative complexity,
not that the benchmark is production capacity evidence.

## Authority allocation

| Claim | Authoritative owner | Derived consumers | Forbidden inference |
| --- | --- | --- | --- |
| Tenant, workflow, principal, and command identity | Host-issued command contract | All strategies and projections | Strategy-local fields cannot broaden scope. |
| Workflow lifecycle legality | Versioned domain lifecycle plus committed events | Scheduler, graph state, journal, chat, control plane | A node label or journal phase cannot create a transition. |
| Active graph revision and task membership | Immutable revision snapshots plus committed revision event | Readiness and join projectors | A mutable active-node value cannot add or remove tasks. |
| Attempt ownership and fencing | Authoritative attempt/lease evidence and harness time | Scheduler and route projection | A checkpoint or heartbeat projection cannot restore ownership. |
| Approval and effect authorization | Existing exact approval/effect contracts | Workflow events and operator projections | Task success or route readiness cannot authorize an effect. |
| External execution | Provider observation and independent effect ledger | Receipt reconciliation, journal, workflow events | Neither a journal record nor graph state proves execution. |
| Accepted result and completion | ADR 0002 result, evidence, criteria, authority, and decision ledgers | Join, chat, and control-plane projections | Join satisfaction or terminal node state cannot imply objective completion. |
| Route readiness and join state | Deterministic derivation from verified evidence | Scheduler and diagnostics | Cached readiness cannot survive a cursor, hash, scope, or revision mismatch. |
| Recovery phase coverage | Derived durable decision journal | Operators and recovery coordinator | Journal coverage cannot manufacture missing portable evidence. |

The model may propose plans, tasks, revisions, and recovery actions. Domain
validation, policy, trusted host authorities, and transactional executors
decide whether those proposals may commit. Models and strategy projections do
not attest identity, permission, effect execution, result acceptance, or
completion.

## Adopted graph-state patterns

Adopt:

- explicit versioned nodes and conditional transitions for inspectable route
  decisions;
- closed condition and reducer registries;
- canonical reducer outputs in the derived state hash;
- exact implementation and definition pins checked at route, checkpoint, and
  restore boundaries;
- history-reconstructed admission rather than caller-supplied projections;
- a graph cursor and state hash for freshness and diagnostics; and
- deterministic readiness and `all`, `any`, and `quorum` join derivation from
  immutable topology and attempt outcomes.

Reject:

- graph-native mutable checkpoints as the only recovery state;
- serialized framework runtime objects as durable authority;
- adapter-owned commands, lifecycle transitions, effects, or receipts; and
- active-node state as proof of task membership, authorization, or completion.

The Phase 3 implementation may materialize graph projections for scheduling
performance. A projection must be reproducible from the exact authoritative
cursor and fail closed when its definition pin, scope, revision, history hash,
or state hash is missing or inconsistent.

## Adopted durable-history patterns

Adopt:

- append-only, inspectable decision phases for command admission, external
  receipt persistence, event commit, and command receipt;
- one-command, gap-free transaction batches that preserve real commit
  boundaries and reject impossible interleavings;
- immutable strategy and semantic-dependency pins;
- hash-chained records bound to a separately persisted count and head;
- lifecycle and ownership replay at every admission boundary; and
- evidence-led tail reconciliation after portable evidence, checkpoint, and
  provider ledgers have been independently verified.

Reject:

- inferring provider execution from journal state;
- allowing the journal to admit commands or invent lifecycle facts;
- vendor-native history serialization; and
- treating an internally consistent rehashed chain as sufficient authority.

The journal is a mandatory integrity and operations projection for the future
kernel's durable command path, but it remains rebuildable. Missing or corrupt
journal state blocks new scheduling until verified repair; it does not erase or
reinterpret authoritative workflow, approval, effect, result, or completion
evidence.

The journal hash chain detects application-level omission, insertion,
duplication, mutation, reordering, and impossible phase or transaction
boundaries when compared with independent portable evidence. It is not a
tamper-proof ledger against a privileged actor able to rewrite both the
authoritative store and every independent head or receipt. Database access
control, immutable backups, audit export, and the planned append-only database
security control SEC-18 remain separate production requirements.

## Deployment decision

Phase 2 remains inside the current supervised or low-risk sequential envelope:

- the supported single-node SQLite deployment and database-serialized writes;
- the existing WAL, foreign-key, and guarded transaction policy; changes to
  busy handling or synchronous durability require separate operational
  validation rather than being inferred from the benchmark configuration;
- the existing sequential scheduler and effect boundary;
- compatibility workflow shadows and transactional event projection; and
- no write-capable dynamic delegation or parallel-worker beta release.

Chat-issued Phase 2 mutations must resolve to the established exact command,
approval, effect, completion, and compatibility boundaries. Chat and graph
views remain projections and must expose revision, cursor, freshness,
incompleteness, and receipt state rather than synthesizing success.

Before Phase 4 bounded parallelism, Phase 3 must separately decide and prove a
concurrency-safe database and durable queue topology, task-attempt leases,
atomic budgets, tenant bulkheads, cancellation propagation, outbox or transport
semantics, and crash recovery under process loss. This ADR supplies patterns;
it does not release those capabilities.

## Migration and cutover boundary

The production migration is expand-first and evidence preserving:

1. **Retain current authority.** Phase 2 continues to execute through
   `agent_runs`, governed actions, and the existing approval, effect, evidence,
   result, and completion ledgers. The Slice 7 compatibility workflow remains a
   non-authoritative projection.
2. **Add the Phase 3 authority store.** Introduce versioned workflow, revision,
   task, attempt, command, event, checkpoint, graph-projection, and decision-
   journal records behind framework-neutral ports. No legacy record is deleted
   or reinterpreted.
3. **Dual-project and compare.** For eligible sequential workflows, commit one
   new authoritative transaction. A co-located compatibility projection may
   share that transaction. A projection in another store must consume a
   transactional outbox record written with the authority commit, expose lag,
   and remain non-authoritative; cross-store best-effort dual writes are not an
   atomicity mechanism. Rebuild graph and journal projections from the new
   evidence and compare them continuously.
4. **Shadow scheduling.** Compute readiness, joins, leases, and recovery
   decisions without dispatching effects. Record disagreement and block cutover
   rather than preferring either projection.
5. **Cut over per new workflow.** A workflow receives an immutable kernel and
   strategy pin at creation. Ownership never changes silently after evidence or
   an external effect exists. Existing legacy workflows finish on their
   established path unless an explicit, verified migration contract is added.
6. **Retire only after parity.** Remove a legacy writer or reader only after its
   supported workflow population is drained or migrated and API, chat,
   control-plane, recovery, audit, and rollback parity is executable.

## Rollback strategy

Rollback is a writer and admission decision, not data deletion:

- stop admitting new workflows to the new kernel;
- stop scheduling when definition pins, projections, journal integrity, or
  compatibility comparisons disagree;
- retain all new commands, events, receipts, journal records, and projections;
- keep compatibility reads explicit about stale or unsupported state;
- use the last binary compatible with the pinned contract, or a narrowly
  scoped recovery tool, to reconcile already kernel-owned workflows; and
- allow the legacy runtime to continue only workflows that never transferred
  execution authority to the new kernel.

An application rollback may ignore expand-only tables, but it must not delete
them, reuse their workflow identities for unrelated work, or resume a
kernel-owned workflow from a stale legacy projection. Database rollback must
remain forward-readable until every workflow written by the new contract has
reached a terminal or explicitly migrated state.

## Failure and recovery scenarios

The adopted composition must preserve these outcomes:

- A changed graph reducer or lifecycle dependency invalidates its immutable
  definition pin before route admission or replay.
- A reordered or consistently rehashed journal fails its causal, transaction-
  batch, authoritative-event-order, or independently persisted head checks.
- A provider-executed effect with no receipt reconciles from the exact pending
  command and provider ledger without a second execution, even after a graph
  revision advances.
- A stale or reassigned worker cannot commit an outcome, satisfy a join, or
  execute an effect.
- Cancellation blocks new work while preserving a late provider observation as
  reconciliation evidence rather than workflow success.
- A graph or journal projection can be discarded and rebuilt without losing an
  approval, effect, result, completion decision, or audit fact.
- A partial, stale, unavailable, contradictory, or unverified result cannot be
  laundered into completion through terminal graph state.
- A mixed-version consumer rejects an unknown command, event, strategy, graph,
  journal, or projection contract instead of silently applying older semantics.

## Alternatives rejected or deferred

### Keep only the sequential kernel

Rejected as the target architecture. It preserves compatibility but does not
provide dynamic topology, independently retryable attempts, deterministic
joins, or the recovery visibility required for later bounded parallelism.

### Select graph state as the workflow authority

Rejected. It would compress approval, effect, result, completion, and history
semantics into a mutable execution representation and make definition changes
capable of reinterpreting retained evidence.

### Select the durable journal as the workflow authority

Rejected. A self-consistent journal cannot independently attest provider
execution, tenant authority, approval, or portable event truth. It is strongest
as an integrity and recovery projection over those authorities.

### Import LangGraph, Temporal, or another workflow runtime

Rejected for the current delivery sequence. The spike found no correctness
property that requires a vendor runtime, while vendor serialization and service
semantics would add a second authority and rollback boundary before the
production kernel contract exists. A later ADR may reconsider operational
infrastructure only against the same portable contracts and migration rules.

### Choose the production database and queue now

Deferred to Phase 3. The local SQLite evidence proves a constrained sequential
envelope, not safe concurrent multi-tenant scheduling.

## Consequences

Positive:

- one portable authority survives strategy and infrastructure changes;
- graph routing and durable recovery are independently inspectable;
- framework upgrades cannot silently reinterpret existing workflows;
- current approval, effect, completion, and API contracts remain valid during
  migration; and
- Phase 2 can build chat supervision without prematurely deploying a parallel
  scheduler.

Costs:

- graph and journal projections add storage, validation, and operational work;
- definition and semantic dependency changes require explicit versioning and
  migration;
- projection disagreement intentionally stops scheduling; and
- Phase 3 still must implement the production persistence, queue, task
  lifecycle, and migration contracts.

## Phase 1 closure

This ADR completes the Phase 1 architecture-decision deliverable:

- workflow, revision, task, attempt, delegation, approval, evidence, result,
  completion, checkpoint, command, and event semantics are defined by accepted
  contracts;
- workflow and governed-action transitions have executable domain and runtime
  verification within the current supported envelope;
- the STPA and security catalogs map initial unsafe control actions and threats
  to controls, detection, verification, or explicitly blocked beta gaps; and
- the orchestration decision is based on an executable four-adapter vertical
  spike with fault, replay, restart, concurrency, topology, and join evidence.

For the Phase 1 exit gate, "allowed transitions" means transitions enabled in
the current supported sequential runtime and the executable portability
contract. Deferred production task, assignment, delegation, and parallel-
worker transitions are not silently allowed; they remain blocked until their
Phase 3 and Phase 4 contracts and verification exist.

Phase 1 completion is not a claim that Phase 3 or Phase 4 capabilities already
exist. Dynamic production scheduling, distributed recovery, parallel agents,
and write-capable delegation remain blocked until their later exit gates pass.

## Acceptance criteria

- The decision names one authority for every consequential workflow claim.
- Adopted graph and journal patterns cannot independently authorize lifecycle,
  effects, result acceptance, or completion.
- Migration is expand-first and prevents old and new writers from silently
  owning the same workflow.
- Rollback preserves all evidence and does not revive work from a stale
  projection.
- The supported SQLite envelope and parallel-execution exclusions are explicit.
- The fresh five-sample measurement and complete golden scenario portfolio pass
  for every adapter.
- Phase 1 status and the research record link to this decision.
- Documentation, safety, security, architecture, lint, and repository diff
  gates remain green.
