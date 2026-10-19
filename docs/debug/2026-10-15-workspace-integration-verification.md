# Conversation workspace integration verification

Date: 15 October 2026
Issue: [170](https://github.com/ai-knowledge-hub/deep-dive-analysis-agentic-commerce-augmentation/issues/170)
Status: implemented locally; provider and human acceptance remain pending

## Scope and presentation

The authenticated Home route now uses the approved monochrome conversation
shell. The rail owns durable conversation selection, search, tenant/account
context and secondary navigation. The main surface owns the objective,
clarification, exact creation review, chronological dialogue, individual command
reviews, receipts and composer. An optional inspector shows the proposed or
recorded plan and the latest answer's original evidence and provenance.

Arial/Helvetica, neutral light/dark surfaces and the small Scout icon carry the
selected direction. Dialogue and welcome contain no large artwork. Character,
silhouette and animation exploration remain deferred. The sample route at
`/design/workspace` remains independently admitted and available for comparison.
Only its icon and keyboard-focus utilities are shared with Home; its sample
model, decisions and fixtures are never imported into production execution.

## Reconstructed surface and authority map

| Surface | Existing writer or authority | Reader after integration |
| --- | --- | --- |
| Authentication and tenant | Clerk/mock identity, TenantProvider, BFF assertions and current backend membership/owner checks | Scoped Home, account controls, private conversation rail |
| Objective and clarification | `operator_workspace` message service; existing product/experiment/battery/control requirements | Conversation and exact creation proposal |
| Run creation | Separate exact proposal/digest confirmation; final locked creation transaction | Run creation decision and receipt; plan inspector |
| Individual action and lifecycle controls | Existing run conversation gateway, immutable command proposal, separate BFF confirmation and backend locked validation | Existing `OperatorCommandDecision`; review shortcuts only send questions |
| Execution | Existing approval ledger, worker, policy, budgets and pre-effect effect ledger | Existing run/action status projections; no new execution path |
| History | Owner/tenant-scoped durable workspace reads and older-page cursor | Numeric chronological merge, deduplication, original structured answers |
| Evidence | Host-built operator response, original snapshot, warnings, facts, provenance and source links | Latest-answer inspector; material warnings also remain in the dialogue |
| Advanced routes | Existing Inbox, Runs, Interventions, Insights, Lab, experiment/evidence/validation and admin routes | Secondary navigation and scoped record links |

No backend schema, signing audience, command payload, approval granularity,
worker, provider or completion-authority contract changes. Creation still grants
no action approval. An approval receipt still certifies a decision rather than
execution. Unknown effects have no automatic retry shortcut. Run status never
becomes an objective-completion claim. The nine-step plan and existing 12-action,
one-candidate and $5 recorded-cost bounds remain server-owned.

## Invariants and bounded failure space

The UI model covers nine material invariants. Executable evidence exercises 9/9
within this frontend scope; this is not a claim about the complete platform.

| Invariant | Independent observable oracle and evidence |
| --- | --- |
| Creation is separate from proposal and approval | Home confirmation test and browser database counts before/after creation |
| Individual action review preserves exact binding | Combined journey test checks run/action/proposal/digest arguments, no implicit confirmation, and stale confirmation failure; unchanged backend action-review tests |
| Recorded answer provenance is immutable | Original digest/fact/source/freshness fixtures remain unchanged through refresh and reload |
| History stays chronological and complete only when known | Combined older-load/refresh/navigation test; overlapping pages deduplicate; disjoint latest windows retain a cursor rather than falsely closing a gap |
| Drafts stay within conversation and identity | Two-conversation drafts, tenant substitution, human substitution, refresh and browser navigation |
| Late work cannot overwrite the current scope | Delayed older page, delayed refresh success/failure, reversed refresh completion and unmounted confirmation schedules |
| Unknown or partial evidence cannot become success/retry | Unknown validation warning remains visible, no retry shortcut, missing completion remains explicit |
| Mobile disclosure contains focus | Both overlays, inert background, Shift-Tab wrap, Escape and focus restoration; real 390px browser inspection |
| Advanced consumers remain compatible | Existing operator-chat tests preserve legacy presentation; unchanged signed BFF and backend tests remain green |

Four disposable semantic mutations were run and restored: replace loaded history
on refresh; share drafts across conversations; accept an older refresh after a
newer one; continue confirmation after the conversation unmounts. Tests killed
4/4. Logs: `runtime-path: /tmp/170-ui-mutations.json` and matching
`runtime-path: /tmp/170-mutation-*.log` files. This is a deliberately bounded
mutation score, not full authority or distributed-runtime coverage.

Counter-review followed the strongest assumption—that reusing the existing
command component alone preserved temporal correctness—through its unmount,
stream, command-history refresh and confirmation continuations. Unmount now
invalidates all request identities, including non-abortable confirmations, so a
late receipt cannot refresh another conversation. Home also tags the recent run
list with its tenant/human scope, preventing prior rows from appearing during a
scope change. Existing backend final-lock and effect controls remain unchanged.

## Browser evidence

Browser verification used the real Home/BFF/API/planner and a disposable SQLite
database with a fixture human/tenant/product/experiment/control/query battery.
Web authentication was explicitly mock. The fixture's read-only model selection
was deterministic; no scheduler or provider execution ran. Development catalog
reads require an admin, so the disposable fixture human was admitted to that
existing development catalog. This does not prove real Clerk or non-admin
production onboarding; owner/tenant boundaries are exercised by backend tests.

Observed database counts:

| Checkpoint | Runs | Actions | Approval commands | Started effects | Creation receipts |
| --- | --- | --- | --- | --- | --- |
| Proposal reviewed, before confirmation | 0 | 0 | 0 | 0 | 0 |
| Creation separately confirmed | 1 | 9 proposed | 0 | 0 | 1 |
| One approval and a separate pause confirmed | 1 paused | 1 approved, 8 proposed | 1 | 0 | 1 |

Reload restored the same conversation, run, creation receipt and action receipt.
The original answer digest and recorded time survived refresh/reload. A draft
survived progress refresh, New conversation and returning via the rail. Preparing
the next action review did not grant another approval. The pause receipt explicitly
retained the uncertified propagation limitation.

Desktop 1440×900 light/dark and mobile 390×844 were inspected. Mobile document
width remained 390px; details focused its labelled dialog, background was inert,
and Escape restored the work-details opener. Captures are ignored local files:
`runtime-path: output/playwright/170-integrated-start.png`,
`runtime-path: output/playwright/170-live-plan.png`,
`runtime-path: output/playwright/170-live-dark.png`,
`runtime-path: output/playwright/170-live-mobile-navigation.png`,
`runtime-path: output/playwright/170-live-mobile-details.png` and
`runtime-path: output/playwright/170-integrated-mobile-approval.png`.

## Verification

- Focused frontend journey/history/Home/operator-chat: 38 passed in four files.
- Full `make web-verify`: 237 passed in 59 files; lint, typecheck, UI language,
  complexity and production build passed. The preview server was stopped before
  building. Log: `runtime-path: /tmp/170-integration-web-verify.log`.
- Focused backend workspace, workspace review/rereview, action review and
  conversational commands: 168 passed in 40.21 seconds.
  Log: `runtime-path: /tmp/170-backend-regression.log`.
- Repository lint, architecture, bloat, script-entrypoint, safety traceability,
  security traceability, documentation and diff checks passed.
  Log: `runtime-path: /tmp/170-integration-repository-gates.log`.
- An initial frontend run inherited the browser-only mock identity and failed
  13 existing identity expectations. The standard environment rerun above passed;
  no expectations were weakened. An initial bloat/complexity failure was resolved
  by extracting answer-detail rendering and presentation helpers, without raising
  limits. No full backend suite was rerun for this presentation-only integration.

## Rollout, rollback and remaining acceptance

Ship against the existing workspace backend/worker and migration-063 prerequisites;
no additional migration or permissions are introduced. Existing advanced routes
and command readers remain available. Rollback is a frontend deployment revert:
retain backend ownership guards, immutable proposals/receipts and existing
workspace records. Drafts are memory-only, scoped to the current mounted Home
session, survive conversation navigation and progress refresh, and clear on
identity/tenant changes or a browser reload. No draft storage or preference
persistence contract is claimed.

The isolated browser checks are automated integration evidence. They do not
satisfy the real-provider objective, actual provider cost, synthetic validity,
customer conversion/business impact, real Clerk onboarding, or 5–7 human
usability sessions. Those remain Issue 170 / Phase 2 exit gates. No push, PR,
production deployment or external message was requested or performed.
