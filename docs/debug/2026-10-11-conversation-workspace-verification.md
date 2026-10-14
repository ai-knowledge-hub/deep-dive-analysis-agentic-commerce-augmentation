# Conversation workspace and governed run creation verification

Status: earlier verification; see the 2026-10-13 rereview supplement
Date: 2026-10-11
Issue: 168
Baseline: merged PR 167, `0c55ed8f70526ec5cac7a70a4250d2a39d43692b`.

## Design and reachable surface

The primary `/` workspace extends the shared operator gateway with a pre-run
objective adapter. It retains the existing sequential planner, host completion
coordinator, action approvals, worker and run supervision. Conversation state
owns the human/tenant context and immutable creation decision; it cannot grant
effect or completion authority.

| Stage | Authority and writers | Readers and invariant |
| --- | --- | --- |
| Objective/clarification | Authenticated human; tenant-scoped experiment/product/battery/query reads | Names are display context; one exact verified experiment is reviewed |
| Proposal | Shared gateway, immutable creation proposal and scope/registry pins | No execution rows or provider calls; bounded plan preview |
| Confirmation | Creation-specific BFF assertion or human bearer write scope; current role/principal recheck under owned write lock | Exact proposal identity, freshness, scope, policy and plan cannot drift |
| Creation | Existing governed planner behind planning barrier, compatibility shadow, completion contract/attempt authority | Non-runnable until durable governance; every action still requires approval |
| Binding/receipt | Same owned transaction binds session and run, human audit and immutable receipt | One run per conversation creation; replay preserves receipt after current access |
| Supervision | Existing run gateway, approval/effect/lifecycle writers | Same session; current projection separate from historical receipt; verified completion only |

Supported objective: one bounded experiment optimisation or comparison with a
verified tenant-owned product and query battery containing enabled queries,
within a 100-query bound. Initial capabilities are the nine existing sequential
steps from retrieval freeze through recommendation. The conversation-supervised
harness permits auto_execute_safe scheduling under human_approval_required;
creation approves no action. Limits are 12 actions, one candidate evaluation and
$5 recorded cost. These are current runtime budgets, not a guarantee of actual
external provider billing. Publication, unrestricted execution, new experiments,
batch workflows and a new scheduler remain outside this slice.

Existing operator-supervised plan-only and other profiles remain unchanged.
Existing direct creation retains standalone transaction ownership. New creation
joins run insertion, registry publication, compatibility projection, completion
contract and attempt writers through savepoints. The final owned commit includes
conversation binding, audit and receipt. Failed creation rolls back all new
execution/governance rows; existing conversation/proposal evidence remains.
Pre-run conversation registration itself may retain a harmless unbound session
if registration fails; it cannot release execution.

## Failure space and independent oracles

The test portfolio compares persisted run/action/event/shadow/governance/attempt,
receipt and effect counts, exact unchanged bindings and immutable receipt bytes.
It covers preparation vs confirmation, current scopes/roles, ten signed-assertion
substitutions, owner isolation, scope and plan drift, ambiguous experiments,
competing/duplicate confirmation, fresh-process replay after newer run progress,
worker refusal before action approval, and immutable records.

Material fault points: run/action planning, compatibility shadow, completion
activation, attempt authority, release to planned, conversation binding, audit,
receipt and final commit. Recovery must leave no pending transaction, and an
unrelated later writer must not commit failed work. Browser tests additionally
challenge late results after new conversation, URL restoration and exact server
identity/assertion forwarding. Quantitative verification and residual boundaries are recorded below.

## Rollout and limits

Apply additive migration 063 and deploy the updated backend and workers before
the workspace BFF/UI. Every API replica must have the legacy session guards
before private workspaces are enabled. Older workers do not know the new harness.
A separate confirmation signing secret is required; read-only signing authority
cannot create runs. Existing v1–v6 command records and run routes are retained.
Rollback should keep additive records and hide the new entry points rather than
erase creation evidence. Never roll back to API code that exposes private sessions
through legacy conversation routes.

This does not certify live provider execution, production deployment or human
usability. The operator usability gate remains required before the next major
platform slice; Phase 2 end-to-end acceptance must distinguish created work,
approved work, committed effects and a verified completed objective.

## Contract mapping and bounded evidence

SC-01/SEC-01/SEC-02 govern authenticated scope and policy; SC-03/SEC-06 govern
independent exact action approval after creation. SC-02 and SEC-07 describe the
broader revision/command contract; their planned distributed portions remain
planned. This adapter implements only the existing sequential creation boundary.
The safety/security schema-v1 catalog memberships and their certified tests are
unchanged; the new tests are supplementary evidence, not a claim that every
future kernel constraint is implemented.

The new backend module has 50 executed cases spanning 19 test functions. Modeled
coverage includes 8/8 required-write failure points plus 1/1 final-commit failure,
4/4 final-lock races (role, scope, session, harness), 2/2 concurrent delivery
schedules (duplicate and competing), 6/6 proposal substitutions/expiry cases,
10/10 signed-assertion substitutions, 4/4 scope-unavailable cases and 3/3 immutable
record classes. A fresh process proves receipt replay after newer state; a real
worker tick proves zero execution before action approval. Counts compare actual
persisted execution/governance/receipt/effect rows; they do not infer safety from
HTTP rejection alone.

Three disposable, internally valid semantic mutations were challenged: suppress
final authorization, replace current scope/policy preflight with frozen admission
state, and let nested run insertion commit the owning transaction. All 3/3 were
killed by independent durable-row oracles: the first two created unauthorized or
unreviewed work, and the third left an orphan run. Mutation score is bounded to
these three modeled controls, not the complete platform failure space.

Isolated browser acceptance used a temporary SQLite database, test human/tenant,
mock web authentication, the real BFF/API and existing planner. Live capability
execution was replaced with a rejecting sentinel. Proposal preparation left zero
runs/actions/approval commands/effects. Separate confirmation created exactly one
planned run, nine proposed actions, one completion contract, nine attempt
registrations and one receipt; approvals and effects remained zero. Reload
preserved the same session/run/receipt. Runs and Interventions displayed the same
creation receipt separately from pending commands. Desktop and 390px mobile
screens were visually inspected. Browser setup initially needed the test origin
configured in FRONTEND_URL; that environmental setup was corrected before
acceptance. Favicon and existing registry display warnings do not certify live
provider behavior.

Frontend executable evidence includes real hook/BFF behavior for separate
confirmation, session continuity, StrictMode URL restore, delayed response after
new conversation, tenant/human changes and signed server identity; Runs and
Interventions tests keep creation separate from confirmation controls. Human
participant usability, actual provider billing and a live approved objective
remain untested partitions.

## Original implementation verification (before the review findings)

- Full backend suite: 1,672 passed, one skipped in 619.93s. The earlier full run
  found the dependency-depth violation; the gateway now receives its objective
  adapter through composition and the rerun passes. The final additive confirmed
  proposal reader was then covered by all 50 current workspace tests (9.60s).
- Frontend: 55 files / 184 tests passed; lint, TypeScript, UI language, complexity
  and production build passed through `make web-verify` after final refinements.
- Backend gates: `make lint`, `make arch-check`, `make bloat-check`,
  `make script-entrypoint-check`, `make safety-traceability-check` and
  `make security-traceability-check` passed. Dependency depth is 9/9, maximum
  internal imports 47/48, with no cycles or complexity violations.
- `git diff --check` passed. Three expected-failing mutant probes demonstrated
  3/3 control removals caught by durable-row assertions.
- Isolated browser acceptance passed creation, URL restoration, shared receipt
  readers and desktop/mobile visual inspection. A supplementary numeric overflow
  probe failed with a CLI syntax error and is not counted as evidence; mobile
  acceptance is based on inspected screenshots.

Counter-review traced standalone/nested registry, tenant, run, compatibility,
completion and attempt writers; ordinary worker scheduling; old run chat/action
commands; replay after changed lifecycle state; private versus run-authorized
readers; and migration/rollback ordering. That earlier bounded review missed the three subsequently reproduced findings;
its passing tests did not establish these new invariants. No claim is made about distributed kernel controls, live
provider correctness, participant usability or production deployment.

Branch: `codex/168-conversation-workspace-run-creation`. Changes are uncommitted;
no push, pull request or deployment was performed. Temporary browser/API/web
processes were stopped after acceptance.


## Review fixes and additional execution evidence

The user review reproduced two blockers and one supervision defect. The fixes
protect the shared storage boundary, separate candidate capacity from global
stopping, and preserve the original structured answer rather than regenerating
provenance during hydration.

| Invariant | Reachable enforcement | Executable evidence |
| --- | --- | --- |
| Private conversations remain private through old routes | Session-store exclusion before LIMIT; legacy session manager, deletion and pre-stream guards; durable workspace membership plus old operator state markers | 18/18 read/write route cases across proposed, bound and damaged-state sessions; 4/4 listing/legacy compatibility cases; rejected calls preserve actual state, turns and execution counts |
| One candidate does not consume validation/recommendation authority | Only this harness uses global action/cost stopping; existing policy and reservation still cap candidate work | Actual created plan, staged first five results, four separately approved executed steps; a second candidate is denied; 2/2 global budget exhaustion cases still pause |
| Same-conversation progress refresh preserves supervision | Stable session/run/human reset boundary; durable turn IDs; structured response stored in private turn metadata and restored only for matching session/run | Live and remounted component regressions retain facts, evidence, original freshness and draft; command-confirmation refresh retains artifacts without resurrecting confirmation; another session resets |
| Every supervised step can complete under exact approval | Closed set of eight bounded local host receipts; existing provider/high-risk provenance verification retained | Nine separately approved real runtime steps with capability/provider work stubbed, each committing one succeeded effect; unapproved ticks invoke no capability; eight committed local receipts replay and eight forged output substitutions fail |
| Unknown local outcome cannot become invented success | Only executing host supplies the internal completion attestation; recovery requires existing committed receipt and matching action outputs | Loss after local invocation but before receipt remains uncertain/failed; caller-authored recovery is rejected and reconciliation invokes no second effect |
| Completion snapshots bind their contract | Snapshot identity includes revision, criteria identity/hash and accepted results | Full supervised execution crosses approval canonicalization that changes pending task inputs with an unchanged accepted result set; old result-only identity reproduces a conflict |

The nine-step execution test uncovered two additional integration failures: local
steps lacked receipt support despite requiring exact approval, and approval input
normalization changed the completion contract without changing the result-only
snapshot identity. Both are fixed without removing pre-effect approval checks.
The host receipt is a trusted executor attestation of returned outputs, committed
atomically with approval fulfillment and action outcome. It is not independent
proof of domain side effects. Interrupted local effects without such a committed
receipt remain held; automatic reconstruction/retry is not introduced. External
validation still requires its exactly bound durable job/result; promotion and
publication do not gain a host attestation bypass.

New private turn metadata retains the original response facts, evidence, warnings,
freshness and snapshot. Progress refresh displays the original answer timestamp.
Pre-fix text-only history cannot regain provenance that was never persisted.

Five disposable regressions challenged internally valid control removals: allow
legacy private-session access (actual proposal content escapes), treat candidate
capacity as global stopping (later work pauses), accept arbitrary local recovery
outputs (uncertain effect can be forged), restore result-only completion snapshot
identity (approval collides), and reset chat on every history array refresh
(original facts/draft vanish). All 5/5 were killed by the targeted tests. This is
a bounded mutation score, not whole-platform coverage. Backend mutants used an
external pytest plugin and isolated databases; the frontend source was restored
in a finally block.

### Verification after fixes

- Focused new regression module: 28 passed (7.53s).
- Earlier compatibility run: 116 passed (400.70s); receipt and snapshot changes
  subsequently receive full-suite verification below.
- Frontend: 55 files / 187 tests passed; `make web-verify` passed including lint,
  TypeScript, UI language, complexity and production build. The initial gate
  caught a prohibited technical label; the visible label now reads Answer recorded.
- Initial full backend attempt was interrupted after 29 passed (297.29s) while
  an optional Hugging Face model download retried unavailable DNS. It is not a
  passing full-suite result. The final run uses HF_HUB_OFFLINE=1 and
  TRANSFORMERS_OFFLINE=1; live model/provider correctness remains untested.
- Final full backend suite: 1,700 passed, one skipped in 303.06s with the
  offline environment above. No tests were excluded.
- Final repository gates passed: lint, architecture, bloat, script entrypoints,
  safety traceability, security traceability and documentation. Architecture
  depth remains 9/9, internal imports 47/48, with no cycles or complexity
  violations. `git diff --check` passed.

The current counter-review traced legacy readers/writers, shared session storage,
owner-only workspace history, worker admission/receipt/recovery, contract
canonicalization, global versus capability budgets, same-session refresh and
cross-session hydration. Production rollout, actual provider billing, live domain
side effects across all nine steps, and human participant acceptance remain
unverified. The original browser creation acceptance remains historical evidence,
not a new execution or privacy acceptance run.


The 2026-10-13 user rereview found additional tenant-switching, control-prerequisite
and long-history defects outside this earlier proof. Fixes and new evidence are
recorded in [the rereview supplement](2026-10-13-conversation-workspace-rereview.md).
