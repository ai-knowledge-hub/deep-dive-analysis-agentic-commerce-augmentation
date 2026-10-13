# Conversation workspace rereview fixes

Date: 2026-10-13
Issue: 168
Branch: `codex/168-conversation-workspace-run-creation`
Status: fixes implemented; final verification results below

The user reproduced three issues despite the earlier passing suites: a global
human principal's stored tenant blocked another valid membership, preparation
accepted an experiment without the baseline control, and history restored the
oldest 500 turns. This report supplements the
[original implementation and earlier review report](2026-10-11-conversation-workspace-verification.md).

## Reachable surface and invariants

| Surface | Authority or prerequisite | Enforcement and independent oracle |
| --- | --- | --- |
| Bearer/BFF workspace list, message, confirmation and history | Global human identity; active status/type; signed requested tenant; current membership and role | Human status/type checks remain; membership authorizes the requested tenant. Two real backend memberships exercise repeated A/B switching and creation in both tenants under both authentication mechanisms. Removed membership, disabled identity, cross-tenant sessions and non-human tenant/type substitution remain rejected. |
| Preparation and final locked confirmation | Tenant-owned experiment/product/battery/queries and a runtime-resolvable control | Use the baseline capability's actual role/label selector; require an experiment-owned control and include its record in the scope digest. Missing control/candidate-only setup creates no proposal or execution. Deletion, role removal, replacement and a change under the final lock create no execution/governance/receipt rows or pending transaction. |
| Private long-history read, BFF and UI pagination | Authenticated workspace owner in the requested tenant; cursor narrows this session's rows | Latest 500 turns are selected by descending immutable turn ID then returned chronologically. Exclusive `before_turn_id` returns older rows, with a next cursor and completeness flag. Same timestamps and concurrent newer inserts cannot reorder or shift older pages. Original answer metadata survives restoration. |
| Older history loading and refresh/tenant transitions | Current session, identity generation and outstanding cursor | Prepend and deduplicate older turns while retaining current run progress and recent evidence. Discard pages after tenant switching or after a refresh supersedes their cursor. The UI exposes Load older messages for pre-run and bound conversations. |

Human principal IDs are globally keyed as `human:<user_id>`. Their registry
`tenant_id` is historical context, not membership authority. The shared active
principal check therefore retains type/status validation while applying registry
tenant equality to non-human identities. This also avoids the same error during
bearer authentication before the workspace role check. Signed token/assertion
client scope checks, endpoint membership rules and owner checks are unchanged.
The existing configured administrator policy remains unchanged. This is not a
new membership or token issuer implementation.

Control selection deliberately retains current runtime compatibility: explicit
`payload.role=control` takes precedence, with a control label as fallback. The
positive test uses real capability dispatch and control resolution; only
ExperimentRunner/provider work is stubbed. The full nine-step runtime test still
stubs capability bodies and is not proof of live domain/provider execution. A
control changed after creation can still make later work fail; these checks
certify preparation/confirmation prerequisites, not future external readiness.

History page queries always include the owner-authorized session ID. A cursor
from another session does not confer access to its rows. Cursors are positive
safe integers and rejected before database binding if malformed or oversized.
Older pages reuse read authentication; pagination supplies no creation or
execution authority. Reading older history does not replace current progress
with the page response's run projection. Progress refresh retains the earlier
answer's original provenance rather than manufacturing fresh evidence.

## Bounded failure space and mutation evidence

The new backend module executes 15 cases: 2 authentication mechanisms for
multi-tenant switching/creation and membership/status rejection; 1 non-human
scope/type boundary; 1 missing-control preparation; 4 confirmation control
changes; 2 real baseline selection conventions; 1 long-history/concurrent-insert
and owner isolation scenario; and 4 invalid cursor partitions.

Frontend additions execute 3 hook scenarios (prepend/deduplicate without losing
current evidence or progress, identity change, superseding refresh), 1 BFF cursor
forwarding case and 5 invalid cursor partitions. Existing component tests remain
the evidence for rendering original structured answers and draft preservation.

Six disposable semantic mutations are challenged: restore the global human
registry tenant lock; bypass current membership; accept a candidate as a control;
remove the control from the scope pin; return oldest-first history; replace
current history/progress with an older page. The backend mutants use an external
pytest plugin and isolated databases. The frontend source is restored in a
finally block. Mutation results are bounded to these controls, not platform-wide
coverage.

## Verification

- Focused workspace portfolio: 93 passed in 17.32s. The final expanded multi-tenant
  creation scenarios then passed with all 15 new cases in 3.92s.
- Initial focused fault injection used a connection from the wrong test thread;
  that fixture was corrected to use the API thread's connection before passing.
- Initial web verification caught the hook complexity limit. Pagination request
  and merge helpers were extracted; final results are recorded below.
- Final full backend suite: 1,715 passed, one skipped in 289.60s.
  HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1 were used to avoid optional model
  downloads; no tests were excluded.
- Final `make web-verify`: 56 files / 196 tests passed, plus lint, TypeScript,
  UI language, complexity and production build.
- Lint, architecture, bloat, script entrypoints, safety traceability and security
  traceability passed. Architecture depth is 9/9; internal imports 47/48; no cycles
  or complexity violations. Documentation and `git diff --check` passed after
  adding this report to the authoritative inventory.
- Six targeted mutations: 6/6 killed. The global-tenant mutant rejected valid
  membership; the membership bypass admitted a removed member; both control
  mutants admitted invalid/unreviewed setup; oldest-first paging lost recent
  evidence; older-page replacement discarded recent answers. All mutant code
  was restored before final delivery.

No live providers, actual billing, production rollout, browser acceptance or
human participant usability were exercised in this rereview. The earlier browser
creation acceptance remains historical evidence. All changes remain uncommitted;
no push, pull request or deployment was performed.

## Combined older-history and progress-refresh follow-up

A later component probe showed that loading older messages and then refreshing
progress put retained older turns after the recent server window. The chat uses
its last response for facts, warnings, recommendation and evidence, so this
ordering error promoted an older answer without changing any server provenance.

`mergeRecordedMessages` now orders recorded messages by their durable numeric
turn IDs across all loaded windows. In-flight local messages remain after
recorded history in local order; after durable IDs arrive, `recordLiveAnswer`
uses the same chronological ordering. Existing rich response metadata is
retained when refresh supplies plain historical text. Selection of the latest
answer therefore follows chronology rather than page arrival order.

The real chat regression exercises recent history, loading older answers, typing
a draft and refreshing only the recent window. It checks current facts, warnings,
recommendation and evidence; both answers remain once in chronological transcript
order, and the draft survives. A second test checks numeric ordering of IDs 1,
2 and 10, preservation of in-flight message order, and assignment of durable IDs
11 and 12. Both tests reproduced the original ordering defects before the fix.
An initial transcript-order assertion assumed paragraph markup; it was corrected
to compare the actual rendered answer elements' DOM order.

Focused component/Home/pagination tests: 29 passed. Final `make web-verify`:
56 files / 198 tests passed, with lint, TypeScript, UI language, complexity and
production build. All repository gates and `git diff --check` passed. Restoring
the original append-older merge killed the component regression (1/1 bounded
mutation); the source was restored byte-for-byte in a finally block. No backend
source changed for this follow-up; the earlier 1,715-pass backend run was not repeated. Live
providers, browser acceptance and human usability remain unverified.

## Initial PR CI guard correction

PR #169's first backend job stopped at the legacy DB import guard before dependency
installation or tests. The registry helper imported modules from the grouped
package root, which matched that guard's prohibited pattern. Explicit grouped
module imports preserve behavior and comply with the guard. Local lint,
architecture, the matching legacy-import pattern scan and all 50 creation tests
passed before pushing the correction. Earlier full-suite and frontend evidence
remain the validation baseline; the new remote CI run is separate evidence.
