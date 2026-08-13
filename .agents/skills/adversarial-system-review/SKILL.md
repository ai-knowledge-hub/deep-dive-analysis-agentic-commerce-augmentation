---
name: adversarial-system-review
description: Review proposed or implemented changes as they integrate with this agentic commerce platform, not only against the ticket or diff. Use for substantive PR reviews, pre-PR readiness reviews, architecture-sensitive fixes, incident follow-ups, workflow lifecycle or persistence changes, approval and delegation changes, agent or tool execution, belief or memory updates, harness evolution, security-sensitive work, concurrency, migrations, cross-runtime contracts, and changes where data loss, duplication, unauthorized effects, tenant leakage, compatibility failure, misleading projections, or operational failure could emerge outside edited files.
---

# Adversarial System Review

Treat the ticket, design, and implementation as hypotheses. Reconstruct the
affected system from code and executable evidence, then try to falsify the
change's safety and security claims at its boundaries.

Do not implement fixes during a review unless the user also asks for changes.
Preserve review independence: report uncertainty instead of silently assuming
an uninspected dependency or planned control behaves correctly.

## Establish the review frame

1. Read repository instructions and select the applicable contracts using
   [review-dimensions.md](references/review-dimensions.md).
2. Establish the comparison base, changed paths, commits, and worktree state.
   Preserve unrelated user changes.
3. Read the issue, PR description, and earlier feedback as statements of intent,
   not as the boundary of investigation.
4. Name the material consequence classes: unauthorized effects, tenant or
   secret exposure, data loss, duplication, corruption, incompatible state,
   misleading operator state, outage, runaway cost, or irrecoverable work.
5. Distinguish current behavior from proposed architecture. Never treat a
   planned security or safety control as implemented.

## Reconstruct the reachable surface

Trace outward from changed behavior into important unchanged code:

- callers, routes, chat commands, schedulers, callbacks, workers, and tools;
- every writer, retry, recovery, cancellation, cleanup, and administrative path;
- readers including chat, control-plane projections, automation, and external
  integrations;
- authoritative and derived state, persistence, queues, caches, checkpoints,
  receipts, and external effects;
- identity, tenant, authority, approval, budget, effect, and policy transforms;
- prompt, context, worker-result, evidence, belief, memory, and harness
  boundaries;
- migrations, old records, mixed-version producers and consumers, deployment,
  rollback, and reconciliation.

Stop tracing only when a path can no longer affect a material invariant, and
record why. Produce a compact surface or writer/reader map before judging the
change.

## Build an invariant ledger

Express each material invariant as a falsifiable statement. For every invariant
record:

- the state, authority, or user outcome protected;
- every actor and operation that could violate it;
- the enforcement point and irreversible commit point;
- executable evidence or direct inspection supporting it;
- assumptions, planned controls, and missing evidence.

Use the lifecycle, workflow schema, STPA, and security catalogs as independent
contract layers where applicable. Cross-check their semantics against runtime
code; documentation agreement is not executable proof.

Reject a control that merely notices lost authority, duplication, leakage, or
corruption after an irreversible effect unless safe reconciliation or
compensation is demonstrated.

## Challenge boundaries and time

Read all applicable sections of
[review-dimensions.md](references/review-dimensions.md). Select dimensions from
the discovered surface rather than mechanically applying every question.

Use the companion `agentic-commerce-test-design` skill when a finding depends
on missing executable evidence, when reviewing added or changed tests, and when
constructing coordinated mutations, schedule probes, or fault injections.

For each stateful or external operation, place authorization, approval, budget
reservation, lease acquisition, validation, effect, commit, acknowledgement,
projection, and cleanup on a timeline. Interrupt or interleave immediately
before and after each material point.

At minimum, challenge relevant paths with:

- two concurrent valid actors and stale readers;
- duplicate, delayed, reordered, or partially delivered work;
- failure immediately before and after each external effect;
- process loss after an effect but before its durable receipt;
- retry with identical and changed inputs;
- pause, cancellation, revocation, timeout, restart, and late completion;
- identity, tenant, approval, authority, and object substitution;
- prompt injection and malicious retrieved, tool, or child-worker content;
- malformed, oversized, empty, legacy, and semantically equivalent inputs;
- old producer/new consumer and new producer/old consumer combinations;
- projection lag, reconciliation failure, exhausted resources, and dependency
  cascades.

Prefer the smallest executable test or probe capable of falsifying an
invariant. Happy-path coverage does not prove an unexercised interleaving.

## Perform the counter-review

After the first pass, assume the implementation's central model is wrong:

1. Name its strongest hidden assumption.
2. Search for an alternate writer, reader, representation, lifecycle state,
   compatibility path, or deployment topology that contradicts it.
3. Identify what mocks, fixtures, sequencing, or shared implementation make
   impossible to observe in tests.
4. Look for circular verification, such as production code serving as its own
   expected-value oracle or a catalog accepting any existing test-like file.
5. Attempt one credible end-to-end harmful narrative using only valid or
   realistically compromised actors.

Do not conclude while a credible high-consequence narrative remains unresolved.

## Grade evidence

Label conclusions using the strongest evidence actually obtained:

- **Executable proof**: a focused test or probe exercises the failure mechanism.
- **Direct inspection**: the complete reachable path and enforcement point were
  inspected.
- **Architectural inference**: a documented but unexecuted contract supports the
  conclusion.
- **Unknown**: required behavior, environment, code, or authority was unavailable.

Passing a large suite proves only the behaviors it exercised. A security or
safety catalog entry marked `planned` remains an evidence gap.

## Run proportional verification

Run focused tests for the affected paths and every applicable repository gate.
For contract-sensitive backend changes, consider:

```bash
make lint
make arch-check
make bloat-check
make script-entrypoint-check
make safety-traceability-check
make security-traceability-check
git diff --check
```

Use `make web-verify` for frontend changes. Attempt the full relevant suite when
proportionate, but report environment-dependent stalls or excluded tests
precisely; never convert an incomplete run into a pass.

## Report findings

Lead with actionable findings ordered P0 through P3. Emit no finding without a
concrete failure outcome. Each finding must include:

- violated invariant and consequence;
- trigger, interleaving, or adversarial path;
- precise file and line evidence;
- why current checks or tests do not prevent it;
- smallest appropriate remediation direction;
- evidence strength.

Then summarize the reconstructed surface, scenarios examined, commands and
results, residual risks, unknowns, and intentionally unreviewed areas. If there
are no findings, say so plainly without manufacturing low-value comments.

## Completion gates

Finish only when:

- all changed persistent, external, authorized, learned, or user-visible effects
  have known producers and consumers;
- alternate, administrative, background, and legacy paths were searched outside
  the diff;
- every high-consequence invariant has proof or an explicit evidence gap;
- commit points and meaningful failure interleavings were examined;
- applicable lifecycle, schema, STPA, and security contracts were cross-checked;
- the counter-review found no unresolved blocker;
- demonstrated safety is clearly separated from assumption and future work.
