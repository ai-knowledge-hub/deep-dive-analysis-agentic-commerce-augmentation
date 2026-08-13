---
name: agentic-commerce-test-design
description: Design, implement, and review invariant-driven tests for this agentic commerce platform across workflow state, authority, approval, delegation, attempts, effects, tenancy, budgets, messages, evidence, belief, memory, harness evolution, projections, recovery, and compatibility. Use for substantive feature work, architecture-sensitive fixes, security or safety controls, lifecycle and persistence changes, agents and tools, connectors, migrations, concurrency, incident follow-ups, validators, policy gates, and suites that may cover known examples while missing coordinated or cross-boundary failures.
---

# Agentic Commerce Test Design

Derive tests from the platform's canonical contracts and runtime behavior, not
only from acceptance examples or implementation branches. Treat requirements,
code, existing tests, safety controls, and security controls as independent
evidence layers that may conflict.

Use a general failure-space method when available, but keep this skill
standalone. Read [platform-test-dimensions.md](references/platform-test-dimensions.md)
to select project-specific invariants and interactions. Read
[verification-strategies.md](references/verification-strategies.md) when choosing
test techniques or challenging an existing suite.

## Route To Canonical Contracts

Read only the documents causally relevant to the change, but read selected
documents completely:

- product scope or beta boundary: `docs/platform-modernisation-plan-v2.md`;
- workflow, revision, task, attempt, delegation, event, result, checkpoint, and
  authority semantics: `docs/decisions/0001-workflow-task-delegation-schema.md`;
- governed lifecycle, effects, delegation, belief, memory, or harness behavior:
  `docs/safety/README.md` and its current catalog and analysis;
- identity, authority, approval, workers, tools, connectors, messages, tenancy,
  secrets, observability, belief, memory, or harness behavior:
  `docs/security/README.md` and its current model and catalog;
- current runtime behavior: executable domain and application code plus focused
  tests;
- documents under `docs/history/`: context only, never current authority.

Do not treat a planned safety or security control as implemented. A catalog entry
marked implemented is credible only to the exact behavior exercised by its
declared executable verification.

## Build The Platform Model

Trace the requested behavior through:

- human, API, chat, scheduler, worker, callback, reconciliation, migration, and
  administrative producers;
- authoritative workflows, revisions, tasks, attempts, delegations, commands,
  events, results, checkpoints, receipts, beliefs, memories, and harness state;
- identity, tenant, authority, approval, policy, effect-class, capability, and
  budget transformations;
- tools, connectors, models, child workers, messages, context capsules, and
  external effects;
- persistence, queues, caches, projections, operator views, retries,
  cancellation, compensation, rebuild, and rollback.

For every material outcome record a falsifiable invariant, independent
authority, writers, readers, enforcement point, irreversible commit point,
observable oracle, and evidence gap.

## Generate Platform-Specific Failures

At minimum, challenge applicable invariants with:

- tenant, principal, workflow, revision, task, attempt, approval, authority,
  policy, object, connector, and receipt substitution;
- delegated authority or budget expansion, including concurrent reservations;
- stale revision scheduling, lease expiry, reassignment, stale fencing tokens,
  late results, duplicate results, and split ownership;
- duplicate or changed commands, multi-event atomicity, replay, ordering gaps,
  and crash around an external effect and durable receipt;
- pause, cancellation, revocation, timeout, compensation, restart, and late
  completion across every active child and external operation;
- prompt injection and malicious retrieved, tool, connector, model, or child
  content attempting to become authority, policy, approval, memory, or harness;
- cross-tenant context, cache, queue, telemetry, projection, belief, memory, and
  message contamination;
- secret-bearing inputs across prompts, results, errors, logs, traces, metrics,
  transcripts, and outbound requests;
- stale priors, poisoned evidence, contradictions, unreviewed memory promotion,
  global harness promotion, and rollback failure;
- projection lag, cursor gaps, false terminal states, missing receipts, and
  reconciliation failure;
- old/new producer-consumer combinations, missing fields, deployment ordering,
  migration, and rollback readers;
- exhausted depth, concurrency, tokens, cost, actions, retries, time, queues,
  storage, dependencies, and telemetry cardinality.

For each relationship test one-sided deletion, deletion of all reciprocal sides,
valid substitution, cross-object swap, duplication, reordering, unexpected
addition, and coordinated internally consistent downgrade. Required membership
must come from an independent contract rather than the submitted relation.

## Model Time And Interactions

Place authenticate, authorize, approve, reserve, lease or fence, execute effect,
commit, receipt, acknowledge, project, compensate, reconcile, and cleanup on a
timeline. Inject failure immediately before and after each applicable material
point.

Cluster dimensions that share authority, tenant scope, workflow family, graph
revision, attempt ownership, budget pool, external receipt, durable record,
projection, recovery path, or trust boundary. Use exhaustive coverage for small
critical spaces, all modeled transitions and pre/post fault points, every
semantic mutation for security-critical relationships, pairwise coverage for
uncoupled dimensions, and stronger interactions inside high-consequence
clusters.

## Select Independent Test Oracles

Prefer independently represented contracts, small reference models,
metamorphic relations, durable receipts, and reconciled authoritative state.
Reject circular verification:

- production code calculating its own expected output;
- submitted catalog membership defining its own completeness;
- shared parser, normalization, authorization, or derivation helpers hiding the
  defect in both implementation and test;
- projections, logs, mocks, status codes, or collected test names treated as
  durable proof.

When no independent oracle exists, report the control or invariant as unproven.

## Challenge The Suite

Before accepting tests, make harmful changes that remain syntactically and
internally valid:

1. Remove a required capability, control, gap, task, event, scope, or verification
   and update every derived field consistently.
2. Remove both sides of a reciprocal relationship.
3. Substitute another valid tenant, principal, workflow family, revision,
   attempt, approval, receipt, or object.
4. Move policy enforcement from effect or commit time to admission time only.
5. Repeat effects after receipt loss or commit from a stale attempt.
6. Pass serially while oversubscribing authority or resources concurrently.
7. Write state that old readers or rollback code cannot interpret.
8. Suppress, delay, duplicate, reorder, or forge the evidence used by the test.

Correct the domain model or oracle when a harmful mutation survives; do not only
add a narrow regression assertion.

## Quantify And Verify

Report explicit numerators and denominators for applicable invariant,
transition, dangerous illegal-transition, relationship-mutation, fault-point,
authority-boundary, interaction, mutation-score, and recovery coverage. State
untested partitions as residual risk.

Run focused tests first, followed by applicable repository gates:

```bash
make lint
make arch-check
make bloat-check
make script-entrypoint-check
make safety-traceability-check
make security-traceability-check
git diff --check
```

Use `make web-verify` for frontend changes. Report incomplete or
environment-dependent runs precisely; never present them as passing.

## Deliverables

Return or create, as appropriate:

1. platform surface and authority map;
2. invariant ledger with independent oracles;
3. bounded failure-space and interaction model;
4. risk-ranked test portfolio and implemented tests;
5. mutation, schedule, and fault-injection results;
6. quantitative coverage, conflicts, unknowns, and residual risks.
