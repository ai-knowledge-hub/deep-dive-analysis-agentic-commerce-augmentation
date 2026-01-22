"use client";

import type {
  SimulationGapReport,
  SimulationOptimizeResponse,
  SimulationRunResponse,
  SimulationRetestResponse,
  SimulationProduct,
} from "../../lib/types";

type Props = {
  query?: string | null;
  run?: SimulationRunResponse | null;
  optimized?: SimulationOptimizeResponse | null;
  retest?: SimulationRetestResponse | null;
  products: SimulationProduct[];
  selectedProductId?: string | null;
  loading?: boolean;
  canRun: boolean;
  canOptimize: boolean;
  canRetest: boolean;
  onRun: () => void;
  onOptimize: (productId?: string) => void;
  onRetest: () => void;
  onSelectProduct: (productId: string) => void;
};

function renderGap(gap: SimulationGapReport | null) {
  if (!gap) return null;
  return (
    <div className="simulation__gap">
      <div className="simulation__gap-header">
        <span>{gap.summary}</span>
        <span className={`simulation__gap-tag simulation__gap-tag--${gap.severity}`}>
          {gap.severity}
        </span>
      </div>
      {(gap.missing_signals ?? []).length > 0 && (
        <div className="simulation__gap-meta">
          Missing: {(gap.missing_signals ?? []).slice(0, 3).join(", ")}
        </div>
      )}
    </div>
  );
}

export function SimulationPanel({
  query,
  run,
  optimized,
  retest,
  products,
  selectedProductId,
  loading,
  canRun,
  canOptimize,
  canRetest,
  onRun,
  onOptimize,
  onRetest,
  onSelectProduct,
}: Props) {
  const scores = run?.result?.scores ?? [];
  const winnerId = run?.result?.winner_id;
  const primaryGap = run?.result?.gap_analysis?.[0] ?? null;

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>Simulation Sandbox</h3>
        <div className="panel__meta">
          <button
            type="button"
            className="panel__action"
            onClick={onRun}
            disabled={!canRun || loading}
          >
            Run
          </button>
        </div>
      </div>
      <p className="panel__subtitle">
        {query ? `Scenario: ${query}` : "Provide a scenario to simulate."}
      </p>

      {scores.length === 0 ? (
        <p className="panel__empty">Run a simulation to see who wins.</p>
      ) : (
        <div className="simulation__scores">
          {scores.map((score) => (
            <div key={score.product_id} className="simulation__score">
              <div className="simulation__score-header">
                <span className="simulation__score-id">
                  {score.product_id}
                </span>
                <span className="simulation__score-value">
                  {(score.score * 100).toFixed(0)}%
                </span>
              </div>
              {score.product_id === winnerId && (
                <span className="simulation__winner">Winner</span>
              )}
              <p className="simulation__reasoning">
                {score.alignment_reasoning || "No reasoning yet."}
              </p>
            </div>
          ))}
        </div>
      )}

      {renderGap(primaryGap)}

      {products.length > 0 && (
        <div className="simulation__picker">
          <span className="simulation__diff-label">Optimize a product</span>
          <div className="simulation__picker-buttons">
            {products.map((product) => (
              <button
                key={product.id}
                type="button"
                className={`simulation__picker-button ${
                  selectedProductId === product.id ? "is-active" : ""
                }`}
                onClick={() => onSelectProduct(product.id)}
              >
                {product.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="simulation__actions">
        <button
          type="button"
          className="button button--ghost"
          onClick={() => onOptimize(selectedProductId ?? undefined)}
          disabled={!canOptimize || loading}
        >
          Optimize {selectedProductId ? "selected" : "weakest"}
        </button>
        <button
          type="button"
          className="button button--primary"
          onClick={onRetest}
          disabled={!canRetest || loading}
        >
          Retest
        </button>
      </div>

      {optimized && (
        <div className="simulation__diff">
          <span className="simulation__diff-label">Before</span>
          <p>{optimized.optimized.before}</p>
          <span className="simulation__diff-label">After</span>
          <p>{optimized.optimized.after}</p>
        </div>
      )}

      {retest && (
        <div className="simulation__retest">
          <span className="simulation__diff-label">Retest results</span>
          <p>
            Top score:{" "}
            {(retest.result.scores?.[0]?.score ?? 0) * 100}%
          </p>
        </div>
      )}
    </div>
  );
}
