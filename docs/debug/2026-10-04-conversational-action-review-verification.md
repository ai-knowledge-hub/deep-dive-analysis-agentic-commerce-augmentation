# Conversational action review verification — Issue 162

Date: 2026-10-04
Status: local implementation and verification; production rollout unverified
Base: merged PR 161, main commit `cfc09b3d1458344b16acf09710b8f7724161a960`
Branch: `codex/162-governed-conversational-action-review`

## Behavior and authority

Approve/reject requests create an immutable, expiring v4 proposal for one proposed
pending action. Exact action IDs, action sequences and a uniquely pending action
can identify the target. Ambiguous and batch requests create no proposal and ask
for selection. The proposal displays normalized inputs, their digest, capability
registry authority, intended effects, review checklist and existing requested
approval identity where present. Read preparation does not normalize persisted
inputs, issue approval, change action/run state or execute a capability.

A separate authenticated human confirmation binds tenant, run, proposing human,
proposal ID/digest, decision and exact action. Review BFF assertions use schema 2
and a distinct audience/issuer with the existing command-only signing secret.
Read assertions and lifecycle schema-1 assertions cannot authorize review.
Verified human identity supplies approval authority; request/model fields do not.
Model intent selection cannot select any mutation or control intent.

Confirmation admits planned, running and paused runs in plan_only or
auto_execute_safe mode, with one proposed target, no worker lock and verified
completion evidence. Verified legacy completion remains compatible. Private
snapshot, linked evidence, registry and preflight are reconstructed under the
final SQLite BEGIN IMMEDIATE lock. Changed inputs, rationale, mode, revision,
budgets, policy, membership, evidence or approval state invalidate the proposal.
An existing requested approval must match a binding rebuilt from the current
normalized action and run; approving a stale request's envelope is blocked.

The existing approval ledger joins the caller transaction using a savepoint.
Approval records/events, normalized action projection, command receipt, human
approval audits, conversational audit, actual workflow compatibility projection
and v4 conversational receipt commit together. Insert faults roll back all of
these writes. Approval/rejection does not start/resume the run, execute the action,
change mode/budgets/stops or claim completion. Existing workers still require the
exact approval at the pre-effect boundary; revocation prevents execution.

Receipt replay precedes fresh admission/expiry checks while active principal and
live owner/admin/operator membership remain required. v4 tables/views are additive;
existing v1/v2/v3 rows, digests and old views are preserved. History combines
contracts without converting their bytes. Migration 060 adds immutable review
records and protects their linked human approval audits.

## Reachable surface and counter-review

| Producer / reader | Enforcement examined |
| --- | --- |
| Host intent and action selection | Closed local mutation intents; model output excluded from control selection; ambiguous/batch target refusal. |
| Browser, same-origin BFF and API | Exact action/decision assertion, verified identity, live membership/principal, proposal identity and digest. |
| Application review preparation | Pure registry normalization, completion verification, evidence completeness, canonical policy/beta preflight, requested envelope rebind. |
| Approval ledger and conversation store | Joined savepoint ownership; locked private snapshot/preflight/source/event fences; atomic approval/action/audit/projection/receipt commit. |
| Existing worker and revocation paths | Chat approval consumed once at the actual worker pre-effect boundary; revocation prevents capability entry. |
| Persistence and migration/history | Immutable proposal/receipt/linked audits; additive v4 views; actual migration preserves prior bytes/cursors/replay. |
| Runs and Interventions | Persisted receipt/action/approval identity, exact inputs, explicit confirmation, unchanged run posture after review and reload. |

The strongest hidden assumption was that the canonical approval transition would
rebind an already requested envelope to the newly displayed action. Direct
inspection showed that transition reuses the requested envelope. The review now
rebuilds and compares its binding; an executable stale-request test and a semantic
mutation challenge that correction. A second assumption was that the approval
adapter could be called inside the conversation transaction without committing
it. Joined savepoints and real projection/receipt insert faults test ownership.

Alternate writers/readers inspected include direct approval/revoke APIs, approval
normalization, worker pre-effect consumption, cancellation, existing lifecycle
receipts, completion readers, workflow audit projection and compatibility views.
SQLite serializes final decisions and cancellation; a lost race produces a
conflict and no second decision. Browser inspection also found duplicate recovery
cards for the approval ledger's received/completed audits. Interventions now
suppresses only audits whose exact approval command is represented by a durable
review receipt, preserving unrelated commands and fallback evidence when review
history is unavailable. No unresolved blocking finding remains in this scope.

## Independent oracles and bounded failure space

Tests inspect durable actions, approvals, effects, receipt hashes, event types,
actual projection writes and unchanged run fields rather than trusting HTTP/UI
success alone. External capability behavior is stubbed only at the provider call
in the worker test; its approval consumption and validation/effect receipts use
real repositories and worker orchestration.

| Partition | Executable evidence |
| --- | --- |
| Source × mode × decision | 12/12 legal combinations preserve status/state/mode/budgets/policy/revision; eight declared illegal sources/modes blocked. |
| Stale private state | Eight mutations: inputs, rationale, budgets, mode, revision, policy, lock, membership. |
| Exact assertion | Nine substitutions: audience, schema, issuer, action, run, tenant, human, decision, proposal digest. Read assertion rejection separately tested. |
| Target selection | Unique/exact target supported; six ambiguous, unknown and batch examples create no proposal. |
| Pending approval compatibility | Current request reused without duplicate request; stale requested envelope cannot become reviewed authority. |
| Atomicity | Receipt faults for both decisions; approval ledger/audit faults; actual workflow projection insert failure; caller's unrelated outer work survives inner rollback. |
| Interleavings | Competing approve/reject; duplicate confirmations; cancellation winning; receipt replay after cancellation and principal deactivation. |
| Persistent evidence | Nine update/delete/replace attacks across review proposal, receipt and linked approval audit. |
| Compatibility | Actual 060 reapplication preserves old v1/v2/v3 bytes, cursor and replay; old views exclude v4, new view includes it. |
| Worker consumption | Confirmed chat approval consumed once by real worker; second tick makes no extra call/effect; revocation prevents capability entry. |
| Failed reconstruction | Persistent missing/raising completion readers; registry, completion and linked-validation changes after route read; model mutation-intent refusal. |
| UI projection | Duplicate audits suppressed only for the exact receipt-linked command; unrelated and fallback audit evidence retained. |

There are 70 new backend cases across the review and admission modules. Four
process-local semantic mutants used isolated databases without editing source:
remove exact action assertion matching; remove final private snapshot comparison;
commit the approval ledger's joined transaction; remove requested-envelope binding
comparison. All four were detected (4/4 targeted mutants). This is a bounded
mutation score, not exhaustive platform coverage.

## Verification results

- Focused backend portfolio before the final admission supplement: 342 passed.
- Full backend `make test`: 1,395 passed, 1 skipped in 531.21 seconds. The existing
  manual live Google semantic-alignment test remains skipped, not passing.
- The six admission supplement cases were added after that full run collected;
  final combined review/admission run: 70 passed. Production changes after the
  full run were formatting and frontend duplicate projection correction only.
- Final web verification passed lint, type checking, 158 tests in 54 files,
  UI language/complexity checks and optimized production build.
- Python lint, architecture, bloat, script entrypoints and diff checks passed.
- Executable safety/security traceability checks passed. Catalog implementation
  status and beta exclusions remain unchanged.
- Documentation gate passed.

## Local browser and fresh-process proof

The real local Runs page, same-origin BFF and unmodified API used an isolated
migrated SQLite database. Browser authentication was the explicit development
mock mode with a seeded operator membership. ADMIN_USER_IDS included that fixture
user to load the existing ancillary catalog; final decision persistence still
required its actual active human principal and tenant membership. This does not
certify production Clerk authentication or signing-secret deployment.

Two pending actions made the first request ambiguous. Selecting action 1 showed
its normalized inputs/effects/checklist and separate confirmation. Database
inspection before the click found both actions proposed, zero approval commands,
zero review receipts and zero effects. The explicit approve click recorded one
approval. A rejection proposal for action 2 was dismissed; reload restored that
same durable proposal with no rejection receipt. Explicit rejection then recorded
the second decision. Reload preserved the receipt digests and both history IDs.
Runs and run-scoped Interventions displayed the same persisted records.

| Decision | Action | Receipt |
| --- | --- | --- |
| approve | `5a34bddd-9525-4aa0-975b-d8c1ca78ca54` | `b21f59aa-39e6-449e-b8a4-b75b5bc0e1b7` |
| reject | `68c9ecc0-896b-437f-a112-3119782ec9a6` | `278c243a-d16d-4d87-af72-9ab6b2f64243` |

Fixture run `5b71b7b4-9b81-4efc-8907-3472049368cf` remained paused, plan_only and
battery_ready. There were two approval commands, two conversational receipts and
zero effects. A fresh Python process replayed both receipts with expiry forced
and both new-admission and approval-commit callbacks forbidden: 2/2 original
digests matched, with no new commands, receipts or effects.

Screenshots were saved outside the repository in the task's visualization
workspace. Local servers were stopped after final verification. Production
rollout, external provider behavior, distributed worker interruption, batch
review, revoke/supersede chat, retries and approve-and-execute remain unverified
or intentionally deferred. No beta control is promoted by this local evidence.

## Follow-up: commit failures and multiple action references

Two P2 findings exposed a standalone approval commit failure and target-selection
ambiguity. The transaction helper released its savepoint before committing an
owned transaction. If commit failed, rollback attempted to use that removed
savepoint, masking the commit exception and leaving approval writes available to
an unrelated later writer. Owned transactions now commit and roll back directly
on the connection; calls joined to an outer transaction retain savepoint-local
commit/rollback. This keeps caller work isolated and makes an owned failed commit
receive a full rollback while preserving its original exception.

The resolver previously matched only the first action sequence. It now collects
all explicit references and shorthand list tails, resolves every target, and
requires one unique action identity. Multiple distinct actions, unknown sequences,
unknown IDs, UUID substitutions and plural batch requests create no proposal.
Equivalent ID/sequence references to the same action remain supported. Bare IDs
are matched at identifier boundaries so an ID prefix cannot select an action.

The follow-up adds 33 regression cases: two exception types through the actual
standalone approval command, one real deferred-foreign-key commit failure,
24 approve/reject combinations across multiple/unresolved target forms, and six
valid exact/equivalent target forms. The approval failure cases assert the
original exception identity, no active transaction, unchanged action, no approval
records/events/commands/effects/audits, and a successful unrelated ensure_user()
commit that cannot resurrect those failed writes. Joined caller isolation remains
covered by the earlier savepoint and conversational atomicity tests.

- Review/approval/finding portfolio: 160 passed.
- Runtime, worker, existing lifecycle and API portfolio: 196 passed.
- Two process-local semantic mutants restore the faulty owned savepoint handling
  and first-sequence-only target selection: both detected (2/2).
- Lint, architecture, bloat, script entrypoint and executable safety/security
  traceability gates passed. Documentation and diff checks passed.
- Frontend files are unchanged by this follow-up; the preceding 158-test web
  verification remains applicable. The full-suite result above predates these
  two fixes and is not reported as a fresh full-suite verification of them.
