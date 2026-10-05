# Operator Experience Guide

Status: current
Last updated: 2026-09-27

This is the current user-facing product guide for the agentic commerce control plane. It replaces the older human-led lab guide as the default way to understand the web app.

For a compact diagram of UX modes and transitions, use `docs/ux-flow-schema.md`.

## Product Posture

The product is an agent-first commerce execution control plane.

Humans should not have to manually drive every simulation, validation, recovery, and learning step. The backend agent runtime should carry the operational complexity through scoped principals, harnesses, skills, tools, policy checks, and auditable execution receipts.

The human interface exists for:

- supervision
- intervention
- approval
- explanation
- audit
- learning review
- advanced exploration when needed

The lab remains available, but it is no longer the primary mental model for the platform.

## Primary Operator Loop

The primary control-plane loop is:

```text
Inbox -> Runs -> Interventions -> Insights -> Lab only when deeper exploration is needed
```

The usability gate for this loop is documented in `docs/usability-simplification-gate.md`.
Primary screens should show goals, recommendations, review decisions, risks, outcomes, and next actions before exposing implementation mechanisms.

The June 2026 language cleanup completed the first broad pass at this gate:
primary operator surfaces now prefer product terms such as evidence set,
outcome summary, linked work, recovery action, and change details over internal
runtime terms. Advanced/admin and lab surfaces may still expose implementation
detail when the operator intentionally opens them.

### `/`

Role: control-plane entry.

Use it to understand the current operational posture and pick the right next workspace. It should stay lightweight and guide the operator toward the right surface rather than becoming another dashboard.

### `/inbox`

Role: attention queue.

Use it when the operator needs to know what requires attention now. Items should be grouped by urgency and risk, not only by creation time.
The top of the Inbox should also choose one clear first move so operators do not have to scan every queue before acting.

Primary questions:

- What is blocked?
- What failed?
- What needs review?
- What can safely wait?

### `/runs`

Role: execution supervision.

Use it to inspect active and recent agent execution. Runs should expose principal, harness, policy, registry, skills, tools, action state, timeline, receipts, and operator chat context.
The top of Runs should keep one start-here decision visible before detailed queue, timeline, and audit context.

The operator chat on this screen accepts free-form questions grounded in the
selected run. Its answer shows a snapshot digest, freshness, warnings, and
links to related records. A request to pause, resume, or cancel can create a reviewable,
time-limited proposal, but execution changes only after the operator presses
**Confirm pause**, **Confirm resume**, or **Confirm cancel**. Resume accepts only a paused run:
`plan_only` returns to `planned`, and `auto_execute_safe` returns to `running`.
It grants no approval or additional execution authority and invokes no capability.
Cancel makes a supported quiescent nonterminal run terminal as `canceled`.
The proposal explains that it cannot be resumed and that continued work requires
an authorized new run. Locks, executing actions, unreconciled effects, or failed
completion verification block this path and direct operators to recovery.
Cancellation preserves existing evidence, approvals, effects, and stopping
markers. Its receipt does not certify worker interruption or reverse effects.
The resulting receipt records that exact outcome and is linked to Interventions. Requests
to approve, retry, or otherwise change execution are not
performed and direct the operator to the governed Interventions workspace.
Selecting another run clears chat and pending proposal context so evidence
cannot bleed across runs. Normal signed-in browser sessions authenticate
through the same-origin web gateway; operators do not load a registry-write
credential to ask questions or confirm these bounded commands.
Pending pause/resume/cancel proposals and completed receipts are reloaded from the durable,
run-scoped command ledger rather than retained only in browser conversation
memory. Runs shows the exact proposal and receipt identities and offers older
pages when the history exceeds the current page. Interventions fetches an
explicitly linked run even when it is outside the newest queue window and shows
the same proposal digest, receipt, and acknowledgement after navigation or
reload. Bounded queue reads label remaining command evidence as incomplete.

Primary questions:

- What is the agent doing?
- Why is it doing this?
- What has already happened?
- What is the next recommended action?
- Is the run safe to continue?

For protocol discovery actions, selected action detail shows provenance counts
so operators can distinguish live UCP Catalog Search, live ACP product-feed
retrieval, and local metadata fallback evidence.

### `/interventions`

Role: explicit human control.

Use it for approvals, rejects, retries, pauses, escalations, recovery proposals, and compensating actions. Risky or side-effectful work should surface here instead of being buried inside long timelines.
The top of Interventions should pick the single highest-priority human decision first, then show the full queue for review.

Primary questions:

- What decision is required?
- What is the risk?
- What changes if I approve or reject?
- Is there a safer recovery path?

### `/learnings`

Role: insights into what changed.

Use it to understand recent evidence, outcome movement, recurring failure modes, and recommended follow-up work. Detailed calibration, belief, memory, and audit mechanics should be available as explanation or advanced detail, not as the first thing the operator must understand.
The top of Insights should lead with one recommended follow-up before raw learning context.

Primary questions:

- What did the system learn?
- What changed since the last review?
- Which assumptions became stronger or weaker?
- What should the operator do next?

### `/lab`

Role: advanced bench.

Use it for exploratory, notebook-like work when the operator intentionally wants to drive the system directly. It can contain chat-led simulation, evidence, alignment, experiment, and validation entry points, but it should stay visually and conceptually secondary to the control plane.

Primary questions:

- What do I want to test manually?
- What evidence or simulation context do I need to inspect deeply?
- What exploratory workflow should later become agent-operated?

## Human And Agent Responsibilities

### Agent responsibilities

The agent should handle routine complexity:

- planning safe next steps
- selecting skills and tools
- generating or revising product representations
- requesting validation
- retrying with approved recovery strategies
- capturing receipts
- summarizing outcomes
- proposing next actions

### Human responsibilities

The human should handle judgment and accountability:

- approving risky or external-side-effect actions
- steering objectives
- reviewing uncertain recommendations
- deciding when to escalate or pause
- interpreting business implications
- changing policy, harness, or configuration posture

## Chat-Led, Not Chat-Only

Operator chat is the guidance layer. Structured UI is the execution truth layer.

Chat should help operators:

- explain selected runs
- summarize failures
- recommend next actions
- navigate to evidence or validation context
- draft recovery proposals
- translate technical outputs into business language

Chat should not silently mutate state. Any approval-worthy action must map to a visible structured state change and explicit confirmation path.

## Visual Design Rules

The current visual direction is documented in `docs/ui-style-direction.md`.

Use these rules when extending the UI:

- Use typography, spacing, and grid before adding more cards.
- Reserve bordered cards for selectable or actionable objects.
- Prefer flat sections, rows, tables, and lists for status and metadata.
- Keep badges quiet; use them to describe state, not as layout scaffolding.
- Avoid card-inside-card nesting unless the inner object is independently actionable.
- Align card and row widths within a section so the page does not look accidentally fragmented.

## Current Navigation Contract

Primary surfaces:

- Control Plane (`/`)
- Inbox (`/inbox`)
- Runs (`/runs`)
- Interventions (`/interventions`)
- Insights (`/learnings`)

Advanced lab surfaces:

- Lab (`/lab`)
- Alignment (`/alignment`)
- Evidence (`/evidence`)
- Simulation (`/simulation`)
- Experiments (`/experiments`)
- Validation (`/validation`)
- Overview (`/overview`)

Admin surface:

- Admin (`/admin`)

### Completion truth in Runs

The selected run's **Verified outcome** section is the completion authority.
Run status describes execution progress but must not be interpreted as proof
that the objective is complete. A green completion label appears only for a
current, verified `COMPLETE` decision. Stale, lagging, leading, corrupt, or
unavailable projections remain explicitly non-authoritative; older legacy runs
are labeled as not governed.

Eligible projection repair is an operator recovery action, not a reevaluation
or rerun. It requires a scoped access key held only in memory for the browser
tab and a second explicit confirmation. Conflicts refresh the authoritative
view before the operator decides whether to retry.

## Historical Guides

The older complete user guide and app workflow documents live under `docs/history/`. They are retained for context and rationale, but they describe the older lab-first product shape and should not be used as the current operator guide.

Use this document for current behavior, `docs/usability-simplification-gate.md`
for acceptance rules, and `docs/ui-control-plane-simplification-plan.md` only
for remaining UX roadmap.

Before the next major backend/platform slice, use `docs/user-testing-plan.md`
to validate whether new operators can complete the primary loop without
understanding internal runtime mechanics.

For a product-to-runtime map of the agents, skills, and tools behind the main platform verbs, use `docs/agent-capability-map.md`.


### Exact action review from the run conversation

An approve or reject request selects one pending proposed action. When several
are plausible, select the action offered by the run-bound review controls.
Review normalized inputs, intended effects, checklist and consequences, then
use the separate confirm button. Dismissal and conversational agreement alone
record no decision. Stale evidence requires a fresh review.

The receipt identifies the action, approval ID, decision sequence and envelope
digest in both Runs and Interventions. Approval does not execute an action or
start/resume its run. The worker still checks exact authorization at execution;
plan-only remains non-executing, and cancellation remains terminal. A recorded
approval decision does not certify a completed effect or objective.
