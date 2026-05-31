import React from "react";
import type { AgentRun } from "../../lib/types";
import { formatOperatorIdentifier } from "../../lib/operatorDisplayLanguage";
import { runAttentionLabel } from "./runAttention";

type RunCounters = {
  total: number;
  running: number;
  planned: number;
  failed: number;
  completed: number;
  approvals: number;
};

type RunSelectionRailProps = {
  runs: AgentRun[];
  selectedRunId: string | null;
  runCounters: RunCounters;
  onSelectRun: (runId: string) => void;
};

function formatRunLabel(run: AgentRun): string {
  if (run.experiment_id) {
    return `Experiment ${String(run.experiment_id).slice(0, 8)}`;
  }
  return `Run ${String(run.id).slice(0, 8)}`;
}

export function RunSelectionRail({
  runs,
  selectedRunId,
  runCounters,
  onSelectRun,
}: RunSelectionRailProps) {
  return (
    <div className="control-surface control-surface--flat">
      <section className="control-section">
        <div className="control-section__header">
          <div>
            <span className="control-section__eyebrow">Runs</span>
            <h3 className="control-section__title">Run selection</h3>
            <div className="control-section__summary">
              Ordered by operator attention, not creation time.
            </div>
          </div>
          <span className="control-chip control-chip--accent">Attention first</span>
        </div>
        <div className="control-data-list">
          {runs.map((run) => {
            const active = run.id === selectedRunId;
            const attentionLabel = runAttentionLabel(run);
            return (
              <button
                key={run.id}
                type="button"
                className={`control-data-row ${active ? "is-active" : ""}`}
                onClick={() => onSelectRun(run.id)}
              >
                <div className="control-data-row__main">
                  <div className="control-data-row__title">{formatRunLabel(run)}</div>
                  <div className="control-data-row__meta">
                    {run.status ?? "unknown"} · {formatOperatorIdentifier(run.state)}
                  </div>
                </div>
                {attentionLabel ? (
                  <span
                    className={`control-chip ${
                      attentionLabel === "Critical" ? "control-chip--attention" : ""
                    }`}
                  >
                    {attentionLabel}
                  </span>
                ) : null}
              </button>
            );
          })}
          {runs.length === 0 && <div className="panel__muted">No agent runs yet.</div>}
        </div>
      </section>

      <section className="control-section">
        <div className="control-section__header">
          <div>
            <span className="control-section__eyebrow">Summary</span>
            <h4 className="control-section__title">Run stats</h4>
          </div>
        </div>
        <div className="control-stat-strip">
          <div className="control-stat">
            <span className="control-stat__value">{runCounters.total}</span>
            <span className="control-stat__label">Total</span>
          </div>
          <div className="control-stat">
            <span className="control-stat__value">{runCounters.running}</span>
            <span className="control-stat__label">Running</span>
          </div>
          <div className="control-stat">
            <span className="control-stat__value">{runCounters.approvals}</span>
            <span className="control-stat__label">Approvals</span>
          </div>
          <div className="control-stat">
            <span className="control-stat__value">{runCounters.planned}</span>
            <span className="control-stat__label">Planned</span>
          </div>
          <div className="control-stat">
            <span className="control-stat__value">{runCounters.completed}</span>
            <span className="control-stat__label">Completed</span>
          </div>
          <div className="control-stat">
            <span className="control-stat__value">{runCounters.failed}</span>
            <span className="control-stat__label">Failed</span>
          </div>
        </div>
      </section>
    </div>
  );
}
