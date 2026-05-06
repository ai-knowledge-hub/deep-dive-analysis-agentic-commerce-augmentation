# UI Control-Plane Simplification Plan

This document translates the agent-first platform direction into a concrete web UI simplification plan for the current Next.js app.

The goal is not to remove the lab. The goal is to stop presenting the lab as the primary top-level navigation model once the product becomes an agent-first execution fabric.

## Current UX Diagnosis

The current app has valuable functionality, but the top-level information architecture is overloaded.

### Current top-level routes

- [web/app/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/page.tsx)
- [web/app/overview/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/overview/page.tsx)
- [web/app/alignment/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/alignment/page.tsx)
- [web/app/evidence/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/evidence/page.tsx)
- [web/app/simulation/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/simulation/page.tsx)
- [web/app/experiments/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/experiments/page.tsx)
- [web/app/validation/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/validation/page.tsx)
- [web/app/agent-runs/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/agent-runs/page.tsx)
- [web/app/admin/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/admin/page.tsx)

### Current navigation

The main sidebar in [web/components/layout/Sidebar.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/layout/Sidebar.tsx) exposes:

- Alignment
- Evidence
- Simulation
- Experiments
- Validation
- Overview
- Agent runs
- Admin

This reflects the internal lab workflow, not the operator’s actual decision loop.

### Main UX problems

1. The homepage is doing too much.
   - [web/app/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/page.tsx) mixes chat, evidence, simulation context, experiments context, model configuration, session history, and navigation intent.

2. Top-level routes are organized by internal subsystems, not operator jobs.
   - Operators think in terms of "what needs attention", "what is running", "what is blocked", and "what changed".
   - The current IA asks them to think in terms of "alignment", "evidence", "validation", and "simulation" as separate first-class pages.

3. Multiple pages are reloading overlapping context.
   - `overview`, `alignment`, and `/` all pull simulations and experiments.
   - This creates UI duplication and increases the feeling of sprawl.

4. `Agent runs` is conceptually the right direction, but it is still a specialized page rather than the main control-plane surface.

5. The sidebar is optimized for breadth rather than clarity.

## Target UX Role

The web app should become the human control plane for an agent-first backend.

That means the main UI should optimize for:

- visibility into autonomous work
- exception handling
- intervention
- auditability
- learning review

The detailed lab workflows should still exist, but as drill-down surfaces rather than primary navigation.

## Target Top-Level Navigation

The recommended primary navigation is:

1. Inbox
2. Runs
3. Interventions
4. Learnings
5. Admin

Everything else becomes:

- secondary tabs
- contextual drill-downs
- advanced tools

## Route Mapping

### 1. Inbox

New route:

- `web/app/inbox/page.tsx`

Purpose:

- show what needs operator attention now

Primary contents:

- blocked approvals
- failed runs
- policy violations
- drift alerts
- validation/provider failures
- stale or stuck runs

Data sources:

- agent run status and event stream
- validation job status
- recent policy events

This should become the default landing page after sign-in.

### 2. Runs

Primary route:

- evolve [web/app/agent-runs/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/agent-runs/page.tsx)

Purpose:

- the main execution timeline and supervision surface

Primary contents:

- run list
- current state
- objectives
- principal identity
- selected skills/tools
- timeline
- action outputs
- receipts
- retry/approval controls

Current `Agent runs` is already the best starting point for the control plane. It should be promoted and simplified rather than replaced.

### 3. Interventions

New route:

- `web/app/interventions/page.tsx`

Purpose:

- focused queue for human decisions

Primary contents:

- approve / reject actions
- pause / cancel / retry run
- downgrade autonomy profile
- reroute harness
- open evidence or simulation context if needed

This should not be hidden inside long run timelines. It should be a dedicated, decision-efficient surface.

### 4. Learnings

New route:

- `web/app/learnings/page.tsx`

Purpose:

- review what the system learned, changed, or recalibrated

Primary contents:

- evidence deltas
- belief changes
- calibration changes
- validation accuracy trends
- protocol readiness changes
- skill and harness performance snapshots

This route should absorb most of what is currently spread between:

- [web/app/overview/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/overview/page.tsx)
- [web/app/alignment/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/alignment/page.tsx)
- [web/app/evidence/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/evidence/page.tsx)

### 5. Admin

Keep:

- [web/app/admin/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/admin/page.tsx)

But narrow its purpose to:

- tenant setup
- provider config
- credential and connector setup
- advanced diagnostics
- lab/advanced feature access

## What Becomes Secondary

The current lab routes should remain available, but move under a secondary "Lab" grouping or advanced workspace entry point.

### Keep as advanced drill-downs

- [web/app/simulation/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/simulation/page.tsx)
- [web/app/experiments/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/experiments/page.tsx)
- [web/app/validation/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/validation/page.tsx)
- [web/app/alignment/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/alignment/page.tsx)
- [web/app/evidence/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/evidence/page.tsx)
- [web/app/overview/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/overview/page.tsx)

These pages are still useful for deep investigation and manual workflows. They just should not dominate the first navigation layer.

## Home Route Recommendation

The current home page should stop being the main all-in-one workspace.

### Current issue

[web/app/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/page.tsx) is effectively:

- chat entry
- evidence launcher
- simulation launcher
- experiments context
- alignment context
- session manager
- model selector

This is too much for both:

- new human users
- future operator workflows

### Recommendation

Repurpose `/` into a lightweight entry page that routes by role:

- if there are pending interventions -> open `Inbox`
- if there are active runs -> open `Runs`
- if the tenant is not configured -> open `Admin`
- optionally provide a clear "Open Lab Workspace" secondary action

The current chat-centric workspace should move to a secondary route such as:

- `web/app/lab/page.tsx`

This preserves manual exploratory work without forcing it to be the front door.

## Sidebar Redesign

### Current sidebar problem

[web/components/layout/Sidebar.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/layout/Sidebar.tsx) is doing three jobs at once:

- global navigation
- tenant switching
- session/history management

This makes the primary nav visually noisy.

### Recommended sidebar model

Primary section:

- Inbox
- Runs
- Interventions
- Learnings

Secondary section:

- Lab
- Simulation
- Experiments
- Validation
- Evidence
- Alignment
- Overview

Utility section:

- Admin
- Tenant switcher
- History

### Specific recommendation

Move session history and chat management out of the main nav emphasis.

The history drawer is useful, but it should not compete with the main operator navigation hierarchy.

## Component Reuse Strategy

This simplification should reuse existing components rather than replacing everything.

### Components to keep and repurpose

- [web/components/layout/Sidebar.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/layout/Sidebar.tsx)
- [web/components/layout/DetailHeader.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/layout/DetailHeader.tsx)
- [web/components/layout/HistoryDrawer.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/layout/HistoryDrawer.tsx)
- [web/components/simulation/SimulationPanel.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/simulation/SimulationPanel.tsx)
- [web/components/evidence/EvidencePanel.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/evidence/EvidencePanel.tsx)
- [web/components/validation/ValidationFlowHeader.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/components/validation/ValidationFlowHeader.tsx)

### Components that should become more central

- `Agent runs` timeline and status panels
- approval and action controls
- policy-state indicators
- run summary cards

### Components that should become secondary

- chat-first exploration widgets
- dense experiment generation/configuration panels
- simulation-first composition panels on the landing page

## Recommended Phases

### Phase 1: Navigation and route reshaping

Deliver:

- add `Inbox`, `Interventions`, `Learnings`
- promote `Agent runs` into `Runs`
- move lab-heavy routes into a secondary nav group
- simplify `/` to a role-aware landing page

Status: mostly implemented. The current follow-up tightens the sidebar so `Lab` remains visible but subsystem-heavy lab tools sit behind an `Advanced lab` disclosure.

### Phase 2: Homepage decomposition

Deliver:

- move current chat-lab experience into `/lab`
- reduce root page to decision-oriented entry content
- remove overlapping summary modules from `/`

Status: in progress. The current root page is now a control-plane entry that loads a lightweight run snapshot, shows attention/active/recent counts, and recommends Inbox, Runs, Interventions, or Learnings based on current run state.

Visual status: implemented for the primary agentic loop. `/`, `Runs`, `Inbox`,
`Interventions`, and `Learnings` now use the flatter control-surface/list
language defined in `docs/ui-style-direction.md`.

### Phase 3: Shared run-centric data layer

Deliver:

- centralize run, simulation, validation, and experiment loading for control-plane pages
- avoid each route pulling overlapping lists independently

### Phase 4: Interaction simplification

Deliver:

- intervention queue
- focused approval cards
- compact run summaries
- clearer state badges and failure surfaces

Status: in progress. `Inbox` now groups recent work by `Critical`, `Review`,
and `Watching` urgency, `Learnings` starts with recommended operator follow-ups
and separates decision signals from general execution signals, and `Runs`
orders the run selector by operator attention so failed and approval-needed
execution contexts surface first.

## Concrete First Implementation Slice

The first UI slice should be intentionally small:

1. rename `Agent runs` label to `Runs`
2. add placeholder routes for:
   - `Inbox`
   - `Interventions`
   - `Learnings`
3. move current workflow-heavy links into a `Lab` or secondary section in the sidebar
4. simplify `/` so it primarily routes users to the correct workspace instead of rendering the full lab

Status: completed, with the next refinement demoting advanced lab tools further behind a collapsible secondary group.

This gives immediate clarity without forcing a full component rewrite.

## Success Criteria

The simplification is successful when:

1. a new operator can tell what requires attention within 10 seconds of landing
2. primary navigation reflects operator jobs rather than internal lab subsystems
3. the app supports agent supervision first and manual lab exploration second
4. the current deep workflows remain available without dominating the UI

## Recommendation

Do not redesign the entire frontend at once.

Use the current app structure as a migration base:

- promote [web/app/agent-runs/page.tsx](/deep-dive-analysis-agentic-commerce-augmentation/web/app/agent-runs/page.tsx) into the core control-plane view
- add `Inbox`, `Interventions`, and `Learnings`
- demote the lab-heavy pages into a secondary navigation group
- move the current all-in-one home page toward a lightweight role-aware entry point

That will align the frontend with the backend shift we have already started.
