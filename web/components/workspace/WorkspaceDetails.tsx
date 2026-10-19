import React from "react";
import type { CreationProposal, WorkspaceHistory } from "../../lib/workspace";
import { workspaceActionLabel } from "../../lib/workspaceDisplay";
function ProposedPlan({ proposal }: { proposal: CreationProposal | null }) {
  if (!proposal) return <section><h2>Scope and plan</h2><p>Describe an objective for an existing experiment. Review the selected product, experiment, nine steps and limits before creating a run.</p><p>Creation grants no action approval.</p></section>;
  const { scope, parameters, plan } = proposal.preflight;
  return <section><h2>Proposed plan</h2><p>{parameters.objective.goal}</p><p>{scope.product} · {scope.experiment}</p>
    <ol className="workspace-plan">{plan.map((step, index) => <li key={index}>{index + 1}. {workspaceActionLabel(step.capability_name)}</li>)}</ol>
    <p>Limits: {parameters.budgets.max_actions} actions, {parameters.budgets.max_variant_runs} candidate evaluation, ${parameters.budgets.max_cost_usd} recorded cost.</p>
    <p>{proposal.preflight.execution_posture}</p><p>Confirm creation in the conversation. Every action still requires its own approval.</p>
  </section>;
}
export function WorkspaceDetails({ history, proposal = null }: { history: WorkspaceHistory | null; proposal?: CreationProposal | null }) {
  if (!history?.run) return <ProposedPlan proposal={proposal} />;
  return <section><p className="workspace-eyebrow">Recorded plan</p><h2>Supervised work</h2>
    <p>Run status: {history.run.status}. Status alone does not certify the objective is complete.</p>
    {history.confirmed_proposal && <p>{history.confirmed_proposal.preflight.scope.product} · {history.confirmed_proposal.preflight.scope.experiment}</p>}
    <ol className="workspace-plan">{history.actions.map((action) => <li key={action.id}><strong>{action.sequence}. {workspaceActionLabel(action.capability_name)}</strong><small>{action.status}</small><details><summary>Action record</summary><code>{action.id}</code></details></li>)}</ol>
    {history.actions_has_more && <p>The action list is partial. Inspect Runs for older actions.</p>}
    {history.receipt && <details><summary>Creation receipt</summary><code className="workspace-digest">{history.receipt.receipt_digest}</code></details>}
    <nav className="workspace-record-links"><a href={`/runs?run_id=${encodeURIComponent(history.run.id)}`}>Inspect run</a><a href={`/interventions?run_id=${encodeURIComponent(history.run.id)}`}>Review interventions</a></nav>
  </section>;
}
