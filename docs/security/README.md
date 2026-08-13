# Security Analysis

Status: current
Last updated: 2026-08-13

The Phase 1 agent-workflow security baseline has two synchronized artifacts:

- `agent-workflow-threat-model-v1.md` explains the boundary, assets,
  adversaries, trust boundaries, threat scenarios, controls, security
  invariants, beta decisions, and response expectations.
- `security-controls-v1.yaml` is the normative, JSON-compatible YAML catalog of
  assets, boundaries, threats, controls, detections, verification tests, and
  owned implementation gaps.

Run:

```bash
make security-traceability-check
```

The gate pins the exact schema-v1 ID set; resolves local and STPA safety
references; rejects missing asset, boundary, control, detection, verification,
or open-gap coverage; enforces structured beta capability exclusions for
exposed critical threats; pins minimum closure evidence and approval authority;
cross-checks concrete blocked capability, tool, and effect identifiers against
the exhaustive executable registry policy; and executes the exact pytest nodes
claimed by implemented verifications. Runtime admission and pre-effect policy
both enforce unresolved executable release gates.
