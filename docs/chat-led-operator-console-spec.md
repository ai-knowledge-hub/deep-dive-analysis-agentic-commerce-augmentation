# Chat-Led Operator Console Spec

Status: future reference specification
Last verified: 2026-09-05
Current behavior: `docs/operator-experience.md`

This document defines the recommended operator experience for the platform as it evolves into an agent-first execution system.

The core idea is:

- chat becomes the primary guidance layer
- structured control-plane views remain the source of truth for execution state

This is not a chat-only UI. It is a chat-led operator console.

## Product Principle

The operator should be able to manage autonomous backend execution in two modes at the same time:

1. conversationally
2. structurally

Conversational mode is for:

- understanding
- summarization
- steering
- explanation
- follow-up questions

Structural mode is for:

- approvals
- intervention
- auditability
- filtering
- comparison
- bulk operations

The UI should always support both.

## Why This Model Fits The Platform

Your backend is moving toward:

- first-class principals
- explicit runs/actions/events
- policy-governed autonomy
- tool and skill execution

That creates a lot of execution state that operators need help interpreting.

Chat is the best layer for:

- "what happened?"
- "why did this fail?"
- "what should I do next?"
- "summarize this run"
- "show me the relevant evidence"

But structured UI is still essential because:

- approvals must be explicit
- policy state must be inspectable
- timelines and receipts must be auditable
- many intervention actions are faster in structured controls

## Recommended Interaction Model

The operator console should be built around three coordinated surfaces:

1. **Agent Briefing**
2. **Execution Workspace**
3. **Operator Chat**

### 1. Agent Briefing

This is the top summary layer.

It should answer:

- what needs attention right now
- what is currently running
- what changed recently
- what the recommended next action is

This is not raw metrics. It is a short machine-generated executive summary.

Example:

- `3 runs need attention`
- `1 policy block requires approval`
- `2 validation jobs completed since your last visit`
- `Recommended next action: review run_123 before allowing synthetic validation retries`

### 2. Execution Workspace

This is the structured source of truth.

Depending on the current route, it should show:

- inbox queue
- runs list
- selected run timeline
- interventions queue
- learning deltas

This is where operators:

- approve/reject
- pause/cancel
- inspect event timelines
- review outputs
- see policy state
- compare runs

### 3. Operator Chat

This is the conversational layer attached to the current workspace context.

The chat should be aware of:

- current tenant
- selected run
- current page context
- current filters
- recent errors/policy events

The chat should support:

- explanation
- navigation
- summarization
- command-like steering

## Chat Responsibilities

The operator chat should be able to do five jobs well.

### 1. Explain

Examples:

- "Why did this run fail?"
- "Why is this action blocked?"
- "What does this validation result mean?"
- "What changed between these two runs?"

### 2. Summarize

Examples:

- "Summarize this run for an account manager."
- "Give me the 3 most important issues in this queue."
- "Summarize what changed since yesterday."

### 3. Navigate

Examples:

- "Open the run that failed most recently."
- "Show me the evidence behind this action."
- "Take me to the validation result for this run."
- "Filter to policy failures only."

### 4. Steer

Examples:

- "Pause similar runs."
- "Retry this with safe auto disabled."
- "Queue a validation rerun."
- "Escalate this to manual review."

### 5. Translate

Examples:

- "Explain this in business language."
- "What is the risk if I approve this?"
- "What does this mean for the brand team?"

## What Chat Should Not Replace

Chat should not replace:

- approval buttons
- timeline inspection
- policy badges
- receipts
- bulk actions
- filtering controls
- hard audit surfaces

Those should remain explicit UI controls.

## Default Screen Design

The default operator console should look like this conceptually:

```text
+---------------------------------------------------------------+
| Agent Briefing                                                |
| "3 runs need attention. 1 policy block requires approval."    |
+-----------------------------+---------------------------------+
| Execution Workspace         | Operator Chat                   |
|                             |                                 |
| Inbox / Runs / Interventions| Context-aware agent assistant   |
| Structured queue and state  | Explain, navigate, steer        |
| Explicit actions            | Natural language interaction    |
+-----------------------------+---------------------------------+
```

On mobile, the chat becomes a bottom sheet or secondary tab.

## Route Strategy

This spec builds on [the UI simplification roadmap](ui-control-plane-simplification-plan.md).

### Primary routes

- `/inbox`
- `/runs`
- `/interventions`
- `/learnings`

### Secondary routes

- `/lab`
- `/simulation`
- `/experiments`
- `/validation`
- `/evidence`
- `/alignment`
- `/overview`

### Recommended role of each route

#### `/inbox`

Primary view:

- attention queue
- failures
- policy blocks
- stuck runs

Chat behavior:

- summarize the queue
- explain why items are here
- recommend prioritization

#### `/runs`

Primary view:

- run list
- selected run
- action timeline
- outputs

Chat behavior:

- narrate the selected run
- explain outputs and transitions
- open linked evidence or validation context

#### `/interventions`

Primary view:

- approvals
- rejects
- retries
- pauses
- escalations

Chat behavior:

- explain risks
- draft rationale
- recommend safest action

#### `/learnings`

Primary view:

- what changed
- new evidence
- calibration shifts
- skill/harness performance trends

Chat behavior:

- summarize learnings
- interpret trends
- connect operational changes to business meaning

## How This Maps To Current Code

### Best current base for structured execution

- [agent runs page](../web/app/agent-runs/page.tsx)

This should become the foundation of `/runs`.

### Best current base for chat

- [chat page](../web/app/page.tsx)
- [chat window](../web/components/chat/ChatWindow.tsx)

The chat UI should be reused, but repurposed from "consumer-style exploration chat" into "operator execution chat".

### Best current base for shared navigation

- [sidebar](../web/components/layout/Sidebar.tsx)

This should be updated to reflect:

- primary control-plane routes
- secondary lab routes

### Best current base for summary header

- [detail header](../web/components/layout/DetailHeader.tsx)

This can evolve into the `Agent Briefing` area.

## Required Backend Support

To make this UX real, the backend needs operator-chat-aware endpoints or orchestration helpers.

At minimum, chat should be able to retrieve:

- current inbox summary
- selected run summary
- recent failures and policy events
- links between runs, validation jobs, evidence, and experiments
- recommended next actions

The chat layer should not scrape the UI. It should consume structured execution state.

## Recommended Chat Commands

These should be supported either as true commands or as natural-language intents:

- `summarize current queue`
- `explain selected run`
- `show policy failures`
- `open latest failed run`
- `show validation evidence`
- `pause this run`
- `approve selected action`
- `retry safely`
- `compare with previous run`
- `what changed since yesterday`

## Trust Model

The operator must always know:

- what the agent is explaining
- what the agent is inferring
- what action is proposed
- what action has actually executed

So the chat should clearly separate:

- explanation
- recommendation
- action

It should never silently mutate state.

## UX Guardrails

### Guardrail 1

Every action proposed in chat must map to a visible structured state change.

### Guardrail 2

Every approval-worthy action must still require explicit confirmation in the UI.

### Guardrail 3

The selected run or queue context should always be visible while chatting.

### Guardrail 4

Chat should default to explanation and recommendation, not execution.

## First Implementation Slice

The first version should be intentionally narrow.

### Step 1

Embed an operator chat panel into the future `/runs` page.

### Step 2

Make the chat aware of:

- current selected run
- current tenant
- current page filters

### Step 3

Support these first chat jobs:

- explain selected run
- summarize failures
- explain blocked action
- recommend next action
- navigate to related evidence/validation section

### Step 4

Only after that, support low-risk operator actions from chat.

## Recommended Decision

Yes, the human control panel should become chat-led.

But the right implementation is:

- **chat as the default operator interaction layer**
- **structured UI as the execution truth layer**

That will give the platform:

- a much more natural operator experience
- stronger interpretability
- safer intervention flows
- a differentiated interface for supervising agentic commerce execution
