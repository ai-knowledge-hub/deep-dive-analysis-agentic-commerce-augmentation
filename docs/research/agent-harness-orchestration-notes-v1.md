# Agent Harness and Orchestration Research Notes v1

Status: architecture input for Phase 1
Date: 2026-08-10
Scope: long-running work, parallel subagents, recursive harnesses, goals, and
continual harness state

## Why this research exists

The platform plan already separates workflow, task, attempt, assignment,
action, belief, and memory state. Recent harness work adds two more concepts
that must be modelled explicitly before implementation:

- a persistent execution environment that can hold context and invoke tools or
  child agents programmatically
- a supplemental harness state that can retain prompts, memories, skills, and
  reusable worker specifications across turns

Neither concept is a replacement for the durable workflow kernel. Both are
inputs to it and must remain subordinate to tenant, policy, authority, budget,
approval, and audit controls.

## Evidence reviewed

### Recursive context and programmatic orchestration

The [Recursive Language Models paper](https://arxiv.org/abs/2512.24601)
treats a long prompt as an external variable in a REPL. The model examines and
decomposes that variable and may make recursive model calls over selected
parts. The important architectural idea is out-of-context data access, not
unbounded recursion.

The [Recursive Agent Harnesses paper](https://arxiv.org/abs/2606.13643)
extends the recursive unit from a model call to a complete agent harness with
tools, code execution, planning, and parallel workers. That makes each child a
real controlled process with its own authority, resources, lifecycle, and
failure modes.

[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model)
separates multi-agent coordination from programmatic tool calling. It recommends
programmatic execution for bounded, predictable stages and requires explicit
eligible tools, output schemas, evidence, concurrency, retry, and stopping
limits. Approval and final semantic validation remain direct control points.

### Isolated and long-running workers

[Claude Code subagent documentation](https://code.claude.com/docs/en/sub-agents)
distinguishes fresh isolated subagent contexts from full-context forks, narrows
tool access, supports background execution, and can isolate file changes in
worktrees. Completion notifications and API failures are explicit; admission or
partial output is not treated as successful completion. Returned reports are
also scanned because child context may contain untrusted instructions.

[Anthropic's long-running harness analysis](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
uses durable progress artifacts, feature status, repository history, and
repeated verification to bridge context windows. The useful lesson is that
continuity comes from inspectable state and evidence, not from asking a model
to remember everything.

### Local Hermes and Prime implementations

The local Hermes checkout was reviewed at commit `893792c99`. Its useful
patterns are:

- a narrow agent core with optional capability at the edges
- a byte-stable conversation prompt and deliberate context compaction
- bounded delegated-agent lifecycle contracts with cancellation and retained
  terminal records
- durable queue/dispatcher concepts with stale-claim recovery and failure
  limits
- memory-provider fan-out that isolates failures, bounds waits, serializes
  writes, and distinguishes durable writes from best-effort prefetch

The local Prime Agent checkout was reviewed at commit `a18809e00`. Its useful
patterns are:

- a persistent IPython kernel as a model-facing control environment
- typed host requests that keep goal, child lifecycle, accounting, and policy
  authoritative in the host
- child admission returning a handle immediately, with results arriving later
  through explicit messages or files
- parent-scoped child registries, depth limits, retained transcripts, and usage
  attribution
- session-local continual harness state by default, an immutable base prompt,
  focused evidence-backed refinement, snapshots, and rollback
- explicit goal completion, bounded autonomous continuation, heartbeats, and
  schedules as distinct mechanisms

## Architecture decisions for this platform

### Adopt in contracts now

1. **The orchestrator remains authoritative.** A REPL, model context, child
   transcript, or harness entry cannot directly grant authority, approve an
   action, commit shared state, or declare workflow completion.
2. **Admission, progress, result, validation, and commit are distinct states.**
   A returned child handle or partial report is not a successful task result.
3. **Recursive and parallel work consumes reserved budgets.** Depth,
   concurrency, tokens, cost, wall time, actions, and retries are enforced by
   the host and inherited without expansion.
4. **Parallel workers are isolated producers.** They return typed, provenance-
   carrying results. Only the coordinator validates and commits workflow,
   belief, or memory state.
5. **Long-running work uses durable evidence.** Goals, checkpoints, leases,
   heartbeats, receipts, progress projections, and completion gates survive
   context compaction and client disconnection.
6. **Context is data.** Prompt variables, retrieved memory, web content, child
   reports, and tool output cannot mutate policy or harness configuration by
   instruction.
7. **Harness state is a versioned configuration aggregate.** Supplemental
   prompts, memories, skills, and worker specifications require scope,
   provenance, evidence, evaluation, approval policy, immutable snapshots, and
   rollback.
8. **Execution environment state is not belief state.** REPL variables and
   checkpoints may assist execution recovery but cannot become the canonical
   Bayesian prior, evidence ledger, posterior, or promoted memory.

### Keep outside the beta execution path

The current beta scope already excludes recursive subagent spawning,
self-modifying policies or workflow definitions, unreviewed memory promotion,
and open-ended peer-to-peer messaging. This research does not change that
boundary.

Continual harness refinement may later create a candidate change, but beta
runtime code must not automatically promote it. Recursive execution may be
evaluated behind a disabled capability after bounded one-level parallel
delegation is reliable. The Phase 4 implementation should begin with read and
recommend workers, deterministic joins, and coordinator validation.

## Consequences for the build sequence

- Phase 1 STPA covers delegation, background execution, result aggregation,
  goal completion, and harness promotion as control actions or causal factors.
- Phase 2 chat artifacts must distinguish queued, admitted, running, partial,
  validated, committed, paused, and complete states.
- Phase 3 owns durable commands, leases, checkpoints, heartbeats, receipts,
  recovery, reservations, and completion gates.
- Phase 4 owns isolated context capsules, worker registries, authority and
  budget non-expansion, typed results, parallel joins, and coordinator-only
  commits.
- Continual harness promotion remains a later safety-governed capability with
  evaluation and rollback, not an implicit property of memory or workflow
  execution.
