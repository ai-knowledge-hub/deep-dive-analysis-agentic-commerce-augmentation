import type { AgentRunEvent } from "../../lib/types";
import type { OperatorCommandRecord } from "../../lib/operatorConversationTypes";

export function policyEscalationSignal(events: AgentRunEvent[], records: OperatorCommandRecord[]): AgentRunEvent | null {
  const reconciled = records.flatMap(({ receipt }) =>
    receipt?.command_type === "reconcile_effect" && receipt.outcome === "succeeded" ? [receipt] : [],
  );
  return [...events].reverse().find((event) => {
    if (!event.is_policy_event) return false;
    const type = String(event.event_type ?? "");
    // Governance audits are evidence, not themselves unresolved policy denials.
    if ((type === "approval_effect_started" && event.status === "started") ||
        (type === "approval_effect_succeeded" && event.status === "succeeded") ||
        (type === "approval_fulfilled" && event.status === "fulfilled") ||
        (type === "action_executed" && event.status === "executed") ||
        (type === "operator_command_approve" && ["received", "approved", "completed"].includes(String(event.status)))) return false;
    if (type === "approval_effect_uncertain" && reconciled.some((receipt) => {
      if (receipt.run_id !== event.run_id || receipt.action_id !== event.action_id) return false;
      const execution = event.anchors?.effect_execution_id;
      if (execution) return execution === receipt.effect_execution_id;
      // Older uncertainty audits bind the original approval/effect key instead.
      const proof = receipt.reconciliation;
      return Boolean(proof?.approval_id && proof.effect_idempotency_key &&
        event.anchors?.approval_id === proof.approval_id &&
        event.anchors?.effect_idempotency_key === proof.effect_idempotency_key);
    })) return false;
    return true;
  }) ?? null;
}
