# Issue 170: Conversation workspace screen verification

Status: maintained; first screen milestone verified locally
Date: 2026-10-14
Branch: `codex/170-conversation-workspace-design`
Base: `origin/main@b4a6a21e147bc611c4573f15a020020a1d7b5a1a`

## Surface and limits

The isolated `/design/workspace` route provides interactive sample screens for
review. [ADR 0004](../decisions/0004-conversation-workspace-interaction.md)
records the selected direction. Home and operator backend contracts are unchanged.
This is a first milestone of Issue 170, not its acceptance completion.

| Reachable surface | Boundary |
| --- | --- |
| New server page | Development/test or explicit production server flag; existing auth middleware retained. |
| Preview components and local state | Sample conversations, drafts and decisions; no operator, provider or model calls. |
| Root layout | Existing auth and TenantProvider remain; tenant-list read may occur. |
| Advanced workspace link | Existing `/lab` destination, outside the disconnected preview. |
| CSS and SVG | Scoped styles and original vector mark; no external assets or design tools. |

In-memory drafts survive conversation navigation but reset on reload. Sample
completion does not verify a production receipt. Placeholder organisation and
metrics are labelled sample data. A production build defaults to no preview.

## Protected interaction invariants

- Run creation and step approval remain distinct. Reviewing an approval does
  not approve; confirmation does not claim a completed result.
- Nine separate confirmations and nine separate result events are required
  for the full illustrative journey. No timer runs work automatically.
- Pause preserves active work and late completion. Resume adds no approval.
  Cancellation is unavailable while a step is active and is terminal once settled.
- Unknown, incomplete and cancelled work cannot offer automatic execution or
  turn synthetic evidence into a customer-impact claim.
- Conversation drafts survive navigation, theme changes and inspector use.
- Hidden mobile navigation and overlay backgrounds cannot receive keyboard input;
  Escape dismisses a surface and restores focus to its opener.
- Production preview admission is enforced in the server page, not by a client flag.

## Verification

### Automated checks

- 30 focused tests across the sample workspace and server page admission:
  all eleven scene fixtures, the nine-confirmation/result sequence, pause and
  late completion, terminal boundaries, planned versus recorded evidence,
  independent drafts, inspector/theme navigation, mobile focus and server-only
  production admission.
- `make web-verify`: 228 frontend tests in 58 files, lint, typecheck, UI language,
  complexity and production build passed. The production route is dynamic.
- `make lint`, `make arch-check`, `make bloat-check`,
  `make script-entrypoint-check`, `make safety-traceability-check`,
  `make security-traceability-check`, `make docs-check` and `git diff --check`
  passed. Traceability gates execute their owned backend verification nodes;
  this does not represent a full backend-suite run.

Two bounded semantic mutations were caught and restored: allowing production
preview admission without an explicit server flag failed the server-page tests;
counting approval as completion failed the component journey at its unchanged
completion-count assertion. Both failures exercised behaviour, not syntax or
imports. Source restoration was verified before the final frontend checks.

A rerun overlapping backend traceability checks timed out four tests at their
five-second limits (two new sample-flow tests and two unchanged Runs tests).
The isolated frontend rerun passed without widening timeouts. A final rerun
includes the additional earlier-conversation shortcut regression. The timeout
run is not treated as a pass; local resource contention is the working explanation.

### Browser inspection

Used a local development server with the existing mock-auth configuration and
Playwright CLI. Inspected desktop at 1440×900 and mobile at 390×844:

- Started a sample objective, reviewed the bounded plan and created sample work.
- Opened and dismissed the separate approval dialog, checked its initial focus,
  native background `inert` state and keyboard dismissal, then confirmed the
  sample step. Completion remained 5 of 9 and cancellation was disabled while
  the result was pending.
- Inspected the optional evidence panel and the completed comparison in light
  and dark appearances. Checked mobile inspector/navigation overlays, Escape
  and focus restoration. Native mobile document width and scroll width were
  both 390 pixels.
- Visually inspected start, plan, approval, confirmation, evidence and outcome
  captures. Images are local artifacts under ignored `runtime-path: output/playwright/`;
  they are not committed to the repository.

Local browser limitations: the unchanged root TenantProvider attempted tenant
list reads against the absent local backend, producing connection warnings;
the existing favicon request returned 404. The preview itself did not make work
calls. A development source refresh reset the in-memory sample during one
browser command; the command timed out and the flow was re-entered after reading
the updated page. Reload persistence is deliberately not offered by this prototype.

### Review outcome and remaining evidence

Counter-review considered the risk that a polished sample UI could be mistaken
for verified live work. Admission is enforced server-side, there is no live
navigation entry, sample labels remain visible, and no operator API is imported
by the new components. Planned inputs/candidate text now remain unavailable
until the relevant sample steps finish. Human trust/comprehension remains a
study question rather than an automated-test conclusion.

The first screen milestone is ready for product review. Final persona/name,
appearance, inspector discoverability and nine-step review burden remain open.
Production history integration must retain original answer provenance through
refresh and pagination; these disconnected screens do not exercise that contract.

The full backend suite is not rerun for this isolated frontend milestone. Live
providers, complete production integration and the planned human usability study
remain unverified. Issue 170 and Phase 2 exit remain open. No commit, push or
pull request was created for this milestone.

## Monochrome refinement 15 October 2026

Applied the owner's publication-brand direction through neutral light/dark
tokens, Arial/Helvetica typography, slightly squarer controls and a small
original nested-contour Scout SVG. The owner rejected the first large welcome
artwork composition: the final dialogue has no image, pattern background or
artwork toggle. No supplied raster or human figure is bundled. Character work
remains deferred; this changes only the isolated design preview.

Inspected the final clean desktop layout at 1440×900 in both appearances and
the mobile layout at 390×844. Restored the browser's normal viewport afterward.
Local captures are `runtime-path: output/playwright/170-monochrome-light.jpg` and
`runtime-path: output/playwright/170-monochrome-dark.jpg`. The original publication artwork
remains untouched. The existing root tenant reads still require a backend.

After the correction, all 30 focused tests and `make web-verify` passed
(228 frontend tests, lint, typecheck, language and complexity checks, production
build). Documentation and diff checks passed. Backend runtime and production
Home are unchanged; the full backend suite and human acceptance were not rerun.
