# Workflow Framework Portability Spike v1

Status: snapshot
Last verified: 2026-09-20
Baseline: `origin/main@131b23d`
Issues: [#142](https://github.com/ai-knowledge-hub/deep-dive-analysis-agentic-commerce-augmentation/issues/142), [#144](https://github.com/ai-knowledge-hub/deep-dive-analysis-agentic-commerce-augmentation/issues/144)

## Decision question

Which first-party orchestration strategy should carry the platform from the
current sequential SQLite runtime into durable task attempts and later bounded
parallelism without making strategy-native state authoritative?

The candidates are:

- the internal sequential workflow kernel;
- a first-party graph-state strategy inspired by explicit graph execution; and
- a first-party durable-history strategy inspired by durable workflow systems.

This document records the independent benchmark contract and evidence. It does
not select a vendor. A later ADR must decide which patterns to adopt from
executable results and state the supported deployment envelope. LangGraph and
Temporal are research references only: their packages, SDKs, runtimes,
services, persistence formats, and framework-native state are excluded from
the implementation.

## Evidence boundary

The first increment is deterministic and local. It defines a common adapter
port and factory, canonical revision-pinned command evidence, immutable events,
command and effect receipts, replayable history export, verified checkpoints,
a harness-owned clock and deterministic effect sink, fault injection, fencing,
and an internal-kernel baseline. The executable contract is
`workflow-portability.v2`. It does not exercise a live language model, a
production scheduler, LangGraph, or Temporal.

Language-model output is deliberately outside the correctness oracle. A later
optional smoke suite may record one pinned model response and replay that exact
artifact through every adapter. Model variability, provider availability, and
prompt quality must not affect replay, recovery, fencing, or effect-deduplication
scores.

## Authority boundary

| Claim | Owner | Adapter responsibility |
| --- | --- | --- |
| Tenant and workflow identity | Host runtime | Preserve exactly; never infer or broaden. |
| Command identity, canonical evidence, and request digest | Host contract | Export the complete command, recompute its digest, deduplicate identical replay, and reject changed reuse. |
| Workflow transition legality | Domain lifecycle | Invoke the shared lifecycle contract before commit and during replay. |
| Time, worker ownership, lease expiry, and fencing | Harness clock and host scheduler contract | Reject expired, stale, substituted, or split ownership at heartbeat and effect boundaries. |
| Actual effect execution and provider receipt | Harness-owned effect sink and immutable receipt ledger | Bind the full canonical command and request digest at execution; candidate events cannot certify execution, deduplication, or provenance. |
| Framework checkpoint or native state | Candidate adapter | Optimization only; never the sole authority. |
| Benchmark result | Independent evaluator | Reconcile exported history against commands, checkpoints, the clock, actual sink executions, and receipts. |

## Framework-neutral adapter contract

Every candidate adapter must support the same operations:

1. create an adapter with harness-owned clock and effect-sink dependencies;
2. apply a canonical tenant-, workflow-, and revision-scoped command;
3. inject crashes before effect execution, after execution before receipt,
   after receipt before event commit, before event commit, and after event
   commit before acknowledgement;
4. create and verify a platform-owned checkpoint;
5. destroy the original adapter and restore a fresh store using only portable
   history, its checkpoint, and the independent external dependencies;
6. expose a reconstructed snapshot; and
7. export commands and both receipt collections in their defined canonical
   order, plus ordered events.

The initial command vocabulary is intentionally small:

- start a planned workflow;
- pause and resume a running workflow;
- assign, heartbeat, expire, or reassign a worker-owned fenced task attempt;
- commit one effect from the current attempt;
- complete the workflow; and
- cancel the workflow.

This is benchmark vocabulary, not the final production task API.

## Required scenario portfolio

| Scenario | Independent observable | Required outcome |
| --- | --- | --- |
| Sequential success | Canonical event export and replayed snapshot | Gap-free history reaches the same terminal state after restart. |
| Crash before a non-effect event commit | Portable command evidence and event/receipt inventories | Pending command survives restoration; retry commits one event. |
| Effect fault matrix | Harness execution count, immutable receipt ledger, event history, and acknowledgement | Every pre/post boundary is distinguishable; recovery produces one sink call, one actual effect, one receipt, and one event. |
| Executed effect with missing receipt | Harness execution command/digest versus pending portable command | Restore requires one exact pending command; deletion, substitution, or additional claimant fails closed. |
| Changed command replay | Exported canonical command and independently recomputed request digest | Conflicting reuse and forged receipt hashes fail deterministically. |
| Lease heartbeat, expiry, reassignment, and late worker | Harness clock plus worker, token, and expiry evidence | A live lease cannot be stolen, expiry permits a higher fence, and the late worker cannot heartbeat or commit. |
| Duplicate effect under another command | Harness sink and immutable receipt binding | Second command conflicts without another provider call or actual effect. |
| Cross-tenant or cross-workflow command | Host scope versus command scope | No state changes. |
| Stale graph revision | Pinned revision versus active revision | Scheduling fails before state changes. |
| Pause, resume, and retry | Lifecycle and attempt event history | Effects are blocked while paused and retry appends a fenced attempt. |
| Cancellation during an active lease | Harness sink and lifecycle history | Late completion/effect is rejected and the sink observes no execution. |
| Verified portable restore | History digest, cursor, scope, receipt inventory, replayed snapshot, and external ledger | Fresh store reconstructs exactly; altered or missing evidence fails closed and stores do not share later mutations. |
| Reordered portable collections | Pinned command-ID and effect-ID ordering rules | Recomputed hashes do not legitimize non-canonical commands or receipts; restore/export bytes remain stable. |
| Corrupt or coordinated history mutation | Independent replay validator | Digest, scope, schema, sequence, fencing, or lifecycle violation is detected. |

Later increments must add runtime-created tasks and `all`/`any`/`quorum` joins
without weakening these scenarios. The isolated SQLite candidate and
operational measurement runner are now implemented.

## Evaluation criteria

Correctness gates are pass/fail:

- lifecycle and event-sequence preservation;
- tenant-scoped command idempotency;
- stale-worker fencing;
- independently observed at-most-once effect calls and executions;
- exact execution-to-command provenance binding, including ambiguous outcomes;
- immutable provider-receipt reconciliation;
- restart-safe replay;
- complete non-proprietary history export; and
- compatibility with existing authority and projection contracts.

Decision measurements are comparative rather than pass/fail:

- implementation surface and framework-specific code;
- required services and supported local topology;
- startup and recovery latency;
- persisted state volume;
- operational observability;
- dependency and upgrade burden; and
- credible path to bounded parallel subagents.

A candidate failing a correctness gate is not rescued by better latency or a
smaller implementation.

## Current evidence

The internal baseline demonstrates the deterministic scenario portfolio in
memory. The candidate store owns command/event state only. The
harness separately owns logical time, provider execution evidence, and an
immutable receipt ledger. Recovery exports portable command, event, and receipt
evidence, verifies the checkpoint and external ledger, and constructs a fresh
store; a regression confirms subsequent mutation of the original store cannot
change the restored one. Provider execution evidence pins the complete command
and request digest before a receipt exists, so reconciliation cannot substitute
another task, attempt, worker, or fence. Commands and command receipts are
canonically ordered by command ID; effect receipts are ordered by effect ID, and
the verifier rejects reordered-but-rehashed histories. The golden scenario suite is parameterized by the
framework-neutral adapter factory, so new candidates must register against the
unchanged suite. This proves the shared contract and independent test oracles
are executable; it does not prove the current production SQLite runtime has
implemented task attempts, leases, or crash-safe distributed scheduling.

The durable SQLite candidate runs the same golden portfolio through normalized,
immutable, explicitly versioned tables for workflow identity, canonical
commands, ordered events, command and effect receipts, checkpoints, and exact
per-workflow graph-definition pins. The SQLite schema version is `2`; graph
definition records are immutable and scope-bound to their workflow.
Existing benchmark databases are accepted only when their complete table,
column, primary-key, unique-index, foreign-key, and trigger contract matches
that version; incompatible or partial schemas fail before persistent connection
settings or workflow evidence are written. Schema detection, first installation,
and validation share one `BEGIN IMMEDIATE` transaction so concurrent first-open
factories cannot race the bootstrap. Restoration opens a new connection and
requires byte-identical portable history plus the independently verified
checkpoint and effect ledger. `BEGIN IMMEDIATE` also serializes competing
connections around validation, lease/effect execution, and evidence commit;
post-validation WAL configuration retries only SQLite busy or locked outcomes
through a bounded deadline. Multi-connection tests cover first-open races, the
WAL lock boundary, duplicate delivery, and competing lease claims.
The canonical measurement runner retains raw cold-start and recovery samples,
database footprint, evidence counts, Python and SQLite versions, journal and
connection settings, and dependency/service requirements.

The first Slice 7d.2a graph-state increment adds an exact platform-owned graph
definition with versioned nodes, transitions, reducer identities, conditional
routes, active-node state, a portable event cursor, and canonical definition
and state hashes. Conditions and reducers come from closed registries: replay
executes the matching condition and deterministic reducer for every verified
event, preserves its canonical output and digest, and incorporates all reducer
outputs into the state hash. Each reducer must be self-contained and expose
exactly three ordinary positional parameters with no runtime defaults. Its
canonical implementation-syntax digest participates in the definition hash;
an executable change therefore invalidates the persisted pin even if its
human-assigned version label is unchanged. `GraphStatePortabilityAdapter`
admits new commands only when replay of independently verified portable history
reconstructs a compatible route. Caller-supplied projection fields are never
route authority. The adapter then delegates durable
authority and effect handling to the SQLite portability boundary. Every graph
view is rebuilt from independently verified portable history; graph state is
never an approval, receipt, effect, or lifecycle authority. The exact
definition ID, state version, and hash are immutably pinned per workflow and
checked before route admission, checkpoint mutation, and restoration, so a
same-ID/same-version definition change cannot reinterpret prior evidence. The candidate runs
the unchanged golden portfolio and the canonical measurement runner, while
graph-specific tests reject unknown versions, nodes, ambiguous or missing
routes, and substituted portable snapshots.

Initial graph-pattern evidence:

| Pattern | Disposition | Evidence and friction |
| --- | --- | --- |
| Explicit nodes and conditional transitions | Adopt | Makes pause, resume, terminal cancellation, and post-cancellation effect reconciliation routes inspectable and deterministic. |
| Named deterministic reducers | Adopt | Every portable event selects a registered reducer, whose canonical output and digest contribute to the graph-state hash. Unknown reducer identities fail closed. |
| Closed condition registry | Adopt | Registered conditions execute against portable event types and operations; unknown identities fail closed, and committed versus reconciled effect branches have separate evidence. |
| Immutable definition pin | Adopt | Workflow-scoped definition ID, state version, and exact hash are checked during routing, checkpointing, and restoration. |
| Active-node and checkpoint cursor | Adopt as projection | Useful for execution diagnostics, but must match the independently verified portable history hash and event cursor. |
| Graph-native mutable checkpoint or serialized runtime object | Reject | Would duplicate authority and prevent clean recovery without a live framework object. |
| Adapter-local command or effect semantics | Reject | The shared lifecycle, command digest, SQLite evidence, effect sink, and receipt ledger remain authoritative. |
| Current sequential command vocabulary | Revise later | It proves deterministic routing but cannot yet express runtime-created nodes or `all`/`any`/`quorum` joins without a new shared contract version. |

Measurement schema `workflow-portability-measurements.v2` now retains the graph
strategy state hash and incremental source
modules/line count alongside raw latency, database growth, evidence counts,
dependencies, services, and connection settings.

Conditional graph routing is now executable, but runtime-created tasks, joins,
and the first-party durable-history strategy remain unmeasured. No
orchestration-pattern decision should be recorded until both strategies run the
complete correctness and operational matrix.

## Non-goals

- selecting a framework from documentation or preference;
- using model quality as a framework score;
- making benchmark state a production authority;
- adding parallel execution, dynamic joins, or delegation;
- introducing LangGraph, Temporal, or another workflow-vendor package, SDK,
  runtime, service, or persisted representation; or
- replacing current approval, effect, completion, or compatibility ledgers.

## Next increments

1. Persist the internal baseline through an isolated SQLite adapter and measure
   restart behavior against the same exported-history oracle. **Implemented.**
2. Add a first-party graph-state strategy without allowing graph state to
   become authoritative. **Initial sequential graph increment implemented.**
3. Add a first-party durable-history strategy and record its operational and
   deployment requirements.
4. Run the complete scenario and operational matrix.
5. Publish the pattern-adoption ADR with evidence, rejected alternatives,
   migration boundary, and rollback strategy.

Run the local measurement artifact with:

```bash
python -m scripts.ops.run_workflow_portability_measurements \
  --output tmp/workflow-portability-measurements.json \
  --samples 5
```

The command performs no model or external-service calls.
Each invocation creates an isolated benchmark-data subdirectory, so rerunning
the command with the same output path cannot reuse or overwrite prior SQLite
workflow evidence.
