# User Testing Plan

Status: current
Last updated: 2026-06-17

This plan validates whether the current agentic commerce control plane is ready
for broader product development after the first usability simplification pass.

## Goal

Validate whether a new operator can understand and use the primary control-plane
loop without needing to understand internal runtime mechanics.

The loop under test is:

```text
Control Plane -> Inbox -> Runs -> Interventions -> Insights -> Lab only when needed
```

## What We Need To Learn

1. Can a new operator tell what needs attention within 10 seconds?
2. Can they identify the recommended next action without scanning every panel?
3. Can they explain what the agent is doing and why?
4. Can they approve, reject, retry, or pause work with confidence?
5. Can they find supporting evidence or validation context when needed?
6. Do internal terms still leak into the primary workflow?
7. Does Lab feel like an advanced workspace rather than the product front door?

## Participants

Use 5-7 sessions before the next major platform slice:

- 2 commerce/growth operators
- 1 product or merchandising stakeholder
- 1 technical operator or solutions engineer
- 1 less technical user who understands the business goal but not the system

If only internal testers are available, separate them into:

- people familiar with the codebase
- people unfamiliar with the current UI

## Setup

Use seeded data that includes:

- at least one active run
- at least one failed or blocked run
- at least one approval-needed action
- at least one recovery proposal
- at least one validation result
- at least one insight/follow-up item

Avoid explaining backend concepts before the test. Give only the business
context:

> This product helps a commerce team supervise agent-run work that improves how
> products are represented, discovered, validated, and monitored.

## Tasks

### Task 1: First Landing

Start on `/`.

Ask:

- What do you think needs attention?
- Where would you click first?
- What do you expect will happen?

Pass signal:

- User can choose Inbox, Runs, Interventions, or Insights for a clear reason.

### Task 2: Triage Work

Open Inbox.

Ask the user to find the most important item and describe why it matters.

Pass signal:

- User can distinguish critical, review, and watching items without help.

### Task 3: Understand A Run

Open Runs and select an active or failed run.

Ask:

- What is the agent doing?
- What already happened?
- What is the next safe action?

Pass signal:

- User uses run state, action review, timeline, and chat without needing a
  technical explanation of registry, harness, receipts, or payloads.

### Task 4: Make A Human Decision

Open Interventions.

Ask the user to approve, reject, retry, or pause one item.

Pass signal:

- User can explain the risk and expected result before acting.

### Task 5: Review Outcome And Learning

Open Insights.

Ask:

- What changed?
- What should the team do next?

Pass signal:

- User can identify one useful follow-up without reading raw audit context.

### Task 6: Advanced Drilldown

Ask the user to find deeper simulation, evidence, experiment, or validation
context only after they request more detail.

Pass signal:

- User understands that Lab is available for deeper investigation, not required
  for every task.

## Observation Checklist

Record each issue with:

- screen
- task
- quote or behavior
- severity
- whether it blocks the primary loop

Severity:

- `P0`: user cannot continue
- `P1`: user chooses a risky or wrong action
- `P2`: user hesitates or needs explanation
- `P3`: wording or layout polish issue

## Metrics

Track:

- time to first correct click from `/`
- whether the user finds the highest-priority intervention
- whether the user can explain a selected run in their own words
- number of internal terms the user asks about
- number of times the user opens Lab before it is needed
- confidence rating after each task, 1-5

## Decision Gate

Before the next major platform slice:

- Fix all `P0` and `P1` findings.
- Batch `P2` findings into a focused UX cleanup PR.
- Keep `P3` findings for polish unless they repeat across users.

The next platform slice is safe to start only when users can complete Tasks 1-5
without moderator explanation of internal runtime concepts.
