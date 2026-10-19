import React from "react";
import type { CreationProposal, CreationReceipt } from "../../lib/workspace";
import { workspaceActionLabel } from "../../lib/workspaceDisplay";
export function RunCreationDecision({ proposal, receipt, busy, onConfirm }: {
  proposal: CreationProposal | null; receipt: CreationReceipt | null; busy: boolean; onConfirm: () => void;
}) {
  if (receipt) return <section className="panel" aria-label="Run creation receipt">
    <h2>Run created</h2>
    {proposal && <><p>{proposal.preflight.parameters.objective.goal}</p><p>{proposal.preflight.scope.product} · {proposal.preflight.scope.experiment}</p></>}
    <p>Your objective is ready for supervised work. Creating the run does not mean the objective is complete.</p>
    <details><summary>Recorded decision</summary><code className="workspace-digest">{receipt.receipt_digest}</code></details>
    <a href={`/runs?run_id=${encodeURIComponent(receipt.run_id)}`}>Inspect this run</a>
  </section>;
  if (!proposal) return null;
  const expired = new Date(proposal.expires_at).getTime() <= Date.now();
  const { scope, parameters, plan } = proposal.preflight;
  return <section className="panel" aria-label="Run creation proposal">
    <h2>Review your objective</h2><p>{parameters.objective.goal}</p>
    <dl><dt>Product</dt><dd>{scope.product}</dd><dt>Experiment</dt><dd>{scope.experiment}</dd></dl>
    <a href={`/experiments?experiment_id=${encodeURIComponent(parameters.experiment_id)}`}>Inspect the selected experiment</a>
    <ol>{plan.map((step, i) => <li key={i}>{workspaceActionLabel(step.capability_name)}</li>)}</ol>
    <p>Limits: {parameters.budgets.max_actions} actions, {parameters.budgets.max_variant_runs} candidate evaluation, ${parameters.budgets.max_cost_usd} recorded cost.</p>
    <p>{proposal.preflight.execution_posture}</p>
    <p>Every action needs a separate approval. Review the committed plan after creation.</p>
    <button type="button" className="button button--primary" onClick={onConfirm} disabled={busy || expired}>{busy ? "Creating…" : "Confirm and create run"}</button>
    {expired && <p>This proposal expired. Send your objective again to refresh it.</p>}
  </section>;
}
