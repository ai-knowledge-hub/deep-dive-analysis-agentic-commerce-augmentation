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
