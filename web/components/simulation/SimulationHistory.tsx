"use client";

import React from "react";
import type { SimulationRunSummary } from "../../lib/types";

type Props = {
  runs: SimulationRunSummary[];
  activeRunId?: string | null;
  productLabels?: Record<string, string>;
  onSelect: (runId: string) => void;
  onAttach?: (runId: string) => void;
  attachLabel?: string | null;
  attachDisabled?: boolean;
  onOpenExperiments?: (runId: string, productId?: string | null) => void;
};

function formatHistoryProductLabel(
  productId: string | null | undefined,
  productLabels: Record<string, string>,
): string | null {
  if (!productId) return null;
  return productLabels[productId] ?? "Product not in current list";
}

export function SimulationHistory({
  runs,
  activeRunId,
  productLabels = {},
  onSelect,
  onAttach,
  attachLabel,
  attachDisabled,
  onOpenExperiments,
}: Props) {
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
          {runs.map((run) => {
            const winnerLabel = formatHistoryProductLabel(run.winner_id, productLabels);
            const linkedProductLabel = formatHistoryProductLabel(run.product_id, productLabels);
            return (
              <div
                key={run.id}
                className={`simulation__history-item ${
                  activeRunId === run.id ? "is-active" : ""
                }`}
              >
                <button
                  type="button"
                  className="simulation__history-main"
                  onClick={() => onSelect(run.id)}
                >
                  <div className="simulation__history-row">
                    <span className="simulation__history-query">{run.query}</span>
                    {winnerLabel && (
                      <span className="simulation__history-winner">
                        Winner: {winnerLabel}
                      </span>
                    )}
                  </div>
                  {typeof run.protocol_readiness_score === "number" && (
                    <span className="simulation__history-badge">
                      Protocol: {run.protocol_readiness_score}/100
                    </span>
                  )}
                  {run.created_at && (
                    <span className="simulation__history-meta">
                      {new Date(run.created_at).toLocaleDateString()}
                    </span>
                  )}
                  {typeof run.protocol_readiness_score === "number" && (
                    <span className="simulation__history-meta">
                      Protocol readiness: {run.protocol_readiness_score}/100
                    </span>
                  )}
                  {linkedProductLabel && (
                    <span className="simulation__history-meta">
                      Linked product: {linkedProductLabel}
                    </span>
                  )}
                </button>
                {onAttach && attachLabel && (
                  <div className="simulation__history-actions">
                    <button
                      type="button"
                      className="button button--ghost button--compact"
                      onClick={() => onAttach(run.id)}
                      disabled={attachDisabled}
                      title={
                        attachDisabled
                          ? "Select a product to attach this run."
                          : `Attach to ${attachLabel}`
                      }
                    >
                      Attach
                    </button>
                    {onOpenExperiments && (
                      <button
                        type="button"
                        className="button button--ghost button--compact"
                        onClick={() => onOpenExperiments(run.id, run.product_id)}
                      >
                        Experiments
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
