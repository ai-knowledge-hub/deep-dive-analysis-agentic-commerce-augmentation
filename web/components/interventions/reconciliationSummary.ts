import type { OperatorCommandRecord } from "../../lib/operatorConversationTypes";

export function reconciliationSummary(record: OperatorCommandRecord): string {
  const { proposal, receipt } = record;
  const proof = receipt?.reconciliation ?? proposal.parameters.reconciliation;
  const identity = `Action ${proposal.parameters.action_id}; effect ${proof?.effect_execution_id}; evidence ${proof?.evidence_id}; original approval ${proof?.approval_id}; frozen start ${proof?.authorization_snapshot_digest}; evidence digest ${proof?.evidence_digest}.`;
  return receipt
    ? `Existing effect outcome recorded: succeeded; action executed; recorded run status ${receipt.resulting_run_status}${receipt.control_state_preserved ? " (control state preserved)" : ""}. ${identity} No provider call or new effect start occurred. Effect success alone does not certify objective completion.`
    : `Verified existing effect outcome: succeeded; current action ${proposal.parameters.action_status}; after recording executed; current run ${proposal.source.run_status}. ${identity} Awaiting explicit reconciliation confirmation in Runs. No provider call, retry or new approval will occur.`;
}
