# Conversational effect reconciliation verification — Issue 166

Date: 2026-10-06
Status: local implementation and verification; production rollout unverified
Base: merged PR 165, main commit `813980b24ae272d4565e23b566146eff29114788`
Branch: `codex/166-conversational-effect-reconciliation`

## Behavior and admission

Slice 2.5b records an existing governed effect outcome after one exact human
selection, evidence preview and separate confirmation. It does not call a
capability, poll a provider, create an action or approval, or reserve another
effect. Model-selected intents and supplied outcomes cannot enter this path.
All explicit action IDs and sequence references must resolve to one target.

| Dimension | Admitted | Blocked or preserved |
| --- | --- | --- |
| Capability | Frozen request_synthetic_validation or promote_variant_lab contract | Unsupported or unverifiable start/contract |
| Effect | started, uncertain; succeeded with consistent executed action | Missing start, conflicting succeeded projection, invalid historical approval |
| Action | executing, failed, executed in this run | Other states, unresolved/batch targets |
| Run | planned, running, failed, paused, completed, canceled/cancelled | Unsupported state; any retained worker token or another executing action |
| Control | Verified completion reader, complete bounded action and stop history | Unverifiable completion, more than 500 actions/control events |
| Terminal state | Record late outcome on paused/completed/canceled run | Preserve its status and state; never grant execution authority |
| Unresolved stop | Verify event-specific clear markers across legacy starts | Preserve control state without clearing unrelated markers |
| Validation auto_run=true | Bound completed job plus matching durable result | Missing, contradictory or cross-scope job/result |
| Validation auto_run=false | Bound created job under frozen inputs | No requirement that a provider has finished |
| Lab effect | Exact bound governed local-effect receipt | Projection or user/model assertion alone is insufficient |
| Historical authority | Approval valid at immutable pre-effect start, original frozen contract | No reauthorization from current registry/policy or a fresh approval |

Approval expiry after a then-valid effect start and current policy/registry drift
do not prevent recording the original outcome. The private snapshot pins the
complete action set, membership, approval/effect state and verified completion;
the proof also pins the exact start, approval envelope, effect identity,
adapter evidence/result and current action projection. Even a newly valid change
to evidence requires a fresh review.

## Producer, writer and reader map

| Surface | Authority and effect | Consumer/commit boundary |
| --- | --- | --- |
| Local intent and exact action resolver | Human text selects one existing target; model classification never controls mutation | Shared operator gateway, read-only preflight and durable v6 proposal |
| Browser confirmation BFF | Authenticated session; schema-v4 operator-reconciliation-api/operator-reconciliation-web-bff assertion | API verifies human, tenant, run, action, execution, proposal ID/digest |
| Direct API confirmation | Signed human with operator_reconciliations:confirm or agent_runs:write plus current operator membership | Same application confirmation and persistence transaction |
| Original worker effect start | Original approval, immutable authorization snapshot and frozen executable contract | Historical authorization and receipt verifiers; no new pre-effect authorization |
| Validation/local-effect adapters | Tenant-bound durable job/result or governed local receipt | Read-only discovery and independent frozen receipt verification |
| Human reconciliation writer | Final BEGIN IMMEDIATE, current access, exact durable proposal, expiry, private snapshot, preflight, revision/event head/lease | Joined effect completion, approval fulfillment, action/link, run projection, audits and conversational receipt |
| Background/direct reconciliation | Existing recovery entry point, preserved direct-command compatibility | Winning background outcome invalidates stale proposal; fresh review can acknowledge consistent existing success without fulfilling twice |
| Retry admission and worker family fence | Related started/uncertain/succeeded effects remain family blockers | Recovery does not create a retry or distinct execution identity |
| Cancel/pause/completion and legacy starts | Current control state and event-specific unresolved stops | Recovery preserves terminal/control state; action success never infers objective completion in chat |
| Runs, Interventions, command-history API | v6 union views and independently verified immutable receipts | Same durable IDs/digests after navigation/reload; current run display separate from recorded receipt state |
| Migration 062 and older readers | Additive tables/triggers/views, immutable scope-bound audits | v1–v5 bytes and cursors unchanged; old views remain available |

Effect completion, run restoration and audit creation now join their caller's
transaction through savepoints. Standalone ownership still commits/rolls back
its own transaction. Nested integrity failures retain their original exception.
Human confirmation requires every write and the final commit to succeed together;
a later unrelated writer cannot commit abandoned recovery writes.

## Invariants and independent oracles

| Invariant | Enforcement | Executable oracle |
| --- | --- | --- |
| Exact human authority and selection | Closed local intent, all-reference resolver, command-specific assertion/current access | No proposal/effect writes for ambiguous text or model intent; claim and direct-scope substitutions |
| Historical evidence supplies outcome authority | Frozen start/approval/contract and adapter receipt verification | Invalid start/scope/result rejected; approval expiry and current registry drift still reconcile |
| Preparation never executes | Read-only discovery; proposal is the sole new durable object | Independent table counts and forbidden capability callable |
| Commit rechecks live evidence/control | Owned write lock, private snapshot and recomputed preflight | Evidence/role/revision/action/lease/cancellation changes between route read and lock yield no receipt |
| No partial recovery | Savepoint composition and owned final commit | Seven required-write faults plus final commit error; original exception, unchanged ledger/action and no pending writes after unrelated writer |
| Control state and other failures survive | Guarded complete action-state derivation and event-specific stop scan | Six run statuses, unrelated failed action, policy stop across legacy start, zero objective-completion inference |
| One consistent recording/replay | Unique execution receipt, exact proposal replay after current access, immutable human audits | Concurrent competing/duplicate delivery, background winner, immutable records and fresh-process restart with sys.executable |
| Operator projection is truthful | Separate effect/action/run fields, evidence anchors, receipt integrity verification | Runs/BFF/Interventions component tests and actual browser navigation/reload with direct SQLite checks |
| Existing contracts remain readable | Additive migration and old views | Actual v1–v5 records survive migration with identical JSON/digests/history cursors |

### Bounded failure space

The focused reconciliation suites cover both durable adapter families; all three
supported effect states and all three supported action states through explicit
reachable pairs; six run-status partitions; both frozen validation auto_run
partitions; 13 browser-claim substitutions and six direct-scope partitions;
nine ambiguous/combined selection cases; ten final-lock changes; seven required
write-fault points and one final-commit failure; nine immutable mutation cases;
ten coordinated receipt rewrites; two confirmation schedules and a background
winner; and fresh-process replay after expiry/state change with access revocation.
These are bounded coverage counts, not an exhaustive Cartesian-product claim.

Four deliberately harmful runtime mutations were tested in disposable pytest
plugins, without changing checkout sources:

| Mutation | Independent detection | Result |
| --- | --- | --- |
| Replace final evidence/control reload with admission-only state | Valid result-payload change between route read and lock unexpectedly returns 200 | Killed |
| Remove final access reload, membership and private authority fence together | Downgraded operator unexpectedly returns 200 | Killed |
| Make joined effect completion commit the caller transaction | Required receipt-write fault exposes escaped transaction | Killed |
| Invoke a capability during recovery | Forbidden capability oracle fails before recording | Killed |

Mutation score is 4/4 for these selected consequence-bearing mutants. The first
probe initially patched the implementation module but not its exported adapter
alias; that did not execute the mutation. Correcting the harness applied the
actual mutation and demonstrated the expected failures. Removing one redundant
check alone is not evidence that a harmful mutation survives.

## Browser evidence

An isolated SQLite fixture had one uncertain approved validation effect, one
completed bound provider job/result and a failed action with no worker lease.
The actual Runs browser flow was:

1. Ask “Reconcile action 1”; review original approval, execution, frozen-start and
   exact job/result/evidence anchors while the effect/action remain unchanged.
2. Click “Confirm reconciliation”; observe effect succeeded, action executed and
   recorded run planned at validation_completed, without objective completion.
3. Open Interventions, reload its receipt, inspect the run again and load the same
   durable command receipt through Runs history.

Direct SQLite checks after navigation showed:

| Object | Before | After |
| --- | --- | --- |
| Effect executions | 1 | 1 |
| Actions | 1 | 1 |
| Validation jobs/results | 1/1 | 1/1 |
| New provider invocations | 0 | 0 |
| Approval fulfillment commands | 0 | 1 |
| Human reconciliation audits | 0 | 2 |
| Conversational reconciliation receipts | 0 | 1 |

Effect and action receipt IDs/output hashes matched. Receipt
`4a5a22e7-56cf-4b48-a1d1-3dde8618adba` remained identical across both views.
Browser evidence: `runtime-path:/private/tmp/166-browser-verification.json`;
screenshot: `runtime-path:/private/tmp/166-reconciliation-receipt.png`.

The fixture injected signed human GET access for its otherwise internal-agent
owned run; browser write confirmation used the actual session BFF and production
schema-v4 verification. Provider execution was forbidden with an independent
invocation marker. An unrelated admin-catalog read was denied for this operator
fixture; its Next development error indicator was hidden for the receipt capture.
These checks do not certify production authentication or deployment.

## Counter-review and compatibility

The strongest hidden assumption was that reusing the common decision/history
objects automatically made every operator surface truthful. Browser navigation
falsified it: Interventions had approval-specific summary wording, which rendered
missing approval fields for reconciliation. A dedicated exact-evidence summary
and independent canceled-run projection test fixed that reader. Narrow-screen
digest overflow was also corrected and recaptured. A second reader check found
that positive approval/effect audits were being treated as policy escalations.
The escalation projection now distinguishes those audits and settles only the
exact receipt-bound effect uncertainty, including legacy audits bound by the
original approval/effect key and exact run/action. A contradictory execution ID
cannot fall back to legacy matching. Unrelated policy denials, other uncertain
effects and failed runs remain visible, with independent projection tests.
Completed reconciliation receipts remain in history but no longer count as a
pending decision; a browser reload verified zero escalations/recovery decisions
and the same receipt in history. Evidence capture:
`runtime-path:/private/tmp/166-reconciliation-interventions.png`.

Alternate writers inspected included direct/background effect recovery, approval
fulfillment, action status/link updates, guarded run restoration, worker leases,
retry-family authority, terminal cancellation and stopping-condition audits.
A succeeded effect with a contradictory action projection remains blocked with
direct-recovery guidance rather than emitting a false success acknowledgement.
A background winner causes the original proposal to return conflict; a fresh
consistent-success proposal records the existing outcome without another effect
start or fulfillment. Different proposals cannot both produce receipts for the
same execution. Exact winning-proposal replay checks current access before
returning its historical receipt, even after expiry or later run cancellation.

Migration 062 must be applied before the new backend/history reader is deployed;
deploy the backend before the frontend starts sending schema-v4 confirmations.
Older v1–v5 views/records remain unchanged. Older application readers do not
support the new v6 command; rollback should retain the additive schema and hide
new confirmation entry points rather than erase immutable evidence.

## Verification results

- Focused reconciliation suites: 92 tests passed, including the additional
  combined stop/step selection cases and historical effect/action pairs.
- Full backend clean rerun: 1,617 tests passed, one existing manually skipped
  live semantic-alignment test requiring GOOGLE_API_KEY. Two final combined
  stop/step selection cases were added after this run's collection and passed
  in the final 92-test focused run. The initial completed run's sole failure
  was the then-unwritten report link; its inventory entry is now verified.
- Frontend: make web-verify passed; 54 files / 171 tests, UI language and complexity
  checks, type/build checks and Next production build. A prior validation-page
  timing failure passed its focused rerun and the clean full rerun. A later
  agent-run page timeout also passed its focused rerun and the clean full gate;
  no unrelated timeout or test configuration was changed.
- Repository lint, architecture, bloat, entrypoint, safety/security traceability,
  documentation and diff gates passed. Documentation inventory placement was
  corrected after the initial report entry check. Architecture has zero cycles
  or complexity violations, 46/48 imports and dependency depth 9/9.
  Final static checks passed after the copy refinements.

Residual limits: no live provider polling, production deployment, distributed
scheduler or expanded beta authority is exercised. Retained leases and over-500
histories fail closed; reconciliation does not repair contradictory succeeded
projections, compensate effects, clear unrelated stops, or certify completion.
All existing direct-command behavior is covered by regression suites; the new
chat path intentionally refuses to infer legacy objective completion.

## Review follow-up: historical success acknowledgement (2026-10-08)

The review identified that a fresh conversational acknowledgement of an already
succeeded historical effect could reapply its frozen next state over newer run
progress. The regression reproduces the schedule with real durable recovery of
validation, a persisted later executed posterior action and its newer run
projection, then an API proposal/confirmation for the older validation effect.
All three nonterminal statuses (planned, running and failed) failed before the
fix: state regressed to validation_completed, diagnostics were cleared and
running/failed status became planned.

Verified existing success now sets the proposal's preserve-control-state flag.
The final transaction independently recomputes and compares that preflight,
then records the acknowledgement without restoring the older run projection.
The regression compares the entire durable run record, the later action,
existing effect rows and fulfillment count; receipt replay must preserve the
same run and immutable receipt. First-time recovery still repairs its projection,
and the authenticated direct recovery path keeps its existing compatibility
semantics. Contradictory success/action evidence remains blocked.

Validation for this follow-up:

- Reconciliation, effect-outcome and agent-run API suites: 139 tests passed.
- Semantic mutation removing the success-preservation rule at both proposal and
  confirmation: all three regression cases failed against durable run state.
- Static lint, architecture, bloat, script-entrypoint and documentation gates
  passed. Safety and security traceability gates passed with their implemented
  verification nodes executed; the final diff whitespace check passed.

The full backend and frontend results above remain the October 6 baseline;
this backend-only follow-up does not claim a new full-backend or frontend run.
