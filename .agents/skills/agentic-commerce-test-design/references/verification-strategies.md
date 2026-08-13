# Verification Strategies

## Technique Selection

| Platform concern | Primary technique | Complement |
| --- | --- | --- |
| Lifecycle and commands | Stateful reference model | Illegal-transition and replay mutation |
| Authority and approval | Property-based non-expansion | Identity, revision, and payload substitution |
| Budgets and concurrency | Deterministic schedule exploration | Concurrent boundary tests |
| Validators and catalogs | Grammar-aware coordinated mutation | Independent pinned schema oracle |
| Persistence and effects | Pre/post commit fault injection | Receipt reconciliation tests |
| Workers and callbacks | Lease/fence schedule model | Duplicate and late-delivery tests |
| Tenant isolation | Cross-scope differential tests | Cache, queue, telemetry, and projection probes |
| Content boundaries | Injection and sensitive-data properties | Provenance and size mutations |
| Belief and memory | Model-based versioned updates | Contradiction and rollback properties |
| Harness evolution | Candidate/promotion state model | Cross-session and global-promotion mutation |
| Migrations | Old/new compatibility matrix | Rollback-reader golden records |
| Dependency resilience | Synthetic fault adapters | Bounded hypothesis-driven chaos |

Generated tests must preserve seeds and shrink failures. Promote minimized
high-consequence counterexamples to stable regression tests while retaining the
general generator.

## Independent Oracle Patterns

Prefer:

1. a canonical contract represented separately from submitted data;
2. a small lifecycle, authority, or budget reference model;
3. a metamorphic relation such as non-expansion, idempotence, monotonicity,
   conservation, reversibility, isolation, or deterministic replay;
4. a durable provider receipt reconciled against authoritative state;
5. a differential implementation maintained through an independent path.

Do not certify a broad control from a narrow test. Exact verification nodes must
exercise every behavior claimed by an implemented safety or security control.

## Mutation Portfolio

For each material graph or catalog relationship exercise:

- unilateral deletion;
- bilateral or all-sides deletion;
- same-type substitution;
- cross-tenant or cross-workflow substitution;
- duplication and reordering;
- unexpected well-formed addition;
- status change plus all dependent-field changes;
- coordinated weakening of source and derived sets;
- legacy representation and mixed-version mutation.

For runtime controls exercise bypass at route, planner, scheduler, worker,
adapter, callback, commit, recovery, and administrative paths.

## Fault And Chaos Protocol

Every fault experiment requires a falsifiable invariant, exact injection point,
bounded tenant/workflow/environment scope, steady-state signal, stop condition,
rollback, reconciliation path, preserved evidence, and reproducible schedule.
Begin with synthetic adapters and isolated environments. Production-facing or
destructive experiments require explicit authorization and proven containment.

## Coverage Reporting

Report explicit denominators for modeled invariants, lifecycle edges, dangerous
illegal edges, relationship mutation operators, authority substitutions,
pre/post fault points, selected interaction tuples, detected harmful mutations,
and safely reconciled recoverable failures. Line coverage is supporting data,
not evidence of these properties.
