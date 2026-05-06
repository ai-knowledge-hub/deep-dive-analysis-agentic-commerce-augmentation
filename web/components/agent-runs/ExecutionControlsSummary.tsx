import React from "react";
import type { AgentRun } from "../../lib/types";

type FlowStep = {
  id: string;
  label: string;
  status: string;
  className: string;
};

type ExecutionControlsSummaryProps = {
  selectedRun: AgentRun;
  flowSteps: FlowStep[];
};

export function ExecutionControlsSummary({
  selectedRun,
  flowSteps,
}: ExecutionControlsSummaryProps) {
  return (
    <section className="agent-run-summary control-section">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Selected run</span>
          <h4 className="control-section__title">Execution controls</h4>
        </div>
        <span className="control-chip control-chip--accent">
          Current: {selectedRun.state ?? "unknown"}
        </span>
      </div>
      <div className="control-chip-row">
        <span className="control-chip">
          Status: {selectedRun.status ?? "unknown"}
        </span>
        <span className="control-chip">
          Approval: {selectedRun.requires_approval ? "required" : "auto-execute safe"}
        </span>
        <span className="control-chip">
          Mode: {selectedRun.run_mode || "plan_only"}
        </span>
      </div>
      <details className="agent-flow-details">
        <summary>View full execution flow</summary>
        <div className="flow-rail">
          <div className="flow-rail__steps">
            {flowSteps.map((step, index) => (
              <div key={step.id} className={`flow-rail__step ${step.className}`}>
                <span className="flow-rail__index">{index + 1}</span>
                <span className="flow-rail__label">{step.label}</span>
                <span className="flow-rail__status">{step.status}</span>
              </div>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
