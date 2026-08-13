# Agentic Commerce Optimisation Platform

This repository is evolving toward a chat-first, governed agent-workflow
platform. Preserve current runtime compatibility while implementing the
contracts in the canonical modernisation plan.

## Canonical guidance

- Read `docs/platform-modernisation-plan-v2.md` for product scope, delivery
  phases, beta boundaries, and the current sequence.
- Read `docs/decisions/0001-workflow-task-delegation-schema.md` for workflow,
  revision, task, attempt, delegation, event, result, and checkpoint semantics.
- Read `docs/safety/README.md` before changing governed control actions,
  lifecycle behavior, delegation, effects, belief, memory, or harness state.
- Read `docs/security/README.md` before changing identity, authority, approval,
  workers, tools, connectors, messages, tenancy, secrets, observability, belief,
  memory, or harness behavior.
- Treat documents under `docs/history/` as context, not current authority.

## Repository skills

- Use `.agents/skills/adversarial-system-review/SKILL.md` for substantive PR or
  pre-PR reviews, architecture-sensitive fixes, incident follow-ups, lifecycle
  and persistence changes, agent or tool execution, belief or memory updates,
  harness evolution, security-sensitive changes, concurrency, migrations, and
  cross-boundary contracts. It reconstructs system reach, invariants, failure
  interleavings, and risks beyond the ticket and edited files.
- Use `.agents/skills/agentic-commerce-test-design/SKILL.md` when designing,
  implementing, or reviewing tests for architecture-sensitive changes,
  security or safety controls, workflow lifecycle and persistence, authority,
  approval, delegation, effects, tenancy, agents and tools, belief, memory,
  harness evolution, concurrency, migrations, recovery, and cross-boundary
  contracts. It derives invariant-driven tests from the platform's canonical
  contracts and challenges suites with coordinated semantic mutations.

## Verification

Prefer focused tests first, followed by the applicable repository gates:

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
environment-dependent test runs precisely; never present them as passing.
