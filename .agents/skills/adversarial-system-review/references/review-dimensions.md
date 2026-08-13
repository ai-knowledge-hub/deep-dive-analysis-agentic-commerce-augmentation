# Agentic Commerce Review Dimensions

Use this reference to select questions from the reachable change surface. Do
not treat it as a checklist and do not claim a dimension was reviewed without
evidence.

## Contract routing

Read only the contracts causally relevant to the change, but read selected
documents completely.

| Changed concern | Contract sources |
| --- | --- |
| Product scope, phase, or beta boundary | `docs/platform-modernisation-plan-v2.md` |
| Workflow status and transitions | `domain/workflow/lifecycle.py`, `tests/modules/test_workflow_lifecycle.py` |
| Workflow, task, revision, attempt, delegation, event, or checkpoint semantics | `docs/decisions/0001-workflow-task-delegation-schema.md` |
| Losses, hazards, unsafe control actions, or constraints | `docs/safety/stpa-workflow-control-analysis-v1.md`, `docs/safety/safety-controls-v1.yaml` |
| Assets, trust boundaries, threats, security controls, detections, or gaps | `docs/security/agent-workflow-threat-model-v1.md`, `docs/security/security-controls-v1.yaml` |
| Parallel agents, recursive context, goals, or continual harness state | `docs/research/agent-harness-orchestration-notes-v1.md` |
| Chat and operator projections | `docs/operator-experience.md`, `docs/chat-led-operator-console-spec.md` |
| Current runtime behavior | `docs/agentic-layer.md` plus executable code and tests |

Machine-readable catalogs are normative for their traceability relationships,
but `implemented` status is credible only when the named executable
verification exercises the claimed behavior.

## Workflow state and ownership

- Identify the authoritative workflow, active graph revision, task membership,
  attempt, result, checkpoint, command, event, and projection state.
- Enumerate human, API, scheduler, worker, callback, recovery, reconciliation,
  migration, and administrative writers.
- Check creation, transition, pause, resume, cancellation, timeout, failure,
  compensation, terminal, archival, and restoration behavior.
- Confirm scheduling cannot read removed or superseded tasks from an inactive
  revision.
- Confirm a stale worker cannot commit merely because lost ownership is detected
  after the write.
- Check whether an identifier, idempotency key, lease, or receipt can be reused
  while older work remains alive.

## Authority, approval, policy, and budget

- Derive identity and tenant from trusted claims at every entry point and
  continuation; reject self-asserted principal and tenant fields.
- Trace the immutable workflow authority envelope into assignments, child work,
  tools, connectors, and commits.
- Apply one consistent non-expansion rule to authority and resources. Equality
  may be valid, but expansion may not.
- Bind approval to the exact payload, effect, evidence, authority, policy,
  revision, expiry, and revocation state used at execution.
- Enforce authorization at the effect and commit points, not only at the route,
  planner, or UI.
- Reserve depth, concurrency, tokens, cost, time, actions, and retries atomically
  so concurrent valid workers cannot oversubscribe a parent budget.

## Time, concurrency, and idempotency

- Place validation, reservation, lease/fence acquisition, external effects,
  commit, receipt, acknowledgement, and release on a timeline.
- Interleave two valid commands, approvals, schedulers, attempts, callbacks, or
  updates around each material boundary.
- Separate command deduplication from event identity so one command can append
  multiple events atomically.
- Crash after an external effect but before its receipt and determine whether
  retry duplicates, reconciles, or safely blocks.
- Exercise lease expiry, reassignment, late result, duplicate result, stale
  fencing token, delayed heartbeat, and split-brain execution.
- Verify pause, cancellation, revocation, timeout, and compensation reach all
  active and external work with acknowledgement or escalation.

## Agent, model, tool, and message boundaries

- Treat user prompts, retrieved content, tool output, model output, child-worker
  reports, memory, and supplemental harness state as untrusted data.
- Ensure none can grant tenant scope, authority, approval, capability, budget,
  policy, configuration, or trusted provenance.
- Verify context capsules are minimal, tenant scoped, size bounded, and use
  opaque secret handles rather than ambient credentials.
- Require typed, provenance-carrying, size-bounded results and coordinator-side
  validation before shared-state mutation.
- Authenticate inter-agent messages; bind them to workflow family, task,
  attempt, tenant, sender, recipient, and freshness; bound rate and queues.
- Check connector target validation, egress allowlists, redirects, private
  addresses, DNS rebinding, timeouts, response size, and content handling.

## Evidence, belief, memory, and harness state

- Trace evidence source, capture time, tenant, quality, independence, and
  transformation into observations and Bayesian updates.
- Require versioned priors and detect stale, contradictory, poisoned, or
  mis-scoped evidence before commit.
- Separate session or conversation context from durable belief and governed
  memory state.
- Confirm only the coordinator commits shared belief, memory, or harness state
  and that every commit has provenance and rollback evidence.
- Keep the base harness immutable. Treat supplemental prompts, goals, memories,
  skills, and worker specs as candidates that are session-local by default.
- Require evaluation, independent approval, versioning, provenance, promotion
  scope, regression detection, and rollback before reuse.
- Do not allow partial work, a child admission, an exhausted budget, or a passed
  subset gate to imply goal completion.

## Security, tenancy, secrets, and supply chain

- Trace tenant identity through storage keys, caches, queues, context, results,
  memory, receipts, logs, metrics, traces, and projections.
- Test indirect object references and tenant substitution at every entry point,
  background continuation, filter, and cursor.
- Check raw secrets cannot enter prompts, results, transcripts, exceptions,
  logs, traces, metrics labels, or unrestricted outbound requests.
- Inspect credential scoping, rotation, revocation, opaque handles, redaction,
  retention, and access auditing.
- Pin and verify provenance for dependencies, models, prompts, skills, plugins,
  registries, worker specs, and evaluation fixtures.
- Compare the change against mapped `THR-*`, `SEC-*`, `SDET-*`, and `GAP-*`
  records. A gap is a release decision, not an implemented defense.

## Failure, recovery, and resource isolation

- Fail each dependency before and after its side effect and classify the result
  as retryable, terminal, or ambiguous.
- Verify compensation targets the exact effect from the failed attempt and does
  not overwrite newer user or workflow state.
- Check restart and reconciliation cannot revive canceled work, duplicate a
  committed effect, or silently convert ambiguity into success.
- Bound loops, fan-out, retries, context, message size, queue depth, concurrency,
  storage versions, telemetry cardinality, and external cost.
- Isolate tenant, workflow, connector, model, queue, cache, database, and worker
  resources with quotas, bulkheads, backpressure, timeouts, and circuit breakers.
- Confirm a local dependency or tenant failure cannot cascade through shared
  pools or misleading stale projections.

## API, chat, and control-plane semantics

- Check status codes, retry signals, idempotency responses, partial success,
  event cursors, and client interpretation.
- Treat chat and control-plane views as projections, not independent authority.
- Expose durable revision, approval, lease, result, receipt, budget, recovery,
  and projection-lag state where operator action depends on them.
- Follow late responses through navigation, unmount, changed selection, pause,
  cancellation, and reconnection.
- Verify optimistic UI and streaming merge keys cannot show false completion,
  hide failure, or let stale data overwrite a newer explicit operator decision.
- Confirm a technically valid internal state is still clear and safe for the
  operator making an irreversible decision.

## Compatibility and evolution

- Exercise old records missing new fields and mixed old/new producer-consumer
  combinations.
- Inspect migrations, lazy backfills, defaults, feature flags, rollback order,
  generated contracts, stored events, cache keys, and external clients.
- Verify rollback can read state written by the new version.
- Compare current runtime behavior with new contracts before calling a change
  backward compatible.
- Distinguish a deterministic legacy conflict from a transient dependency
  failure so retries cannot amplify damage.

## Test and evidence traps

- Ticket anchoring: the described solution is not the full reachable system.
- Diff tunnel vision: bypasses and incompatible consumers often live elsewhere.
- Happy-path saturation: many success tests do not cover one critical race.
- Post-check fencing: noticing lost ownership after commit is not prevention.
- Mocked-away reality: sequential or in-memory substitutes can erase the fault.
- Circular verification: shared implementation is not an independent oracle.
- Catalog self-certification: an existing file or narrow test cannot prove a
  broader control claim.
- Large-suite confidence: suite size does not establish a particular invariant.
- Planned-control inflation: documentation and ownership do not equal a defense.
- Reviewer convergence: form an independent system model before accepting the
  implementation's assumptions.
