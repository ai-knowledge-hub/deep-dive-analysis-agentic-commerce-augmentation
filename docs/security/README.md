# Security Analysis

Status: current
Last updated: 2026-08-25

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
