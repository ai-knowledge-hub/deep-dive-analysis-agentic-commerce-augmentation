"use client";

import React from "react";
import type { AgentRun } from "../../lib/types";
import { formatOperatorIdentifier } from "../../lib/operatorDisplayLanguage";

type Props = {
  latestAgentRun: AgentRun | null;
  hasSelectedExperiment: boolean;
  onOpenRuns: () => void;
};

export function AgentOperatorModePanel({
  latestAgentRun,
  hasSelectedExperiment,
  onOpenRuns,
}: Props) {
  const latestRunSummary = latestAgentRun
    ? `${latestAgentRun.status ?? "unknown"} · ${formatOperatorIdentifier(latestAgentRun.state)}`
    : "none yet";
  const runModeLabel = formatOperatorIdentifier(latestAgentRun?.run_mode ?? "plan_only");

  return (
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <h3>Agent operator mode</h3>
        <span className="panel__badge panel__badge--secondary">Experimental</span>
      </div>
      <p className="panel__subheading">Optional orchestrated path</p>
      <p className="panel__step-helper">
        Use governed automation to run approved capabilities on this experiment. The same protocol
        gates apply (saved evidence, baseline-first, approvals).
      </p>
      <div className="panel__meta-strip">
        <div>
          <strong>Latest agent run</strong>: {" "}
          {latestRunSummary}
        </div>
        <div>
          <strong>Run mode</strong>: {runModeLabel}
        </div>
      </div>
      <div className="panel__actions panel__actions--priority">
        <button
          type="button"
          className="panel__action panel__action--prominent"
          onClick={onOpenRuns}
          disabled={!hasSelectedExperiment}
        >
          Start in Runs
        </button>
        <button type="button" className="panel__action panel__action--ghost" onClick={onOpenRuns}>
          View Runs
        </button>
      </div>
    </section>
  );
}
