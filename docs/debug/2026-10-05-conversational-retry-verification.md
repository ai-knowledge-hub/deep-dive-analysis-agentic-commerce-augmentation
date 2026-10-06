# Conversational retry verification — Issue 164

Date: 2026-10-05
Status: local implementation and verification; production rollout unverified
Base: merged PR 163, main commit `933082cafba533e5d93c68705d827107acdcd9a9`
Branch: `codex/164-governed-conversational-retry`

## Behavior and admission

One exact failed action can receive an immutable v5 `same_action` retry proposal
on a quiescent planned, running or paused sequential run in plan_only or
auto_execute_safe mode. Explicit IDs, sequences and a uniquely failed action
identify the source. Multiple, unresolved, checkpoint, alternative-strategy and
combined mutation requests do not create proposals. Model-selected intent cannot
enter the control path. Preparing, dismissing or reloading creates no action,
approval or effect; only the durable proposal is written.

The proposal pins normalized inputs, complete live registry semantics, policy,
harness, authority, revision, budget state, source and related effect evidence,
linked validation/experiment evidence, verified completion and full private
control state. It admits read/recommend and the current durably fenced governed
effect classes; unfenced write_low_risk effects require separate recovery.
Failed/completed/canceled runs, worker leases, executing actions, unresolved run
effects, any committed effect in the related retry family, unverifiable completion
or incomplete required linked evidence block new admission. A failed projection
cannot erase an ancestor, child or sibling's committed effect. Beta exclusions
are unchanged.

Confirmation uses a schema-v3 `operator-retry-api` / `operator-retry-web-bff`
assertion bound to authenticated human, tenant, run, failed source, strategy and
proposal ID/digest. Read, lifecycle and action-review assertions do not suffice.
Equivalent signed human bearer authority retains the existing API path. The
final BEGIN IMMEDIATE transaction checks live human access, durable proposal,
expiry, source, event head, private snapshot and live preflight. It allocates the
new sequence/ordinal/effect identity under the same lock and commits the child,
two human audits, actual workflow projections and immutable receipt together.
Nested action insertion joins through a savepoint; any outer failure fully rolls
back all writes, including final commit failure. A later unrelated writer cannot
commit abandoned retry writes.

The child is proposed with no copied approval, outcome or canonical result link.
Fresh exact approval and current worker policy, revocation, lease, cancellation,
budget and single-use effect checks remain necessary. Confirmation executes
nothing, changes no run status/mode, starts or resumes no work and resets no
budget. Receipt replay checks current human access before fresh eligibility or
expiry and remains available after subsequent approval, execution or cancellation.

## Reachable surface and invariant ledger

| Surface / actors | Protected outcome and enforcement | Independent evidence |
| --- | --- | --- |
| Local classifier, model, target resolver | Read-only model output; exactly one resolvable source, no combined mutation. | Explicit intent, proposal/action/event/approval counts and target matrices. |
| Browser BFF and API | Authenticated human, tenant/run/action/strategy/proposal scope; current role and active principal. | Ten claim substitutions, read-assertion refusal, changed live membership. |
| Application preparation and completion reader | Full private state, authoritative completion, registry, evidence, policy and budget admission. | Eight fenced drift dimensions, persistent missing/throwing completion reader, final-lock completion/registry/validation drift and exhausted budget. |
| Durable effect/validation stores, direct recovery | A failed projection never authorizes repeating a committed related effect. | Real started/uncertain/succeeded effect records, legacy retry ancestor, successful retry child before background status reconciliation. |
| Retry/action/audit/workflow writers | One outer transaction; unique under-lock sequence, ordinal and effect key. | Competing confirmations, exact replay, later independent ordinal, insertion/projection/final-commit faults with later unrelated writes. |
| Worker, status derivation and reconciliation | Only receipt-backed pending retries hold their exact source failure; stale derivation cannot erase a new child. | Real default worker and fresh approval consumption; unreceipted/unrelated failures; retry commits between derivation and projection; existing cancellation race. |
| Persistence, migration and history readers | Immutable receipts/audits; old contract bytes/cursors remain valid; historical replay does not depend on mutable current action state. | Nine update/delete/replace probes, actual migration 061 upgrade with v1-v4 records/cursor replay, fresh process receipt verification. |
| Runs and Interventions | Exact recorded outcome, same identities, explicit confirmation and fresh-approval guidance. | Actual mock-auth browser flow and durable SQLite counts, frontend components and receipt/audit deduplication tests. |

The eight rows bound the review's material invariants; each has executable
mechanism evidence. They do not constitute exhaustive certification of the
platform or every natural-language request.

## Counter-review and resolved failures

The strongest initial assumption was that appending a retry action would suffice
for the existing worker. Default worker orchestration synchronizes completion
and derives run status from all failed actions, so the original failed source
made the run terminal before the child could receive approval. A verified v5
receipt now holds only its exact source failure while its child is proposed,
approved or executing. Unreceipted and unrelated failures remain effective;
harness stopping conditions and full completion membership still see the
original source. Finished/rejected/failed children release the hold. Retry
success never itself satisfies the original required task or goal completion.

An initial run-lease implementation of status reconciliation rejected an
existing valid cancellation interleaving. The final implementation preserves the
previous lifecycle compare-and-swap and atomically compares the observed action
ID/status set under the final database lock. A retry committed after derivation
adds an action and prevents the stale failure projection from committing;
cancellation still wins independently through the existing status fence. This
is a bounded action-set fence, not distributed attempt fencing.

A second harmful narrative used a successful retry child's receipt and then
requested another retry of its still-failed original source before background
run-status reconciliation. The initial ancestor-only effect check admitted that
proposal. The final check follows related retry descendants and siblings as well
as ancestors. The new test first reproduced the unsafe admission against real
approval/effect/validation persistence, then passed after the family check.

The first model-intent mutation survived because the test observed only absence
of a child/proposal: another source fence independently prevented its write.
The corrected oracle also checks the read-only returned intent and durable
proposal count, covering the authority boundary even when a later fence blocks.

Alternate paths inspected include direct retry strategies, guarded sequence
allocation, action review and approval normalization, cancellation, worker
pre-effect consumption, effect reconciliation, completion synchronization,
workflow audit dual-write, mixed command history and earlier migration views.
The admission-only family fence still allowed two siblings to be confirmed and
freshly approved before either executed. The real default-worker regression
reproduced two provider calls and two succeeded effects. The final pre-effect
`BEGIN IMMEDIATE` transaction now resolves the family and checks its durable
effects before reserving a new start. It uses immutable v5 source/child receipts,
legacy retry keys and committed effect identities, follows both directions and
terminates cycles without truncating the family. A started, uncertain or
succeeded related effect rejects the new authorization without consuming its
approval, reserving another effect or writing a start audit. Current exact-effect
replay retains its existing reconciliation outcome before the family check.
Only the provider boundary is replaced in the worker regression; approval,
effect, result, receipt, worker and reconciliation persistence are real.

The effect-start insert has one production writer in `approval_ledger`; normal
runtime execution calls it before marking the provider invoked. Direct legacy
recovery produces retry identities consumed by the same transaction. Effect
completion and reconciliation do not start new effects. An isolated extraction
of the unchanged exact replay outcome into the existing persistence helper keeps
the ledger within its file-size gate. No new migration or frontend change was
required for the rereview fix. Older worker binaries lack the new family fence
and must be replaced before enabling conversational retries.

No unresolved blocking finding remains within this bounded slice.

## Bounded failure-space evidence

| Dimension | Tested coverage / boundary |
| --- | --- |
| Supported source/mode matrix | 6/6: planned/running/paused × plan_only/auto_execute_safe. |
| Dangerous source states | 7/7 named cases: created, planning, failed, completed, canceled, cancelled, unknown. Unsupported mode admission is additionally enforced by direct inspection. |
| Target/command ambiguity | 9/9 named multiple, shorthand, unknown, batch and combined requests. The existing exact review resolver suite remains applicable. |
| Assertion substitution | 10/10 named schema/audience/issuer/action/human/tenant/run/strategy/command/digest substitutions, plus read assertion refusal. |
| Fenced state drift | 8/8 named source inputs, revision, budget, policy, mode, lease, terminal status and membership changes; 3/3 final-lock completion/registry/validation interleavings. |
| Completion verification failure | 2/2 persistent missing or throwing reader cases. |
| Source effect states | 3/3 committed started/uncertain/succeeded states; ancestor and successful-child mechanisms separately exercised. |
| Atomic write faults | 5/5 named action/audit/receipt/workflow projection/final commit boundaries, including subsequent unrelated writer. |
| Immutable records/audits | 9/9 update/delete/replace operations across proposal, receipt and linked audit. |
| Concurrent delivery/recovery | Competing fresh confirmations, concurrent exact replays, independent later retry ordinal, cancellation both orders, retry crossing stale reconciliation, source replay after later changes. |
| Compatibility/restart | Fresh installs across fixtures; actual pre-061 upgrade retaining four old contracts and cursor/replay; separate-process verification. |

Six process-local semantic mutants were applied without modifying source or
production data: remove source-effect admission, permit model retry intent, hide
all failed actions instead of verified receipt-held sources, let nested action
creation commit its caller transaction, remove the final action-set comparison,
and omit related retry descendants from effect checks. All six targeted tests
failed as intended (6/6 detected after oracle correction). This is a targeted
mutation portfolio, not an exhaustive mutation score.

The sibling-execution rereview adds 17 cases: 12/12 combinations of committed
effect state (started/uncertain/succeeded), winning sibling (first/second), and
identity representation (original keys/both keys rewritten before fresh
approval); 2/2 timing boundaries (a related commit after application validation,
and two simultaneous starts under one valid lease); 2/2 legacy/independent
same-input controls; and 1/1 real default-worker provider-call regression.
Independent oracles count durable effects and start audits, preserve the losing
approval and original source, and count provider calls. Started and uncertain
exact replays still require reconciliation. Removing the final fence, ignoring
started/uncertain effects, and omitting immutable receipt relationships each
make the focused tests fail (3/3 additional semantic mutants detected: 16, 11
and 6 failing cases respectively). These mutations were process-local; source
and production data were unchanged. The earlier pinned legacy allocation test had
asserted that both unique sibling identities could start effects. It now still
proves independent ordinals, keys and fresh approvals, then verifies that only
one effect starts and the other approval remains unconsumed. Its pinned node
identity and the security schema-v1 membership remain unchanged. Five isolated locked-query probes passed for transitive root membership,
workflow isolation, tenant isolation, retention of a rewritten committed key
and cycle termination (5/5). These exercise the real query against synthetic
SQLite relationship rows, rather than the full approval/provider path. A
500-action transitive chain, the conversational admission bound, resolved in
0.030 seconds in that local probe; a 5,000-action legacy chain took 2.965
seconds. This is a local timing observation, not a production performance SLA.
The new tests do not certify distributed workers or every legacy graph shape.

## Verification results

Initial issue 164 build verification, before the sibling-execution rereview:

- Focused retry/cancellation suites: 97 passed, including 76 new retry cases.
- Final full backend suite, including the successful-child repetition regression:
  1,510 passed, 1 skipped in 561.90 seconds. The skipped semantic-alignment test
  requires a live GOOGLE_API_KEY and remains unverified.
- Final frontend verification: 165 tests in 54 files, lint, typecheck, language,
  complexity and production build passed.
- Lint, architecture, bloat, entrypoint, docs, safety and security gates passed.
- `git diff --check` passed.

Sibling-execution rereview: 17 focused cases passed; the expanded retry and
effect-authorization/migration portfolio passed 135 cases before the replay
helper extraction. The final effect/recovery/receipt portfolio passed 90 cases
after the helper extraction and legacy-test correction. Final lint, architecture,
bloat, entrypoint, safety, security, documentation and diff checks passed. The
final full backend run passed 1,527 tests with 1 skipped in 615.22 seconds.
The existing skipped semantic-alignment case requires a live GOOGLE_API_KEY;
that live-provider partition remains unverified. No frontend files changed
during this rereview; the earlier 165-test frontend verification remains the
applicable build evidence.

CI portability correction (2026-10-06): the fresh-process receipt test used a
repository-relative `.venv/bin/python`, which is absent on the GitHub Actions
`setup-python` runner. It now launches `sys.executable`, preserving the actual
new process and durable receipt-digest assertion. Running the focused test from
`runtime-path:/private/tmp` with the repository on `PYTHONPATH` reproduced the same missing
interpreter failure before the fix and passed afterward (1 passed in 3.28
seconds), without relying on a working-directory `.venv`.

Safety VT-03 includes exact supplementary retry nodes. Security's immutable
schema-v1 verification contract remains unchanged; its gate runs the pinned
baseline, while the new assertion and effect-family tests run in the focused
and full backend suites. This evidence supplements current SEC-06/SVT-06 without
closing planned controls, changing required identifiers or releasing beta blocks.

## Browser evidence and practical limits

An isolated synthetic SQLite database and local mock-auth BFF/API verified:
request → exact same-action preview → dismissal/reload without action creation →
explicit confirmation → one proposed child → separate approval proposal → fresh
approval → Runs/Interventions navigation and reload. Direct database inspection
recorded one unchanged failed source, one freshly approved child, one retry
receipt, unchanged planned run status and zero effect executions. No provider
was called by the browser. The default-worker test exercises real approval and
effect persistence with only the external provider call replaced.

Both surfaces reload the same proposal and receipt identities. Interventions
suppresses only the exact lifecycle audit already represented by a committed
retry receipt, retains unrelated/unavailable-history audit evidence, and marks
retry preparation as medium risk. Screenshots were captured outside the repo.
The isolated mock session's existing raw client/brand selector requests returned
403 and displayed a development badge; the authenticated conversational BFF,
retry, approval, receipt and run-scoped navigation requests succeeded. This
fixture did not verify live Clerk login or the legacy tenant-selector auth path.

Migration 061 and updated backend/workers must deploy before the new UI. Older
readers retain v1-v4 views; older workers cannot apply v5 receipt-backed failure
holds and may conservatively mark a source-failed run failed. Terminal revival,
independent task-attempt replacement, broader recovery strategies, production
publishing, distributed stop propagation and compensation remain outside scope.
A successful retry does not rewrite original failure or required completion
membership. Production deployment, live provider credentials and distributed
worker behavior are unverified.
