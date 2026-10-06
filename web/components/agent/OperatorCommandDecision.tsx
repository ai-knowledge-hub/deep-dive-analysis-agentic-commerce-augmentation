import React from "react";
import type { OperatorCommandProposal, OperatorCommandReceipt } from "../../lib/operatorConversationTypes";

export const commandLabels = { pause: "Pause", resume: "Resume", cancel: "Cancel", approve: "Approve action", reject: "Reject action", retry: "Retry action" };
const receiptLabels = { pause: "Pause", resume: "Resume eligibility", cancel: "Cancellation", approve: "Action approval", reject: "Action rejection", retry: "Retry action proposed" };

type Props = {
  proposal: OperatorCommandProposal | null;
  receipt: OperatorCommandReceipt | null;
  runId: string;
  confirming: boolean;
  onConfirm: (proposal: OperatorCommandProposal) => void;
  onDismiss: (id: string) => void;
};

export function OperatorCommandDecision({ proposal, receipt, runId, confirming, onConfirm, onDismiss }: Props) {
  const retry = proposal?.parameters.retry_plan;
  const review = proposal?.parameters.review;
  return <>
    {proposal && receipt?.proposal_id !== proposal.proposal_id ? (
      <section className="operator-chat__proposal" aria-label={`${commandLabels[proposal.command_type]} proposal`}>
        <h4>{commandLabels[proposal.command_type]} proposal</h4>
        {retry ? <>
          <p>Failed source action {proposal.parameters.action_id}: {retry.capability_name.replaceAll("_", " ")}</p>
          <p>Strategy: same action. Review the inputs for the new action.</p>
          <pre>{JSON.stringify(retry.normalized_inputs, null, 2)}</pre>
          {retry.side_effects.map((effect) => <p key={effect}>{effect}</p>)}
          <ul>{retry.review_checklist.map((item) => <li key={item}>{item}</li>)}</ul>
          <small>Input digest {retry.inputs_hash}. Retry identity is allocated on confirmation.</small>
        </> : null}
        {review ? <>
          <p>Action {proposal.parameters.action_id}: {review.capability_name.replaceAll("_", " ")}</p>
          <p>Review the exact inputs and intended effects before confirming.</p>
          <pre>{JSON.stringify(review.normalized_inputs, null, 2)}</pre>
          {review.side_effects.map((effect) => <p key={effect}>{effect}</p>)}
          <ul>{review.review_checklist.map((item) => <li key={item}>{item}</li>)}</ul>
          <small>Input digest {review.inputs_hash} · Approval {review.approval_id ?? "new request on confirmation"}</small>
        </> : null}
        <ul>{proposal.consequences.map((item) => <li key={item}>{item}</li>)}</ul>
        <div className="panel__muted">Expires {proposal.expires_at} · revision {proposal.source.active_graph_revision} · proposal {proposal.proposal_digest.slice(0, 12)}</div>
        <div className="panel__actions">
          <button type="button" className="button button--primary button--sm" disabled={confirming} onClick={() => onConfirm(proposal)}>
            {confirming ? "Confirming…" : `Confirm ${proposal.command_type}`}
          </button>
          <button type="button" className="button button--ghost button--sm" disabled={confirming} onClick={() => onDismiss(proposal.proposal_id)}>Dismiss</button>
        </div>
      </section>
    ) : null}
    {receipt ? <div className="panel__notice panel__notice--info" aria-label={`${receipt.command_type === "resume" ? "Resume" : receiptLabels[receipt.command_type]} receipt`}>
      {receiptLabels[receipt.command_type]} acknowledged · receipt {receipt.receipt_id}. Recorded outcome: {receipt.action_id ? receipt.outcome : receipt.resulting_run_status}.
      {receipt.command_type === "retry" ? <>
        <p>Source action {receipt.source_action_id} → proposed action {receipt.action_id}</p>
        <p>Strategy: same action · retry {receipt.retry_count} · action sequence {receipt.action_sequence}</p>
        <small>Effect identity {receipt.effect_idempotency_key}</small>
        <p>Fresh approval is required. Request “Approve action {receipt.action_id}” and review the new approval proposal.</p>
        <p>Confirmation did not execute work or start or resume the run.</p>
      </> : receipt.action_id ? <>
        <p>Action {receipt.action_id} · approval {receipt.approval_id} · decision sequence {receipt.approval_sequence}</p>
        <small>Approval envelope {receipt.approval_envelope_digest}</small>
        <p>This decision did not execute the action or start or resume the run.</p>
      </> : " Runtime propagation is not independently certified. "}
      <a href={`/interventions?run_id=${runId}`}>Open Interventions</a>
    </div> : null}
  </>;
}
