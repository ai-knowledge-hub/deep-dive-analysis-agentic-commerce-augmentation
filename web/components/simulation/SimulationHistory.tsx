"use client";

import type { SimulationRunSummary } from "../../lib/types";

type Props = {
  runs: SimulationRunSummary[];
  activeRunId?: string | null;
  onSelect: (runId: string) => void;
};

export function SimulationHistory({ runs, activeRunId, onSelect }: Props) {
  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>Simulation History</h3>
        <div className="panel__meta">
          {runs.length > 0 && <span className="panel__badge">{runs.length}</span>}
        </div>
      </div>
      {runs.length === 0 ? (
        <p className="panel__empty">No simulations yet.</p>
      ) : (
        <div className="simulation__history">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              className={`simulation__history-item ${
                activeRunId === run.id ? "is-active" : ""
              }`}
              onClick={() => onSelect(run.id)}
            >
              <div className="simulation__history-row">
                <span className="simulation__history-query">{run.query}</span>
                {run.winner_id && (
                  <span className="simulation__history-winner">
                    Winner: {run.winner_id}
                  </span>
                )}
              </div>
              {run.created_at && (
                <span className="simulation__history-meta">
                  {new Date(run.created_at).toLocaleDateString()}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
