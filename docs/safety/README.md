# Safety Analysis

Status: current
Last updated: 2026-10-04

The Phase 1 safety baseline has two synchronized artifacts:

- `stpa-workflow-control-analysis-v1.md` explains the system boundary, control
  structure, losses, hazards, process models, unsafe interactions, causal
  scenarios, and constraints.
- `safety-controls-v1.yaml` is the normative, JSON-compatible YAML traceability
  catalog used by CI.

Run:

```bash
make safety-traceability-check
```

The gate pins the complete required schema-v1 identifier set and rejects silent
coverage deletion, duplicate or unresolved identifiers, missing STPA
categories, unmapped hazards or unsafe control actions, and planned controls
without ownership. Implemented controls require exact pytest node identifiers,
and the gate executes those nodes before passing.

CTRL-03/VT-03 now certify exact approval for the current sequential runtime:
admission and the atomic pre-effect commit revalidate tenant, principal, action,
effect identity and versions, payload, evidence, authority, revision, registry,
harness, policy, expiry, revocation, and supersession. Single-use effect state
and receipt-linked fulfillment make revocation races, retries, and uncertain
outcomes explicit without claiming the broader task-attempt, compensation, or
parallel-workflow controls that remain planned.

Phase 2.1 keeps explanation outside the control path: run lifecycle status
cannot be used as completion evidence, stale snapshots are marked after a
second authority-fence read, and conversation state is excluded from workflow
replay. Phase 2.2 adds one closed control action, pause, as an immutable proposal
followed by a separate human confirmation. Exact scope, revision, snapshot,
event head, governing pins, preflight, expiry, idempotency, audit events, and
receipt are host-owned; the final run/event/receipt outcome is atomic. The
complete snapshot and preflight are reconstructed again after the final SQLite
write lock is acquired, preventing an action, approval, effect, validation, or
completion-projection change from crossing the confirmation boundary. The
receipt explicitly limits its acknowledgement to the control-plane pause.
Worker and external-operation propagation remains uncertified and SEC-17 stays
planned, avoiding a false claim that the broader stop hazard is closed.

Phase 2.3a adds paused-only conversational resume eligibility using a distinct
immutable v2 proposal and explicit confirmation. Under the same final write
lock, the host rechecks full control state and live preflight. Active execution,
started or uncertain effects, and unrelated stopping conditions block resume.
Only the recorded operator-pause marker may be cleared. The sequential mode
mapping preserves plan-only non-execution, approvals, budgets, policy, attempts,
and committed effects. The atomic receipt records eligibility and exact status;
worker continuation and external propagation remain uncertified.

Phase 2.3b adds terminal conversational cancellation of quiescent nonterminal
runs. Successful completion verification and full control-state revalidation
under the final write lock are required. Executing actions and started or
uncertain effects block admission. Existing stops and evidence remain intact;
status, audits, workflow projection, and receipt commit atomically. The receipt
certifies control-plane cancellation only. Worker interruption, propagation,
and compensation remain outside this slice; SEC-17 remains planned.


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
