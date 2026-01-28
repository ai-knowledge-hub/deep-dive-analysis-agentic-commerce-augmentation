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
  scenarioValue?: string;
  onScenarioChange?: (value: string) => void;
  toneSuggestion?: string | null;
  toneValue?: string;
  toneNotice?: string | null;
  onToneChange?: (value: string) => void;
  onToneUseSuggestion?: () => void;
  onToneSave?: () => void;
  onToneClear?: () => void;
  onToneFromBrand?: () => void;
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
  scenarioValue,
  onScenarioChange,
  toneSuggestion,
  toneValue,
  toneNotice,
  onToneChange,
  onToneUseSuggestion,
  onToneSave,
  onToneClear,
  onToneFromBrand,
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
  const primaryGap =
    run?.result?.gap_analysis?.find((gap) => gap.product_id === selectedProductId) ??
    run?.result?.gap_analysis?.[0] ??
    null;
  const protocolReadiness =
    run?.result?.protocol_readiness?.find(
      (entry) => entry.product_id === selectedProductId
    ) ??
    run?.result?.protocol_readiness?.[0] ??
    null;
  const protocolIssues = protocolReadiness?.issues ?? [];
  const protocolScore = (() => {
    const scoreIssue = protocolIssues.find(
      (issue) => issue.field === "ucp_readiness_score"
    );
    if (!scoreIssue?.message) return null;
    const match = scoreIssue.message.match(/(\\d{1,3})\\s*\\/\\s*100/);
    if (!match) return null;
    const value = Number(match[1]);
    if (Number.isNaN(value)) return null;
    return value;
  })();

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
      <div className="simulation__scenario">
        <label className="simulation__scenario-label" htmlFor="simulation-scenario">
          Scenario
        </label>
        <textarea
          id="simulation-scenario"
          rows={2}
          value={scenarioValue ?? query ?? ""}
          onChange={(event) => onScenarioChange?.(event.target.value)}
          placeholder="Describe the buyer intent you want to simulate."
        />
      </div>

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

      {primaryGap?.competitor_summary && (
        <div className="simulation__comparison">
          <span className="simulation__diff-label">Why you lost</span>
          <p>{primaryGap.competitor_summary}</p>
        </div>
      )}

      {protocolIssues.length > 0 && (
        <div className="simulation__comparison">
          <span className="simulation__diff-label">Protocol readiness</span>
          {protocolScore !== null && (
            <div className="simulation__protocol-score">
              Readiness score: {protocolScore}/100
            </div>
          )}
          <ul>
            {protocolIssues
              .filter((issue) => issue.severity !== "info")
              .slice(0, 4)
              .map((issue, index) => (
                <li key={`${issue.field}-${index}`}>
                <strong>{issue.severity.toUpperCase()}:</strong> {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(run?.result?.lessons ?? []).length > 0 && (
        <div className="simulation__lessons">
          <span className="simulation__diff-label">Lessons learned</span>
          <ul>
            {run?.result?.lessons?.map((lesson) => (
              <li key={lesson}>{lesson}</li>
            ))}
          </ul>
        </div>
      )}

      {run?.result?.gap_analysis?.length ? (
        <div className="simulation__gap-list">
          <span className="simulation__diff-label">Gap analysis</span>
          {run.result.gap_analysis.slice(0, 3).map((gap) => (
            <div key={`${gap.product_id}-${gap.goal}`} className="simulation__gap-row">
              <span className="simulation__gap-goal">{gap.goal}</span>
              <span className={`simulation__gap-tag simulation__gap-tag--${gap.severity}`}>
                {gap.severity}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="simulation__tone">
        <span className="simulation__diff-label">Tone</span>
        {toneNotice && <div className="simulation__notice">{toneNotice}</div>}
        <p className="simulation__tone-suggestion">
          {toneSuggestion || "No tone suggestion yet."}
        </p>
        <textarea
          rows={2}
          value={toneValue ?? ""}
          onChange={(event) => onToneChange?.(event.target.value)}
          placeholder="Confirm or edit the brand tone."
        />
        <div className="simulation__tone-actions">
          <button
            type="button"
            className="button button--ghost"
            onClick={onToneUseSuggestion}
            disabled={!toneSuggestion}
          >
            Use suggestion
          </button>
          <button
            type="button"
            className="button button--ghost"
            title="Connect a brand catalog to pull tone from live product copy."
            onClick={onToneFromBrand}
          >
            Use tone from brand site
          </button>
          <button
            type="button"
            className="button button--primary"
            onClick={onToneSave}
            disabled={!toneValue}
          >
            Save tone
          </button>
          <button
            type="button"
            className="button button--ghost"
            onClick={onToneClear}
            disabled={!toneValue}
          >
            Clear
          </button>
        </div>
      </div>

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
          <span className="simulation__diff-label">Before vs after</span>
          <div className="simulation__diff-grid">
            <div>
              <span className="simulation__diff-sub">Before</span>
              <p>{optimized.optimized.before}</p>
            </div>
            <div>
              <span className="simulation__diff-sub">After</span>
              <p>{optimized.optimized.after}</p>
            </div>
          </div>
        </div>
      )}

      {(retest || optimized) && (
        <div className="simulation__lift">
          <span className="simulation__diff-label">Lift summary</span>
          <div className="simulation__lift-row">
            <span>Winner before</span>
            <span>{winnerId ?? "—"}</span>
          </div>
          <div className="simulation__lift-row">
            <span>Winner after</span>
            <span>{retest?.result?.winner_id ?? "—"}</span>
          </div>
          <div className="simulation__lift-row">
            <span>Optimized lift</span>
            <span>
              {(() => {
                const targetId = optimized?.optimized.id;
                const beforeScore =
                  run?.result?.scores?.find((score) => score.product_id === targetId)?.score ??
                  null;
                const afterScore =
                  retest?.result?.scores?.find((score) => score.product_id === targetId)?.score ??
                  null;
                if (beforeScore === null || afterScore === null) return "—";
                const delta = (afterScore - beforeScore) * 100;
                return `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pts`;
              })()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
