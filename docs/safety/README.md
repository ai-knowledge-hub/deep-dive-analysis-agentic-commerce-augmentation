# Safety Analysis

Status: current
Last updated: 2026-08-10

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
