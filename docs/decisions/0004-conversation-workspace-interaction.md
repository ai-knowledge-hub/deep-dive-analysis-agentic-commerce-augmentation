# ADR 0004: Conversation workspace interaction

Status: accepted direction; Home integration implemented locally; acceptance pending
Date: 2026-10-14
Issue: [170](https://github.com/ai-knowledge-hub/deep-dive-analysis-agentic-commerce-augmentation/issues/170)
Owners: product design and agent runtime

## Context

Phase 2 has a governed conversation workspace and bounded run creation. The
next milestone is to make that operator journey coherent and readable, then
collect a real approved objective and human usability evidence. Automated
verification of the existing workspace does not satisfy those acceptance gates.

The user supplied three interface research reports and examples of a clean
chat application with personalised assistants. Their common recommendation is
a persistent conversation, an explicit next decision, and progressive disclosure
of evidence and operational detail. This is a design hypothesis to test with
operators, not evidence that a particular layout improves decisions.

The selected references are [Grok Bot](https://x.ai/bot) and the supplied Codex
screenshots for the conversation shell; [Linear](https://linear.app) for visual
restraint; and [Devin](https://devin.ai) for separating work from supervision.
[Simile](https://www.simile.ai) and [Aaru](https://www.aaru.com) are research
references for explaining simulation limits. Their presentation does not prove
the validity of this platform's synthetic results. No copied assets or external
design account are required for the first prototype.

## Decision

Use a conversation-first workspace with three regions:

1. A compact sidebar for existing conversations and the assistant's identity.
2. The main conversation, centred on the current decision, progress or outcome.
3. An optional inspector for the agreed plan, evidence, setup and assistant scope.

Advanced inspection and calibration remain accessible through the secondary
workspace. The main journey must eventually be usable without entering it.
On mobile, navigation and the inspector become dismissible overlays, with
keyboard focus contained and background controls inert.

Introduce one recognisable commerce assistant. **Scout** is a provisional name
and a small original SVG mark for review. It describes a supported role; it does
not introduce another principal, an independent memory, a delegated worker,
or a cloud computer. Personalisation must not obscure who authorised an effect.

### Visual and interaction direction

The visual thesis is a quiet, warm canvas with precise typography, a muted
green action colour, and generous space around the current decision. Light and
dark appearances share the same hierarchy. A conversation is the visual anchor;
routine information uses text, dividers and lists rather than dashboard tiles.

The content sequence is starting work, reviewing scope and a bounded plan,
supervising one step at a time, and reviewing a result with its limitations.
The main artifact is interactive only when an operator decision is required.
Progress remains compact; detailed provenance and all nine steps live in the
inspector. The composer and conversation draft remain available across navigation.

Use a brief artifact entrance, a restrained inspector reveal, and clear control
hover/focus feedback. The pending indicator means a result is pending, not that
provider progress has been measured. Respect reduced-motion preferences.

### Map presentation to existing authority

| Presentation | Existing meaning and boundary |
| --- | --- |
| Assistant | One commerce role; no new autonomous identity or policy authority. |
| Conversation | Existing authenticated, tenant-owned session and recorded turns. |
| Reviewed work | One existing product and experiment, a control variant and enabled query battery. |
| Run | One bound sequential run per conversation, with the existing governed creation receipt. |
| Current decision | Exact individually reviewed action; approval is distinct from execution. |
| Result | Recorded evidence, provenance, freshness, validation limits and a recommendation. |
| Environment | Future execution infrastructure; no VM provisioning in this milestone. |

Retain the current nine-step objective, 12-action limit, one candidate evaluation
and $5 recorded-cost limit. The latter is not a promise about complete provider
billing. Creation grants no action approval. Each of the nine steps still needs
its own approval. The prototype groups the plan for readability without
introducing a blanket approval or changing the runtime's approval policy.

Distinguish creation, approval, execution, validation and business impact in
language and state. Pausing stops further scheduling; a started step can finish.
Cancellation ends a settled run and reverses no completed effect. Unknown
provider outcomes require investigation; they must not offer a casual retry.
Incomplete work and stale or missing evidence cannot become a verified outcome.

An illustrative selection-rate comparison is synthetic experiment evidence,
not customer conversion, revenue lift or proof of customer behaviour. Do not
invent confidence scores, calibrated uplift or successful publication.

### Isolated first milestone

Build reviewable, interactive screens at `/design/workspace` before replacing
Home. Include start, clarification, plan, approval, pending work, blocked setup,
pause, unknown validation outcome, partial work, outcome and cancellation.

The route is available in development and test. Production requires explicit
server-side `WORKSPACE_DESIGN_PREVIEW=true`; existing authentication middleware
continues to apply. There is no public navigation entry. The preview components
use sample state, make no work-related API calls, create no durable records and
execute no provider or model. The existing application layout can still perform
tenant-list reads; the preview is not a separate unauthenticated application.
In-memory conversations and drafts survive navigation within the page and reset
on reload. Fixtures cannot substitute for real receipt or evidence verification.

Keep Home, existing operator controls, backend and provider execution unchanged
in this milestone. Review the concrete screens, then connect the selected
interaction to existing owner checks, durable conversation history, exact
proposals, confirmations, receipts and verified answer artifacts.

## Scope and sequence

Voice and multimodal input are future extensions to the same conversation and
authority model. Do not add controls that imply those capabilities exist now.
Multiple assistants, persistent cloud VMs, autonomous routines, publication and
new execution permissions need separate implementation contracts and acceptance.

1. Review the interactive desktop/mobile screens and the assistant identity.
2. Integrate the approved layout into the authenticated production workspace,
   preserving current backend contracts and history/evidence behaviour.
3. Exercise one approved objective with real execution and its recorded outcome.
4. Conduct the planned 5–7-person operator study, particularly the nine-approval
   burden and comprehension of synthetic evidence and pause/cancel semantics.
5. Resolve blockers and gather Phase 2 exit evidence before advancing Phase 3.

Open decisions: final assistant name and identity, preferred default appearance,
inspector discoverability, mobile approval ergonomics, whether individual step
reviews impose unacceptable friction, and any missing read model needed for
production integration. Changes to approval granularity require a separately
reviewed authority contract rather than a cosmetic shortcut.

## Brand refinement 15 October 2026

The owner selected alignment with the publication's monochrome editorial
identity, then explicitly rejected large artwork in the dialogue, including the
welcome screen. Keep conversations, the composer and review surfaces clean.
Use Arial/Helvetica typography, neutral light/dark surfaces and restrained
geometry. Op Art appears only in small icon artwork such as the provisional
Scout mark. No patterned rail, background, welcome image or artwork toggle is
part of this selection. The supplied full-size raster artwork is not bundled.

The crayon character studies remain exploration references; silhouette design
and animation are deferred. The small nested-contour SVG is a temporary
code-native mark, not a final character or a reproduction of the supplied figures.
The earlier muted-green visual thesis is superseded by this refinement.

## Evidence and related contracts

Screen and verification evidence is recorded in
[the dated report](../debug/2026-10-14-workspace-screen-verification.md).
This ADR accepts the interaction direction; it does not close Issue 170 or prove
production usability, live-provider behaviour, simulation validity or business
impact.

- [Canonical modernisation plan](../platform-modernisation-plan-v2.md)
- [Workflow and delegation semantics](0001-workflow-task-delegation-schema.md)
- [Evidence, result and completion contracts](0002-evidence-result-completion-contracts.md)
- [Operator experience](../operator-experience.md)
- [User testing plan](../user-testing-plan.md)

## Home integration 15 October 2026

The approved monochrome shell now presents authenticated Home using the existing
workspace, command and evidence contracts. The isolated sample remains at
`/design/workspace`; only presentation utilities are shared. Individual command
reviews still use exact server proposals and separate confirmation. Navigation
and progress refresh preserve scoped drafts and chronological history; evidence
keeps its original snapshot, freshness and provenance. Proposed and recorded
plans plus latest-answer evidence are available in the optional inspector.

[Integration verification](../debug/2026-10-15-workspace-integration-verification.md)
records the authority map, failure-space tests, isolated browser evidence and
frontend rollback. The provider objective and human usability study remain
pending; this integration does not complete Issue 170 or Phase 2 acceptance.
