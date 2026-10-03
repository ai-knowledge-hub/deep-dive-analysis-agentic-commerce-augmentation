# Issue 158: governed conversational resume verification

Date: 2026-10-02. Local branch: `codex/158-governed-conversational-resume`.
Comparison base: `54f9a66c3db9bd1983a08db2e99963359d2f94b3` (merged PR 157).
Scope: Phase 2.3a, sequential compatibility runtime. No commit, push, PR, or
deployment was performed. This report is implementation evidence, not a new
safety/security certification or a replacement for the canonical plan and ADR.

## Surface and authority map

Human chat -> authenticated same-origin BFF -> scoped operator gateway ->
immutable proposal -> separate human confirmation -> existing command service
-> SQLite commit lock -> run status, audit events and immutable receipt.
Runs and Interventions read the same tenant/run-scoped paginated projection.

The model selects only closed intent and server-created fact identities. It
cannot select authority, scope, mode, command parameters, status, or approval.
The command BFF uses a distinct signing secret and binds exact type, proposal
ID/digest and authenticated scope. Membership is rechecked inside the write
lock; the ledger checks an active tenant-bound human principal.

The compatibility start writer and later runtime scheduler remain separate
paths. Confirmation changes only eligibility; runtime approval and pre-effect
checks still control capability execution. The approval/effect ledger, linked
validation job/result readers, completion read model, live registry and harness
stopping rules feed the final snapshot/preflight fence. Registry/policy/harness
pins and current run inputs are preserved. Migration 057 adds resume tables and
mixed read views; existing pause tables, immutable bytes and digests survive.

## Invariant ledger

| Invariant | Enforcement / commit point | Independent observation |
| --- | --- | --- |
| Proposal and dismissal cannot resume a run | Separate confirmation endpoint | Paused DB rows and zero receipts before the browser click |
| Only paused supported modes admit resume | Domain contract, preflight, SQL checks | Explicit expected mapping: plan-only to planned, safe mode to running; illegal sources rejected |
| Read or pause authority cannot confirm resume | BFF type/scope assertions and role checks | HTTP rejection plus unchanged run and absent receipt |
| Changed control evidence invalidates uncommitted proposals | Snapshot/preflight rebuilt under `BEGIN IMMEDIATE` | Injected mutations produce conflict with no command audit or receipt |
| Unverified completion cannot admit a new resume | Successful-reader flag in the private snapshot and proposal/locked preflight | Real authoritative decision corruption blocks proposals and final admission even with a stable failed-read digest |
| Starts cannot resolve unrelated stopping conditions | Bounded scan across all starts; later same-run exact clear required | Compatibility start plus conversational pause retains policy, budget and unknown markers |
| Busy or unreconciled effects cannot be resumed | Lock, executing-action and started/uncertain-effect preflight | Real effect fixtures remain unchanged and proposal is absent |
| Resume cannot manufacture approval or repeat a committed effect | Status-only update; unchanged pre-effect boundary | Subsequent runtime refuses missing canonical approval; succeeded effect/fulfilled approval preserved |
| Unrelated stops cannot be cleared | Current harness evaluation and insertion-ordered control history | Other stop markers survive; clear event names only the exact operator-pause event |
| Run, audits and receipt form one outcome | Single SQLite transaction | Receipt insertion fault rolls back status and every new event |
| Exact retry returns one outcome despite later state | Durable receipt replay before admission checks | Two confirmations share receipt identity; later pause stays paused; fresh process returns original digest |
| Mixed history survives reload and migration | Verified projection and stable scoped cursor | 16 mixed records paginated; v1 pause bytes/cursor/replay unchanged after actual migration application |
| Navigation cannot replace the new run with an old confirmation/read | Confirmation generation, selected-read generation and active selection scope | Navigation during receipt-history refresh suppresses the old callback; delayed detail reads cannot replace the new selection |

All 13 modeled invariants have executable evidence, including the October 3
review corrections below. This is a bounded model,
not exhaustive coverage of the platform's future workflow kernel.

## Failure space and counter-review

- Legal compatibility edges: 2/2 tested. Illegal source partitions: 7/7 tested
  (`created`, `planning`, `planned`, `running`, `completed`, `failed`, `canceled`).
  Unsupported mode samples: 5/5 tested (including empty, case variant and future mode).
- Snapshot/preflight change classes: 17/17 selected classes tested: action inputs,
  budget, authority, mode, revision, policy pin, registry pin, cancellation, busy
  lock, membership, completion projection, live registry, approval, effect,
  validation job, validation result and completion evidence beyond the display
  cap. Completion and live-registry races use
  synthetic adapters; other evidence changes use isolated SQLite state.
- Authority substitutions: 9/9 selected cases rejected: wrong command body,
  pause assertion, read assertion, bearer without write scope, other run, digest,
  other principal, tenant and expired proposal.
- Stop partitions: exact operator pause plus 4 recorded unrelated conditions
  and 3 live harness conditions tested. Effect partitions: started, uncertain,
  succeeded and absent exact action approval tested against real ledger fixtures.
- Schedules: 5/5 selected schedules exercised: concurrent exact confirmations,
  concurrent distinct proposals, resume -> later pause -> old resume retry,
  navigation during confirmation-history refresh, and an old detail read arriving
  after navigation. The shared Runs reader now clears old context on selection,
  fences late reads/polls and keeps URL selection separate from list refreshes.
  Recovery/fault points: 2/2 selected points exercised: receipt insertion failure
  and lost acknowledgement followed by fresh-process replay.
- Compatibility cases: pre-057 pause evidence with actual additive migration,
  mixed post-057 pagination, and legacy pause retry tested. Deployment ordering
  and rollback-reader limits are documented in the deployment guide.

Five temporary semantic source mutations were run against the tests and then
restored. Removing the final snapshot comparison admitted changed action inputs;
removing the final preflight digest comparison admitted live-registry drift;
jointly removing executing-action and unreconciled-effect checks admitted both
started and uncertain effect proposals. Removing the post-history confirmation
generation check invoked the old refresh callback after navigation; removing the
detail-response fence displayed the old run's running state in the new selection.
Tests detected 5/5 harmful mutations (six failing cases). Restored backend and
frontend focused suites passed. This score applies only to those five selected
mutations.

The counter-review's strongest assumption is that a control-plane status change
can safely express sequential resume eligibility. Real effect and runtime tests
show it does not bypass the existing effect gate or reset a prior effect. It
does not prove worker interruption, worker continuation, distributed fencing,
external-operation propagation or compensation; SEC-17 and Phase 3 retain those
responsibilities. Bounds above 500 actions or control events are
blocked in code; stress/soak behavior at those limits is not certified here.

## Review corrections: 2026-10-03

The review identified two gaps in the original failure model: repeated failed
completion reads could produce a stable digest, and an unrelated compatibility
start could hide an unresolved stopping marker. Regressions reproduced both
against isolated SQLite state before the changes.

Resume now requires a non-missing result from the scoped completion reader at
proposal creation and again in preflight under the final write lock. Read-only
integrity warnings remain available. Verified legacy views remain compatible
without inventing a completion decision. Old uncommitted unsafe proposals fail
final admission; already committed receipts still replay before admission,
including when the route's earlier receipt read misses a concurrent commit.

The stop scan no longer treats `run_started` or `run_resumed` as a resolution
boundary. Later same-run clear events resolve only the named stop ID. It fails
closed when more than 500 control events prevent complete bounded verification;
a start cannot make that history complete. This is a conservative admission
bound, not a claim that large histories are automatically repaired or compacted.

The additional portfolio contains **19 regression cases** with durable status,
receipt and audit oracles. It covers 3/3 selected completion fault points
(proposal creation, before confirmation and under the commit lock); 2/2
unverified-reader partitions (missing and exception); 2/2 verified legacy modes;
2/2 receipt replay paths; 3/3 unrelated-stop samples; 4/4 resolution relationships
(exact later same-run clear, another event ID, a clear before its stop, another
run); and 2/2 history-bound partitions (500 complete events and a hidden old
stop beyond the read bound). A separate historical-producer case verifies that
changed corrupt authority cannot commit through an unchanged failed-read digest.

Two temporary semantic mutations were detected and restored: removing the
completion admission guard caused three regression failures, and restoring the
start boundary caused five. Mutation detection was **2/2** for these selected
defects. This adds evidence for these admission controls; it does not extend the
prior production-worker, external-effect or authentication claims.

October 3 verification:

- Full backend `make test`: **1,235 passed, 1 skipped** in 487.87 seconds.
  The skipped real-embedding semantic alignment test still requires a Google
  API key and manual execution.
- Final focused backend: **111 passed**, including all 19 new regression cases.
- Lint, architecture, bloat, script entrypoint, documentation, safety and security
  traceability checks passed; the traceability gates executed their implemented
  verification nodes. `git diff --check` passed.
- These corrections changed backend admission and documentation. The October 2
  frontend/browser results below are historical evidence; no new frontend or
  production rollout certification is claimed. Changes remain uncommitted.

## Verification results: 2026-10-02

- Final full backend `make test`: **1,216 passed, 1 skipped**, 491.38 seconds,
  including the full private completion-evidence fence and all three
  derived-authority race cases. The permanently skipped test is real semantic
  alignment with live embeddings, marked for manual execution with a Google API key.
- Final focused backend: **92 passed**, covering resume, real approval/effect
  composition, historical command contracts and operator API behavior.
- `make web-verify`: passed lint, type checking, **144 tests in 51 files**, UI
  language, complexity checks and optimized production build.
- Repository lint, architecture, bloat, script entrypoint and documentation
  gates passed. Safety and security traceability gates passed with their
  implemented verification nodes executed. `git diff --check` passed.

The local in-app Browser used an isolated migrated SQLite database and mock
authentication with real BFF assertions. Proposal creation and dismissal left
both runs paused with no receipts. Reload restored the dismissed proposal.
Explicit confirmation produced `planned` and `running` respectively. Runs and
reloaded run-scoped Interventions showed identical proposal/digest/receipt
identities for each run. Direct DB inspection found zero actions and zero effect
executions after both confirmations. Local servers were stopped after checking.

Browser receipt identities:

| Mode | Run | Receipt | Recorded outcome |
| --- | --- | --- | --- |
| `plan_only` | `6ce298e4-efa3-439b-a21e-8e1facd2d702` | `cb6c0232-8201-40dc-92de-2359ba603138` | `planned` |
| `auto_execute_safe` | `2c4ff6eb-a339-4c85-8acf-495e61cc0788` | `ed1fed6c-4fd2-49b4-8ab8-775e5509db11` | `running` |

These identities are from the final browser pass after the navigation fixes.
Switching away from the pending plan-only proposal cleared its chat and command
context in the safe-mode run. Switching back restored the exact plan proposal;
both confirmations and their matching Runs/Interventions records were then
checked against the final code.

The test browser's client/brand sidebar reads returned 403 for the seeded
operator, while run reads, chat, confirmation and command history succeeded.
That ancillary sidebar authorization behavior is outside this change. Production
Clerk authentication, production migration/rollout and live worker propagation
remain unverified. No production-ready deployment claim follows from the local
browser run or production build.
