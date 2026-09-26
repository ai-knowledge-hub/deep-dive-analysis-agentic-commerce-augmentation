# Architecture Decision Records

Status: current

Architecture decision records capture durable platform choices and the
constraints future implementations must preserve.

- `0001-workflow-task-delegation-schema.md`: framework-neutral logical schema
  for durable workflows, tasks, attempts, graph revisions, delegation,
  checkpoints, and results.
- `0002-evidence-result-completion-contracts.md`: accepted Slice 6a contract for
  exact evidence provenance and freshness, coordinator-validated task results,
  independently versioned completion criteria, authoritative completion
  decisions, and lag-aware operator projections.
- `0003-workflow-orchestration-pattern-adoption.md`: accepted evidence-led
  decision to keep portable workflow evidence authoritative, adopt graph-state
  as a rebuildable routing projection, adopt durable-history integrity and
  recovery-journal patterns, and preserve explicit migration and rollback
  boundaries.
