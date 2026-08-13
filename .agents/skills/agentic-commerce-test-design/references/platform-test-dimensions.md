# Platform Test Dimensions

## Workflow State And Ownership

- Active graph revision exclusively determines schedulable task membership.
- Every transition follows the canonical lifecycle and preserves terminality.
- Only the current assigned and fenced attempt may commit a result or effect.
- Pause, cancellation, revocation, timeout, compensation, and recovery reach all
  active work or produce durable visible escalation.
- Commands deduplicate independently from events so one command can atomically
  append multiple distinct events.

## Identity, Authority, Approval, And Budget

- Trusted claims, never request parameters or model content, determine principal
  and tenant identity.
- Workflow and delegated authority are immutable host-issued envelopes; child
  authority is a subset of its parent.
- Approval binds to exact payload, effect, evidence, authority, policy, graph
  revision, expiry, and revocation state used at execution.
- Capabilities and effect classes are enforced at execution and commit.
- Depth, concurrency, tokens, cost, actions, retries, and time are reserved
  atomically and cannot expand through parallel work.

## Effects, Idempotency, And Recovery

- Retry may repeat computation but cannot repeat a committed external effect.
- Idempotency binds to scoped identity and a semantic request hash; changed
  replays conflict deterministically.
- Ambiguous external outcomes block, reconcile, or compensate using durable
  provider evidence rather than becoming success silently.
- Compensation targets the exact effect and attempt and cannot overwrite newer
  user or workflow state.

## Agents, Tools, Messages, And Content

- Prompts, retrieved content, model output, tool output, connector responses,
  child reports, messages, memory, and supplemental harness state carry no
  authority.
- Context and results remain minimal, typed, provenance-carrying, size-bounded,
  tenant-scoped, and validated by the coordinator before shared commit.
- Inter-agent messages bind tenant, workflow family, task, attempt, sender,
  recipient, freshness, size, rate, and authority non-expansion.
- Tool and connector targets obey capability, effect, scheme, address, redirect,
  DNS, timeout, response, and egress policy.

## Evidence, Belief, Memory, And Harness

- Evidence retains source, time, tenant, quality, independence, and
  transformation provenance.
- Belief updates use versioned priors and reject stale, contradictory, poisoned,
  or mis-scoped evidence.
- Session context is distinct from durable governed memory.
- Only the coordinator commits shared belief, memory, or harness state.
- Base harness state remains immutable; supplemental candidates are local by
  default and require evaluation, independent approval, versioning, provenance,
  promotion scope, regression detection, and rollback before reuse.

## Tenancy, Secrets, And Isolation

- Tenant identity follows every storage key, cache, queue, message, context,
  result, receipt, belief, memory, log, metric, trace, and projection.
- Secrets use opaque scoped handles and never enter prompts, results,
  transcripts, errors, logs, traces, metrics labels, or unrestricted requests.
- Tenant and dependency resources are isolated by quotas, pools, bulkheads,
  timeouts, backpressure, and retention controls.

## Audit And Operator Truth

- Durable commands, events, approvals, effects, receipts, and recovery evidence
  are attributable, tamper-evident, ordered, and reconcilable.
- Projections expose revision, cursor, approval, lease, receipt, budget,
  recovery, ambiguity, and lag where operator action depends on them.
- Optimistic or late UI updates cannot hide failure, show false completion, or
  overwrite newer explicit operator intent.

## Compatibility And Evolution

- New writers and old readers, old writers and new readers, and rollback readers
  preserve required semantics or fail deterministically without retry storms.
- Migrations, defaults, lazy backfills, feature flags, and deployment ordering
  do not revive canceled work, duplicate effects, broaden authority, or erase
  traceability.
- Schema and catalog versions pin exact membership where additions or deletions
  require an explicit migration decision.

## High-Risk Interaction Clusters

Apply stronger than pairwise coverage to:

- tenant substitution + stale projection + administrative continuation;
- approval revocation + stale worker + effect commit;
- lease expiry + reassignment + late result + duplicate callback;
- concurrent child admission + parent budget reservation + retry;
- external effect + process loss + missing receipt + reconciliation;
- cancellation + dependency timeout + compensation + restart;
- prompt injection + tool output + memory or harness promotion;
- secret-bearing content + provider error + telemetry and transcript capture;
- new schema writer + old consumer + rollback;
- projection lag + operator command + ambiguous terminal state.
