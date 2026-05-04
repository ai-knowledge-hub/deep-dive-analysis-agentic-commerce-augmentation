import React from "react";
import type { AgentAction, AgentRun } from "../../lib/types";

type Props = {
  run: AgentRun | null;
  briefing: string;
  proposedCount: number;
  approvedCount: number;
  failedCount: number;
  policyCount: number;
  selectedAction: AgentAction | null;
};

export function OperatorChatSummary({
  run,
  briefing,
  proposedCount,
  approvedCount,
  failedCount,
  policyCount,
  selectedAction,
}: Props) {
  return (
    <>
      <div className="panel__header">
        <div className="panel__meta panel__meta--stack">
          <h3>Operator chat</h3>
          <div className="panel__subtitle">
            Chat-led guidance over the selected execution workspace.
          </div>
        </div>
        <span className="panel__badge panel__badge--secondary">
          {run ? "Context aware" : "Awaiting run"}
        </span>
      </div>

      <div className="panel__notice panel__notice--info">{briefing}</div>

      {run ? (
        <div className="agent-ops-summary">
          <span className="panel__badge panel__badge--secondary">
            Proposed: {proposedCount}
          </span>
          <span className="panel__badge panel__badge--secondary">
            Approved: {approvedCount}
          </span>
          <span className="panel__badge panel__badge--secondary">Failed: {failedCount}</span>
          <span className="panel__badge panel__badge--secondary">Policy: {policyCount}</span>
          {selectedAction ? (
            <span className="panel__badge panel__badge--warning">
              Selection: {selectedAction.capability_name}
            </span>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
