# Security Analysis

Status: current
Last updated: 2026-10-05

The Phase 1 agent-workflow security baseline has three synchronized artifacts:

- `agent-workflow-threat-model-v1.md` explains the boundary, assets,
  adversaries, trust boundaries, threat scenarios, controls, security
  invariants, beta decisions, and response expectations.
- `security-controls-v1.yaml` is the normative, JSON-compatible YAML catalog of
  assets, boundaries, threats, controls, detections, verification tests, and
  owned implementation gaps.
- `domain/security/contract_v1.py` is the immutable schema-v1 authority for all
  17 threat closure requirements and mandatory blocked runtime capability,
  tool, effect, gate, control, and verification tuples. The catalog and runtime
  policy are validated projections of this contract.

Run:

```bash
make security-traceability-check
```

The gate pins the exact schema-v1 ID set; resolves local and STPA safety
references; rejects missing asset, boundary, control, detection, verification,
or open-gap coverage; enforces structured beta capability exclusions for
exposed critical threats; pins minimum closure evidence for every threat and the
closure approval authority; cross-checks concrete blocked capability, tool,
effect, gate, control, and verification identifiers against the exhaustive
executable registry policy; and executes the exact pytest nodes claimed by
implemented verifications. Runtime admission and pre-effect policy consume the
domain contract directly. Releasing a schema-v1 block requires implemented
prerequisites and a new versioned contract rather than an in-place projection
edit.

SEC-06/SVT-06 are implemented for the current sequential runtime. Governed
effects require the canonical approval ID and envelope digest, exact binding
revalidation at admission, and a transactional single-use authorization commit
immediately before the capability call. The durable effect record distinguishes
started, uncertain, and succeeded outcomes and links the final receipt to
approval fulfillment and the compatibility action projection. SEC-16 remains
planned, so production publishing and write-capable dynamic delegation remain
blocked by the immutable beta release contract.

The Phase 2.1 operator gateway accepts normal browser traffic only through the
same-origin Clerk/mock-authenticated web BFF. The BFF replaces request identity
and creates a short-lived server assertion bound to tenant, user, and exact run;
its read-only signing secret never reaches the browser and cannot mint agent or
write authority. Phase 2.2 uses a different command-only secret and assertion
audience for one exact pause, resume, or cancel proposal; it binds the command type,
proposal ID and digest as
well as tenant, human, run, expiry, and nonce. Reusing the read assertion cannot
cross that boundary. Direct API clients require a signed human bearer token. Body
tenant/user selectors must match verified claims; membership and the fixed
read scope are then checked. Sessions are bound
to one authorized run and cannot be carried across run or tenant boundaries.
Retrieved execution content and user questions are treated as untrusted data:
the model may return only a closed intent and existing server-created fact IDs,
while raw generated prose is never exposed as fact or authority. Mandatory
intent facts, typed provenance, evidence completeness states—including missing,
unavailable, and contradictory linked validation jobs—and resolved source links
are server-owned. Client-supplied lifecycle, revision, cursor, and completion
claims are rejected. Explanation remains isolated from execution; only the
closed pause, resume, and cancel intents may create non-mutating proposals, and only explicit
confirmation reaches the existing command service. Stale or substituted
proposal scope fails closed, the full evidence digest is reconstructed under
the final write lock, and exact retries return one immutable receipt. A
tenant-and-run-scoped authenticated read projection verifies and exposes the
immutable proposal and receipt to both Runs and Interventions without trusting
browser conversation memory. Its run-bound opaque cursor is rejected outside
the originating tenant and run, and every bounded page reports total and
remaining evidence so authorization-safe pagination cannot masquerade as a
complete audit history.
Resume uses a distinct v2 contract restricted to paused runs and supported
existing modes. Membership and active-human checks, full private control-state
hashing, and live registry/preflight checks share the final commit lock. Resume
does not manufacture action approval or broaden capability, policy, budget, or
mode authority. Additive migration 057 preserves historical pause identities
and digests while mixed history remains tenant/run scoped.
Governed validation completion records its verified job link atomically with
the effect receipt. Compatibility reads of the older output-only shape require
the exact tenant, action, approval, effect-execution, idempotency, and receipt
provenance; an output value alone cannot introduce operator evidence.
Recovery actions carry a prior validation job only as non-authoritative source
context. They begin with no result link, preventing a stale source job from
blocking or being mistaken for the retry's separately authorized effect.

Phase 2.3b uses a distinct v3 cancel contract with the same authenticated exact
proposal boundary and final locked authority check. Cancellation grants no
capability or effect authority, retains prior approvals/evidence, and rejects
in-flight or unreconciled work. Migration 058 preserves v1/v2 evidence while
adding immutable v3 history. Terminal cancellation receipts do not close the
planned worker-interruption and late-worker controls.


Phase 2.4a adds exact conversational approve/reject review for one pending action.
Preparation cannot mutate authority. Explicit confirmation binds the action,
decision and durable proposal; read and lifecycle assertions do not suffice.
Live human access and full private state are revalidated under the final lock.
The approval ledger and conversational receipt commit together, including the
required audit/workflow projections. Existing requested approval bindings must
still match current action/evidence/authority. Confirmation executes nothing;
the existing worker pre-effect, revocation, policy, budget and single-use checks
remain authoritative. Terminal cancellation blocks new decisions, while exact
historical receipts remain replayable to currently authorized humans. This slice
does not upgrade planned distributed controls or change beta exclusions.


Phase 2.5a adds exact same-action retry proposals for one failed action on a
quiescent nonterminal sequential run. A separate schema-v3 retry assertion binds
human, tenant, run, source action, strategy, proposal and digest; read, lifecycle
and action-review assertions cannot confirm it. Under the final write lock the
host rechecks access, verified completion, full private state, registry, policy,
harness, linked evidence and budgets. Committed source-family effects and
unresolved run effects block admission. The new proposed action has a separate
under-lock sequence, retry ordinal and effect identity, no copied approval or
result link, and requires fresh approval. Child creation, human audits, workflow
projections and immutable v5 receipt commit together; commit failure rolls back
all pending writes. Exact replay checks current access before new eligibility.

The effect-start transaction also rechecks the complete related retry family
under its write lock. Started, uncertain and succeeded related effects block
preapproved siblings before any reservation or provider call. Immutable v5
receipt relationships survive rewritten action keys; legacy retry identities
remain fenced. Exact effect replay requests reconciliation, and independent
actions with identical inputs keep their separate approvals and effects.

A verified receipt holds only its source failure while the exact child is
proposed, approved or executing. Reconciliation checks the observed action set under the final
write lock before projecting status; unrelated failures and stopping conditions remain effective.
A finished or rejected child releases the hold. The failed source and required
completion membership are unchanged, so successful retry is not workflow
completion. Migration 061 preserves v1-v4 evidence and readers, with separate
v5 history views. All workers must receive the receipt hold and pre-effect family fence before
enabling the new UI. Existing beta
exclusions, distributed cancellation/attempt controls and broader recovery
remain unchanged; planned controls are not certified by this slice.

Supplementary retry evidence, admission boundaries, failure-space coverage and
rollout limits are recorded in
[the issue 164 verification report](../debug/2026-10-05-conversational-retry-verification.md).

Phase 2.5b reconciliation adds a schema-v4 assertion in the separate
`operator-reconciliation-api` audience, bound to exact human, tenant, run,
action, effect execution and proposal digest. Current membership and active
human checks precede replay and are repeated under the commit lock. Supplied
outputs and model-selected mutation intent grant no authority. The supplementary
[reconciliation verification](../debug/2026-10-06-conversational-reconciliation-verification.md)
covers substitution, evidence scope and replay/rollback; schema-v1 SVT
verification references remain unchanged.
