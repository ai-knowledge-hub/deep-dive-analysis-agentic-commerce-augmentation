# Conversational cancellation verification — Issue 160

Date: 2026-10-03
Status: local implementation and verification; production rollout unverified
Base: merged PR 159, main commit `5de4a58904e82ae96626578e260ba0b70c5e33a0`
Branch: `codex/160-governed-conversational-cancel`

## Behavior and authority

The closed cancel_run intent creates an immutable, expiring v3 proposal.
A separate authenticated human confirmation makes a supported quiescent run
terminal as canceled. Proposal creation, dismissal, explanation, and model
selection cannot commit cancellation. The conversation is excluded from replay.

The admitted sources are created, planning, planned, running, and paused, using
plan_only or auto_execute_safe. Failed, completed, canceled, cancelled, unknown,
noncanonical status, and unsupported mode are ineligible. Verification accepts
successfully verified legacy completion views; missing or corrupt evidence fails
closed. Existing stop markers are retained and do not block terminal exit.

The final SQLite BEGIN IMMEDIATE transaction reconstructs membership, active
human principal, full private snapshot, live registry and preflight. It fences
revision, mode, governing pins, event head, complete bounded actions, approval,
effect, linked validation and completion evidence. Locks, executing actions,
started/uncertain effects, or incomplete action state block admission.

Status, human command audit, lifecycle audit, required workflow-event projection,
and immutable receipt commit together. Receipt replay precedes new admission.
No capability executes; mode, state, revision, approvals, budgets, pending work,
evidence, stops, and completed effects are preserved. The receipt acknowledges
control_plane_canceled and explicitly declares runtime_propagation_not_certified.
Worker interruption, distributed propagation, compensation and new-run creation
remain outside this slice. SEC-17 and its associated governance gaps remain
planned; no catalog control is upgraded to implemented by this record.

## Reachable surface

| Producer or reader | Enforcement and consequence |
| --- | --- |
| Browser chat / host intent selector | Closed cancel intent, nonmutating proposal, mandatory terminal consequences. Retrieved/model content cannot become confirmation. |
| Same-origin command BFF | Separate command-only secret; short-lived assertion binds human, tenant, run, proposal ID/digest and command type. Read assertions cannot confirm. |
| API / command service | Exact durable proposal, verified identity and role; cancellation dispatches to the durable command store without calling a capability. |
| SQLite command store | Final locked snapshot/preflight, expiry, principal, source and event-head fences; one atomic status/audit/projection/receipt commit. |
| Runtime start/step/retry/replanning | Existing terminal checks prevent new work; current governed pre-effect commit also fences late workers against canceled state. |
| Effect recovery | Existing reconciliation preserves canceled terminal projection; cancel leaves succeeded effects and fulfilled approvals unchanged. |
| Migration 058 / history | Additive immutable v3 tables; v1/v2 rows and digests unchanged; separate v3 views include all three contracts; old v1/v2 views exclude v3 rows. |
| Runs / Interventions | Exact persisted proposal/receipt identity after reload; run navigation clears context. Canceled Runs guide links to its record instead of starting or approving pending work. |
| Background lifecycle / persistence | Migration 059 protects receipt-backed cancellation even without completion governance. Reconciliation and planning activation use conditional transitions; stale writers return the persisted status. Legacy explicit cancellation does not gain v3 receipts or conversation authority. |

Resume and cancel share the existing full private snapshot builder. Resume's
stop-history scan and exact operator-pause clearance remain separate. The public
snapshot and private fence retain their previous digest shape for v2 admission.

## Independent oracles and bounded failure space

Tests inspect persisted run/action/approval/effect rows, event types/counts,
immutable receipt identity/digest, source markers, actual workflow projection,
and literal canonical source/target expectations. HTTP success and UI text are
not used as the only oracle. Fault injections use isolated databases.

| Partition | Executable coverage |
| --- | --- |
| Legal source × supported mode | 10/10 combinations, target canceled, mode/state/actions preserved, terminal command rejection and exact receipt reload/replay. |
| Declared illegal source/mode representatives | 11/11: six status and five mode representatives. This is not an exhaustive arbitrary-string space. |
| Stop marker retention | 4/4 policy, budget, operator, unknown markers, including exhausted effective budget. No stop-clear event. |
| Completion failure timing | 3/3 before proposal, before confirmation, after early read before commit lock; actual corrupt authoritative completion records. |
| Persistent reader failure | 2/2 missing/raising readers, repeated unchanged failures cannot produce a proposal. |
| Quiescence | Lock, executing action, oversized bound sentinel, started and uncertain effects. |
| Post-early-read evidence/authority changes | 8/8 inputs, mode, revision, policy, lock, membership, linked validation identity, live registry. |
| Additional private evidence changes | 4/4 approval, effect, validation result, validation job, using real durable approval/effect fixtures. |
| Exact command assertion | 7/7 run/tenant/principal/digest substitutions, pause/resume assertion substitutions, read-only assertion. |
| Persistent evidence mutation | 9/9 update/delete/replace attacks across proposal, receipt and lifecycle audit. |
| Atomic write faults | 2/2 receipt and actual workflow-event projection insert failures roll back status, source audits and receipts. |
| Competing confirmations | 3/3 exact duplicate cancel, cancel versus pause, cancel versus resume; only one new receipt/outcome wins. |
| Replay admission paths after corruption | 2/2 early receipt read and receipt discovered under the final commit lock. |
| Compatibility/history | Actual 058 upgrade preserves v1/v2 bytes, replay, existing cursor and prior-reader views; 58 mixed proposals remain accessible across pages, with no duplicates or missing records. |
| Effect safety | Started/uncertain effects blocked; canceled runtime cannot execute; completed effect and fulfilled approval preserved; stale worker cannot commit a new effect. |

There are 75 new backend cancellation cases across the API, effects and
compatibility modules. Existing pause/resume/API tests also run in the focused
portfolio. The two terminal-guide UI cases include pending work so the display
cannot suggest approving or starting it after cancellation.

Three deliberately harmful, syntactically valid mutations were applied and
restored sequentially before final verification:

1. Remove completion verification admission guard: detected.
2. Remove final locked private snapshot comparison: detected.
3. Remove both executing-action and unreconciled-effect admission guards: detected.

Mutation score: 3/3 targeted mutants detected. This bounded score does not claim
exhaustive mutation coverage of the platform or distributed runtime.

## Verification results

- Focused backend portfolio: 175 passed.
- Final full backend make test: 1,310 passed, 1 skipped, 488.70 seconds. The existing
  skipped live semantic-alignment test requires manual execution with a Google
  API key; it is not represented as passing.
- Final make web-verify: passed lint, type checking, 149 tests in 52 files,
  UI language and complexity checks, and optimized production build.
- Python lint, architecture, bloat and script-entrypoint gates: passed.
- Safety/security traceability gates: passed, including execution of implemented
  verification nodes. Catalog status and beta capability exclusions unchanged.
- Documentation gate and git diff check: passed.

## Local browser and restart evidence

An isolated migrated SQLite database and mock-authenticated browser used real
same-origin BFF assertions. No production tenant or effect was involved.
Proposal creation and dismissal left both initial runs paused with zero receipts;
reload restored the proposal. Switching runs removed the previous proposal and
switching back restored its exact identity. Explicit clicks canceled both modes.
A planned plan-only run and a quiescent running auto-execute-safe run also
canceled through the browser. Runs and run-scoped Interventions rendered the
same receipt/proposal identity. Reload preserved the Interventions record.
The terminal guide now directs users to the cancellation record. The four
flows and restart replay were repeated against a fresh database after the
separate-v3-view compatibility fix; the identities below are from that final pass.

| Source | Mode | Run | Receipt |
| --- | --- | --- | --- |
| paused | auto_execute_safe | `8f13b930-a2bb-4e26-9073-0f51cd6e7d68` | `666a8b4b-72b3-4650-957e-c292e4176adf` |
| paused | plan_only | `184c829e-841e-4ba4-9d02-b13f7d3c0230` | `244de626-0190-4c5b-aff8-95c33e5ec526` |
| planned | plan_only | `09a9b1db-72ff-4f29-b822-cb3195ba2282` | `112a0a34-450a-43b6-accd-35232482a6c2` |
| running | auto_execute_safe | `0d829ff3-1db4-48a6-bae3-0a17aa5eb202` | `c91c852d-cbc2-44b0-90bd-af533a2ba963` |

Database inspection found four canceled runs, four immutable cancellation
receipts, eight source audit events, zero actions and zero effect executions.
A fresh Python process read those v3 proposals from the database and replayed
all 4/4 receipts with expiry forced and the admission callback set to raise.
All original receipt digests matched; no status or audit duplication occurred.
Local servers and the temporary browser tab were stopped after verification.
The local development database had received an earlier form of this unpublished
migration during test startup. Its views were synchronized with the final
v1/v2-plus-separate-v3 shape after making a SQLite backup under the temporary
folder. All six proposal/receipt tables were compared before and after and
preserved exactly; no command or workflow row was changed by that repair.

The seeded operator's ancillary client/brand sidebar reads returned 403; run
reads, chat, confirmation, completion and history succeeded. This existing
sidebar authorization behavior is outside the slice. Production Clerk sign-in,
production migration/rollback, distributed workers and real external-provider
interruption remain unverified.

## Review conclusion

The adversarial review traced host intents through authentication, durable
proposal/confirmation, actual transactional dual projection, runtime terminal
and pre-effect checks, recovery, additive schema, and both readers. The
counter-review's hidden assumption was that early quiescence or missing
completion evidence could authorize later cancellation. Locked reconstruction,
corruption/race tests and targeted mutations challenge that assumption.
Browser inspection also found and corrected a misleading terminal start guide.
Compatibility review found and corrected a rollback-reader risk: v3 history now
uses separate views, leaving old v1/v2 views free of unparseable v3 records.
The initial review missed background status writes after quiescent cancellation;
the follow-up below addresses that finding.
The planned distributed stop/lease/compensation controls remain explicit gaps.

## Follow-up: terminal cancellation across background writers

The P1 finding identified two reachable violations: worker reconciliation after
lock release could make a canceled legacy run planned and runnable, and the
initial-plan governance failure handler could replace cancellation with failed.
The prior terminal guard applied only to completion-governed runs.

Migration 059 adds a receipt-scoped persistence guard that rejects any status
other than canonical canceled, independent of completion governance. It is
additive for installations that already applied 058 and changes no receipt
bytes. Runtime reconciliation preserves terminal runs and compares the observed
status atomically before writing; a lost race rereads the persisted run.
Planning activation releases or fails only a run still in planning, preserving
the original activation exception when cancellation has won. Both release
modes return current persisted state after successful activation.

The new terminality module has 21 cases: 14 persistence overwrite combinations
(seven targets across legacy/governed runs), actual worker lock-release and
mid-reconciliation cancellation races, four activation success/failure and
release-mode combinations, and an actual 058-to-059 upgrade with a preexisting
receipt. Oracles inspect durable status, runnable selection, receipt digest,
single cancellation event, and unchanged state/error. The activation tests
enter after a persisted plan and use the real completion coordinator for the
successful activation; its failing dependency is injected deterministically.
They do not certify interruption of an in-flight planner or provider.

- Focused cancel/runtime/worker/completion portfolio: 157 passed.
- Follow-up full backend `make test`: 1,331 passed, 1 skipped in 490.23 seconds.
  The skip remains the existing manual live Google semantic-alignment test.
- Three process-local semantic mutants detected: remove the persistence guard,
  remove reconciliation's conditional transition, remove planning activation's
  conditional transitions. Mutants used isolated databases and did not modify
  repository source during the full-suite run.
- Lint, architecture, bloat, script entrypoints, documentation and executable
  safety/security traceability checks passed. Frontend files were unchanged by
  this follow-up; the existing web verification above remains its UI evidence.
  Final `git diff --check` passed. No unresolved blocking finding remains in
  this reviewed cancellation scope.
