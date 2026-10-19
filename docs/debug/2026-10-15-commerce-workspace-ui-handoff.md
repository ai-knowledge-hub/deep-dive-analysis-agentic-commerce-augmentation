# Commerce workspace UI integration handoff

Date: 15 October 2026
Status: session handoff; verify current state before edits

## Next objective

Continue Issue 170 by integrating the approved clean monochrome conversation
shell with the real authenticated Home workspace. Deliver the existing supported
objective-to-plan-to-creation-to-individual-action-review-to-evidence journey
inside that shell. Defer silhouette, character and animation exploration.

## Verified current state

- Repository: `historical-path: /Users/dessigeorgieva/Desktop/testing_websites/deep-dive-analysis-agentic-commerce-augmentation`.
- Branch: `codex/170-conversation-workspace-design`.
- HEAD and locally stored `origin/main`: `b4a6a21e147bc611c4573f15a020020a1d7b5a1a`
  (merged PR 169). Remote main was not fetched for this handoff.
- The working tree has substantial intentional uncommitted work from this chat.
  New preview files use intent-to-add, not staged contents. `docs/design/` is
  untracked. Preserve all of it; inspect `git status` before changing anything.
- [Issue 170](https://github.com/ai-knowledge-hub/deep-dive-analysis-agentic-commerce-augmentation/issues/170)
  is OPEN, title: “Phase 2 exit: clean conversation workspace design and real
  objective acceptance”. Queried GitHub on 15 October; no PR exists for this branch.
  No branch push, commit, new CI run or deployment was performed in this session.
- Local sample preview: `http://127.0.0.1:3100/design/workspace`. Development
  server was restarted with mock auth; recheck availability rather than assuming
  a prior process survives. Root TenantProvider reads warn without a local backend.
- Rive CLI 1.5.1 installed via Homebrew. Doctor passed core checks; not signed in.
  No character project or rig exists. Rive work is now deferred.

## Completed milestone

Interactive sample screens in `web/components/workspace-preview/` cover start,
clarification, plan, individual approval, running, blocked, paused, unknown
validation outcome, partial, outcome and cancelled. Drafts survive navigation
within this sample page; reload resets its in-memory fixtures. It imports no
operator API and executes no work. Do not mistake the fixtures for integration.

`web/app/design/workspace/page.tsx` enforces development/test admission or explicit
server `WORKSPACE_DESIGN_PREVIEW=true`. Existing authentication middleware remains.
Production Home (`web/app/page.tsx`) still uses its existing layout and controls.

## Accepted direction and invariants

Authoritative design record:
`docs/decisions/0004-conversation-workspace-interaction.md`, particularly the
15 October refinement. Preserve the useful conversation layout, compact sidebar,
one obvious next action and optional plan/evidence inspector. Advanced tools stay
secondary. The user liked the clean interface and expressly rejected large Op Art
in the dialogue, including welcome artwork. The final selection is:

- Arial/Helvetica typography, neutral light/dark surfaces, restrained geometry.
- No large illustrations, patterned sidebar, optical backgrounds or artwork toggle.
- Subtle Op Art only in small marks such as the current Scout icon. It is an
  original code-native nested-contour SVG, provisional rather than final branding.
- Keep the current product name provisional; do not rename the app to the
  publication or copy its category navigation. No publication repository changes.
- Pastel/crayon concepts and supplied figures are exploration references only.
  None are bundled. Defer silhouettes, Rive, Blender and Remotion.

Preserve existing authority and product boundaries: one tenant-owned existing
product/experiment, control variant, enabled query battery, one bound run per
conversation, nine individually approved steps, one candidate evaluation,
12-action and $5 recorded-cost limits. Creation grants no action approval.
Proposal, confirmation, committed effect, verified evidence, recommendation and
real business impact remain distinct. Unknown provider outcomes cannot offer an
unsafe automatic retry. Synthetic selection rates are not customer conversion.

## Where to integrate

Start by reconstructing these existing paths before moving markup:

- `web/app/page.tsx`: real identity/tenant context, conversation shell and run list.
- `web/components/workspace/OperatorWorkspace.tsx`: creation review, clarification,
  history, paging and run-bound chat. Currently includes redundant navigation and
  conversation selection controls that the new shell should consolidate.
- `web/components/workspace/useOperatorWorkspace.ts`: durable list/read/select,
  creation confirmations, request epochs, identity resets, paging and progress.
- `web/components/layout/Sidebar.tsx`: existing navigation, sessions and mobile UI.
- `web/components/agent/OperatorConsoleChat.tsx`, `web/components/agent/operatorChatHistory.ts`,
  `web/components/agent/OperatorCommandDecision.tsx`: structured answers, provenance and governed controls.
- `web/components/workspace/RunCreationDecision.tsx`, `web/lib/workspace.ts`,
  `web/app/api/operator-workspace/route.ts`: typed creation/BFF contracts.

Extract reusable presentation pieces or tokens from the sample shell, but keep
sample state/model and scene controls out of the live route. Real conversations
must use durable IDs and real evidence, not the sample title or progress model.
Do not replace governed command components with the prototype decision handler.

## Recommended first actions

1. Read AGENTS.md, canonical plan Phase 2, ADRs and safety/security guidance.
   Read this handoff, ADR 0004 and Issue 170; refresh status/base before edits.
2. Trace the production UI and build a compact parity map for current actions,
   auth/tenant selection, history, receipts, evidence and advanced navigation.
3. Refactor the real primary journey into the approved shell with reusable
   accessible components. Preserve exact review detail while simplifying chrome.
4. Test navigation plus progress refresh plus older-history loading together;
   keep the latest answer latest and retain original structured provenance.
   Preserve drafts across same-session refresh/navigation, isolate them on
   identity/tenant changes and reject delayed responses from the prior scope.
5. Verify the real browser journey and mobile overlays before requesting design
   approval or proposing a PR. Report missing provider/human acceptance precisely.

## Validation evidence and remaining work

Latest corrected monochrome preview: `make web-verify` passed 228 frontend tests
in 58 files, lint, typecheck, UI language, complexity and production build.
30 focused preview/server-admission tests passed; docs and diff checks passed.
Logs: `runtime-path: /tmp/170-monochrome-web-verify.log`, `runtime-path: /tmp/170-monochrome-tests.log`.
Captures: `runtime-path: output/playwright/170-monochrome-light.jpg` and
`runtime-path: output/playwright/170-monochrome-dark.jpg` (ignored local artifacts).
Desktop 1440×900, both appearances, and mobile 390×844 were inspected.

Earlier full repository lint/architecture/bloat/entrypoint/safety/security/docs
gates passed for the prototype. See
`docs/debug/2026-10-14-workspace-screen-verification.md`. One overlapping test run
timed out; isolated reruns passed without widening timeouts. No full backend suite
was rerun here. No live-provider objective or 5–7-person usability study was done.
Issue 170 and Phase 2 exit remain incomplete. Preview approval is not proof of
production parity, simulation accuracy, human usability or business impact.

For the substantive integration, apply repository adversarial-system-review and
agentic-commerce-test-design skills. Run focused meaningful regressions,
`make web-verify`, applicable backend tests and repository gates listed in
AGENTS.md, plus `make docs-check` and `git diff --check`. Preserve the preview
route for comparison and make rollout/rollback explicit before retiring paths.

## Working conventions

Continue in this existing checkout and branch; no reset, clean, worktree switch
or history rewrite. User authorised continuation of UI refactoring and creation
of a fresh chat; pushing/PR creation was not requested for this milestone.
No external accounts or assets are needed. Do not request repeated approval for
ordinary reversible work. Give concise progress updates and test actual combined
behaviour rather than mirroring markup in tests.

## Human Systems capture

```json human-systems-session-handoff
{
  "schemaVersion": "human-systems.codex-session-handoff/v1",
  "sessionId": "session_20261015_commerce_workspace_ui",
  "projectId": "agentic_commerce",
  "recordedAt": "2026-10-15T09:37:04.000Z",
  "generatedBy": { "id": "codex", "kind": "agent" },
  "visibility": "private",
  "candidateLearnings": []
}
```

## Fresh task starter

Continue Issue 170 in the existing commerce repository and branch. Read this
handoff and ADR 0004 first. Integrate the approved clean monochrome shell into
the real authenticated conversation workspace while retaining current governed
creation, individual approvals, durable history, tenant isolation and structured
evidence. Defer silhouettes and animation. Start with read-only status checks and
a production parity map, then implement and verify the complete primary journey.
Preserve all existing uncommitted work and report remaining provider/human gates.
