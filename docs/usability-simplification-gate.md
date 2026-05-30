# Usability Simplification Gate

Status: current
Last updated: 2026-05-30

This gate exists to prevent backend and agent-runtime complexity from leaking into the default operator experience.

The product goal is not to expose every mechanism. The product goal is to help an operator improve commerce discoverability with a small number of clear decisions.

## Default Mental Model

The primary operator model is:

```text
Goal -> Agent suggestion -> Human review -> Approved action -> Outcome
```

Daily users should be able to complete a useful flow without understanding Bayesian updates, calibration profiles, memory artifacts, retrieval snapshots, command preflights, registry fingerprints, or harness profiles.

## Primary Product Nouns

Use these in primary screens, onboarding copy, and task flows:

- Goal
- Product
- Run
- Recommendation
- Review
- Approval
- Risk
- Outcome
- Insight
- Next action

## Internal Mechanism Nouns

These terms are allowed, but only behind progressive disclosure:

- belief revision
- memory artifact
- calibration profile
- hypothesis
- retrieval snapshot
- policy profile
- harness profile
- command preflight
- compensating action
- registry fingerprint
- posterior

Preferred placements:

- "Why did the agent decide this?"
- "View evidence"
- "View audit details"
- "Advanced"
- Admin configuration
- Lab/debug views

## Progressive Disclosure Levels

### Novice

Novice operators see:

- what needs attention
- what the agent recommends
- what happens if they approve or reject
- what changed after the action

### Advanced

Advanced operators can open:

- evidence
- validation
- simulation
- experiment details
- policy warnings
- recovery details

### Expert

Experts can inspect:

- registry releases
- harness posture
- policy profiles
- calibration movement
- memory artifacts
- raw receipts and audit trails

## Usability Acceptance Checklist

Every user-facing feature should pass this checklist before more surface area is added:

- Can the operator answer "what should I do next?" within 10 seconds?
- Is there one primary action on the screen?
- Does the screen use operator words before implementation words?
- Are risky decisions routed through review, approval, or intervention?
- Are internal mechanism terms hidden behind explanation, audit, admin, or lab affordances?
- Can a new operator follow "select product -> run optimization -> review recommendation -> approve/reject -> monitor outcome" without reading architecture docs?
- Does the feature belong in Inbox, Runs, Interventions, Insights, Lab, or Admin?

## Navigation Contract

Primary:

- Inbox
- Runs
- Interventions
- Insights

Secondary:

- Lab

Administrative:

- Admin

Advanced lab routes can remain available, but they should not become the default mental model.

## PR Review Prompt

Use this prompt when reviewing product-surface changes:

> Does this change help an operator complete a business task with less conceptual load, or does it make them understand more of the internal system?

If the answer is "more internal system", the change should either be moved behind progressive disclosure or redesigned around the operator decision.
