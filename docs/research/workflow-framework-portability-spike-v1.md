# Workflow Framework Portability Spike v1

Status: snapshot
Last verified: 2026-09-19
Baseline: `origin/main@c4b6a5b`
Issue: [#142](https://github.com/ai-knowledge-hub/deep-dive-analysis-agentic-commerce-augmentation/issues/142)

## Decision question

Which orchestration approach should carry the platform from the current
sequential SQLite runtime into durable task attempts and later bounded
parallelism without making framework-native state authoritative?

The candidates are:

- the internal workflow kernel;
- a LangGraph-style adapter; and
- a Temporal-style adapter.

This document records the independent benchmark contract and evidence. It does
not select a framework. A later ADR must make that decision from executable
results and state the supported deployment envelope.

## Evidence boundary

The first increment is deterministic and local. It defines a common adapter
port and factory, canonical revision-pinned command evidence, immutable events,
command and effect receipts, replayable history export, verified checkpoints,
a harness-owned clock and deterministic effect sink, fault injection, fencing,
and an internal-kernel baseline. The executable contract is
`workflow-portability.v2`. It does not exercise a live language model, a
production scheduler, LangGraph, or Temporal yet.

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

Later increments must add runtime-created tasks, `all`/`any`/`quorum` joins,
SQLite persistence, and operational measurements without weakening these
scenarios.

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

The internal baseline currently demonstrates the deterministic scenario
portfolio in memory. The candidate store owns command/event state only. The
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

LangGraph-style and Temporal-style evidence remains unmeasured. No framework
decision should be recorded until both run the unchanged correctness suite and
their operational assumptions are measured explicitly.

## Non-goals

- selecting a framework from documentation or preference;
- using model quality as a framework score;
- making benchmark state a production authority;
- adding parallel execution, dynamic joins, or delegation;
- introducing a permanent Temporal service; or
- replacing current approval, effect, completion, or compatibility ledgers.

## Next increments

1. Persist the internal baseline through an isolated SQLite adapter and measure
   restart behavior against the same exported-history oracle.
2. Add a minimal LangGraph-style adapter without allowing graph state to become
   authoritative.
3. Add a minimal Temporal-style adapter and record its service and deployment
   requirements.
4. Run the complete scenario and operational matrix.
5. Publish the decision ADR with evidence, rejected alternatives, migration
   boundary, and rollback strategy.
