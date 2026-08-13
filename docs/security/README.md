# Security Analysis

Status: current  
Last updated: 2026-08-11

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

The gate pins the complete schema-v1 ID set; resolves local and STPA safety
references; rejects missing boundary, threat, control, detection, verification,
or gap coverage; and executes the exact pytest nodes claimed by implemented
security verifications.
