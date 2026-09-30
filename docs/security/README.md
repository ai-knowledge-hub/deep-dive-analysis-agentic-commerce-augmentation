# Security Analysis

Status: current
Last updated: 2026-09-27

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
its dedicated signing secret never reaches the browser and cannot mint agent or
write authority. Direct API clients require a signed human bearer token. Body
tenant/user selectors must match verified claims; membership and the fixed
read scope are then checked. Sessions are bound
to one authorized run and cannot be carried across run or tenant boundaries.
Retrieved execution content and user questions are treated as untrusted data:
the model may return only a closed intent and existing server-created fact IDs,
while raw generated prose is never exposed as fact or authority. Mandatory
intent facts, typed provenance, evidence completeness states—including missing,
unavailable, and contradictory linked validation jobs—and resolved source links
are server-owned. Client-supplied lifecycle, revision, cursor, and completion
claims are rejected. The gateway contains no execution-command dependency.
Governed validation completion records its verified job link atomically with
the effect receipt. Compatibility reads of the older output-only shape require
the exact tenant, action, approval, effect-execution, idempotency, and receipt
provenance; an output value alone cannot introduce operator evidence.
Recovery actions carry a prior validation job only as non-authoritative source
context. They begin with no result link, preventing a stale source job from
blocking or being mistaken for the retry's separately authorized effect.
