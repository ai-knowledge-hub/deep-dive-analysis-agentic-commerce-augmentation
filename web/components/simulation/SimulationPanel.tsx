"use client";

import React, { useEffect, useState } from "react";
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
  productCopy?: string;
  onProductCopyChange?: (value: string) => void;
  optimizationMode?: "copy" | "feed" | "both";
  onOptimizationModeChange?: (mode: "copy" | "feed" | "both") => void;
  feedPreview?: {
    acp?: string;
    ucp?: string;
  } | null;
  evidenceSummary?: {
    intentSignal: string | null;
    total: number;
    rank: number | null;
    alignment: number | null;
    discovered: boolean;
    focusHint: string | null;
  } | null;
  sourceSessionId?: string | null;
  brandToneSummary?: string | null;
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
  productCopy,
  onProductCopyChange,
  optimizationMode = "both",
  onOptimizationModeChange,
  feedPreview,
  evidenceSummary,
  sourceSessionId,
  brandToneSummary,
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
  const [bestMatchPending, setBestMatchPending] = useState(false);
  const [scoresOpen, setScoresOpen] = useState(false);
  const [secondaryInsightsOpen, setSecondaryInsightsOpen] = useState(false);
  const scores = run?.result?.scores ?? [];
  const winnerId = run?.result?.winner_id;
  const selectedScore = selectedProductId
    ? scores.find((score) => score.product_id === selectedProductId) ?? null
    : null;
  const bestScore = scores.length
    ? [...scores].sort((a, b) => b.score - a.score)[0]
    : null;
  const bestProduct = bestScore
    ? products.find((product) => product.id === bestScore.product_id)
    : null;
  const primaryGap =
    run?.result?.gap_analysis?.find((gap) => gap.product_id === selectedProductId) ??
    run?.result?.gap_analysis?.[0] ??
    null;

  useEffect(() => {
    if (!loading) {
      setBestMatchPending(false);
    }
  }, [loading]);

  useEffect(() => {
    if (!bestMatchPending) return;
    if (!bestScore?.product_id) return;
    onSelectProduct(bestScore.product_id);
    setBestMatchPending(false);
  }, [bestMatchPending, bestScore?.product_id, onSelectProduct]);
  const protocolEntries = (run?.result?.protocol_readiness ?? []).filter(
    (entry) => entry.product_id === selectedProductId
  );
  const protocolReadiness =
    protocolEntries.length > 0
      ? protocolEntries
      : run?.result?.protocol_readiness ?? [];

  const readinessByProtocol = ["ucp", "acp"]
    .map((protocol) => {
      const entry =
        protocolReadiness.find((item) => item.protocol === protocol) ?? null;
      const issues = entry?.issues ?? [];
      const scoreIssue = issues.find(
        (issue) => issue.field === `${protocol}_readiness_score`
      );
      const scoreMatch = scoreIssue?.message?.match(/(\d{1,3})\s*\/\s*100/);
      const score =
        scoreMatch && !Number.isNaN(Number(scoreMatch[1]))
          ? Number(scoreMatch[1])
          : null;
      return { protocol, issues, score, hasEntry: Boolean(entry) };
    })
    .filter((entry) => entry.hasEntry);

  const activeMissingSignals = primaryGap?.missing_signals ?? [];
  const feedSuggestions =
    activeMissingSignals.length > 0
      ? activeMissingSignals.slice(0, 6).map((signal) => ({
          signal,
          field: "feed.keywords",
        }))
      : [];

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>Simulation Sandbox</h3>
      </div>
      <div className="simulation__intro">
        <div className="simulation__intro-card">
          <span className="simulation__diff-label">Scenario</span>
          {sourceSessionId && (
            <p className="simulation__note">
              Scenario filled from connected evidence.
            </p>
          )}
          <textarea
            id="simulation-scenario"
            rows={2}
            value={scenarioValue ?? query ?? ""}
            onChange={(event) => onScenarioChange?.(event.target.value)}
            placeholder="Describe the buyer intent you want to simulate."
          />
        </div>
        <div className="simulation__intro-card">
          <span className="simulation__diff-label">Optimization target</span>
          <div className="simulation__mode-buttons">
            {(["copy", "feed", "both"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`simulation__mode-button ${
                  optimizationMode === mode ? "is-active" : ""
                }`}
                onClick={() => onOptimizationModeChange?.(mode)}
              >
                {mode === "copy"
                  ? "Copy only"
                  : mode === "feed"
                  ? "Feed only"
                  : "Both"}
              </button>
            ))}
          </div>
          <p className="simulation__intro-text">
            {optimizationMode === "copy"
              ? "Optimize the website/product copy for intent fit."
              : optimizationMode === "feed"
              ? "Optimize ACP/UCP feed fields and protocol readiness."
              : "Optimize both copy and feed in one pass."}
          </p>
        </div>
        <div className="simulation__intro-card">
          <span className="simulation__diff-label">Evidence summary</span>
          {evidenceSummary ? (
            <>
              <div className="simulation__intro-metric">
                <span>Intent signal</span>
                <strong>{evidenceSummary.intentSignal ?? "—"}</strong>
              </div>
              <div className="simulation__intro-metric">
                <span>Discovered</span>
                <strong>{evidenceSummary.discovered ? "Yes" : "No"}</strong>
              </div>
              <div className="simulation__intro-metric">
                <span>Rank</span>
                <strong>
                  {evidenceSummary.rank ? `#${evidenceSummary.rank}` : "—"}
                </strong>
              </div>
              <div className="simulation__intro-metric">
                <span>Alignment</span>
                <strong>
                  {typeof evidenceSummary.alignment === "number"
                    ? `${Math.round(evidenceSummary.alignment * 100)}%`
                    : "—"}
                </strong>
              </div>
              <p className="simulation__intro-text">
                {evidenceSummary.discovered
                  ? evidenceSummary.focusHint === "depth"
                    ? "We’re ranking but not at the top. Push depth on top intent signals."
                    : "We’re discovered. Consider breadth to cover adjacent intent."
                  : "Not discovered. Focus on core intent signals to enter the set."}
              </p>
            </>
          ) : (
            <p className="simulation__intro-text">
              No evidence snapshot yet. Run a chat query to ground the scenario.
            </p>
          )}
        </div>
      </div>

      <div className="simulation__run">
        <span className="simulation__step-title">Step 1 · Run simulation</span>
        <p className="simulation__intro-text">
          Generate alignment scores across all products for the current intent.
        </p>
        <button
          type="button"
          className="button button--primary-subtle"
          onClick={onRun}
          disabled={!canRun || loading}
        >
          {loading ? (
            <>
              Running simulation<span className="button__dots" />
            </>
          ) : (
            "Run simulation"
          )}
        </button>
      </div>

      <div className="simulation__recommendation">
        <span className="simulation__step-title">Step 2 · Select target product</span>
        {bestProduct && bestScore ? (
          <div className="simulation__recommendation-body">
            <strong>{bestProduct.name}</strong>
            <span>{(bestScore.score * 100).toFixed(0)}% alignment</span>
          </div>
        ) : (
          <p className="simulation__intro-text">
            Run a simulation first to identify the closest product.
          </p>
        )}
        <div className="simulation__recommendation-actions">
          <button
            type="button"
            className="button button--primary-subtle"
            onClick={() => {
              if (bestScore?.product_id) {
                onSelectProduct(bestScore.product_id);
              } else {
                setBestMatchPending(true);
                onRun();
              }
            }}
            disabled={!canRun || loading}
          >
            {loading && bestMatchPending ? (
              <>
                Finding match<span className="button__dots" />
              </>
            ) : (
              scores.length === 0
                ? "Run + find best matching product"
                : "Find best matching product"
            )}
          </button>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => setScoresOpen(true)}
            disabled={scores.length === 0}
          >
            See all product scores
          </button>
        </div>
        {scores.length === 0 ? (
          <p className="simulation__intro-text">
            No scores yet. This action will run simulation first, then select the top match.
          </p>
        ) : null}
        {products.length > 0 && (
          <div className="simulation__picker">
            <span className="simulation__diff-label">
              Product to optimize
            </span>
            <p className="simulation__intro-text">
              Defaults to the product selected in the client panel.
            </p>
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
        {activeMissingSignals.length > 0 && (
          <div className="simulation__run-missing">
            <span className="simulation__diff-label">Top missing signals</span>
            <div className="simulation__signal-chips">
              {activeMissingSignals.slice(0, 3).map((signal) => (
                <span key={signal} className="simulation__signal-chip">
                  {signal}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {(optimizationMode === "copy" || optimizationMode === "both") && (
        <div className="simulation__copy">
          <span className="simulation__step-title">Step 3 · Optimize web copy</span>
          {brandToneSummary && (
            <p className="simulation__tone-suggestion">
              Current brand tone: {brandToneSummary}
            </p>
          )}
          <textarea
            rows={4}
            value={productCopy ?? ""}
            onChange={(event) => onProductCopyChange?.(event.target.value)}
            placeholder="Edit the web description used for optimization."
            disabled={false}
          />
          <p className="simulation__intro-text">
            Updates here are applied to the simulation only (no permanent save).
          </p>
        </div>
      )}

      {(optimizationMode === "feed" || optimizationMode === "both") && (
        <div className="simulation__feeds">
          <span className="simulation__step-title">Step 3 · Optimize feeds</span>
          <div className="simulation__feed-grid">
            <div className="simulation__feed-card">
              <div className="simulation__feed-title">ACP feed</div>
              <pre className="simulation__feed-code">
                {feedPreview?.acp ?? "No ACP feed snapshot yet."}
              </pre>
            </div>
            <div className="simulation__feed-card">
              <div className="simulation__feed-title">UCP feed</div>
              <pre className="simulation__feed-code">
                {feedPreview?.ucp ?? "No UCP feed snapshot yet."}
              </pre>
            </div>
          </div>
          <p className="simulation__intro-text">
            These are demo snapshots for the POC. In production they map to live
            ACP/UCP payloads.
          </p>
        </div>
      )}

      {scoresOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal simulation__scores-modal">
            <div className="simulation__scores-header">
              <div>
                <h4>All product scores</h4>
                <p className="simulation__scores-meta">
                  Ranked by alignment for this intent.
                </p>
              </div>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setScoresOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="simulation__scores-list">
              {scores.length === 0 ? (
                <p className="panel__empty">Run a simulation to see who wins.</p>
              ) : (
                scores
                  .slice()
                  .sort((a, b) => b.score - a.score)
                  .map((score) => (
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
                  ))
              )}
            </div>
          </div>
        </div>
      )}

      <details
        className="panel__details simulation__details"
        open={secondaryInsightsOpen}
        onToggle={(event) => setSecondaryInsightsOpen(event.currentTarget.open)}
      >
        <summary className="panel__details-summary">
          Secondary insights (gap/protocol/feed/lessons)
        </summary>
        {renderGap(primaryGap)}

        {primaryGap?.competitor_summary && (
          <div className="simulation__comparison">
            <span className="simulation__diff-label">Why you lost</span>
            <p>{primaryGap.competitor_summary}</p>
          </div>
        )}

        {protocolReadiness.length > 0 && (
          <div className="simulation__comparison">
            <span className="simulation__diff-label">Protocol readiness</span>
            <p className="simulation__intro-text">
              Readiness checks ACP/UCP compliance, not intent fit.{" "}
              <strong>Intent fit:</strong>{" "}
              {selectedScore
                ? `${Math.round(selectedScore.score * 100)}% alignment`
                : bestScore
                  ? `${Math.round(bestScore.score * 100)}% (best match)`
                  : "—"}
            </p>
            {readinessByProtocol.map((entry) => (
              <div key={entry.protocol} className="simulation__protocol-block">
                <div className="simulation__protocol-title">
                  {entry.protocol.toUpperCase()}
                </div>
                {entry.score !== null && (
                  <div className="simulation__protocol-score">
                    Readiness score: {entry.score}/100
                  </div>
                )}
                <ul>
                  {entry.issues
                    .filter((issue) => issue.severity !== "info")
                    .slice(0, 4)
                    .map((issue, index) => (
                      <li key={`${entry.protocol}-${issue.field}-${index}`}>
                        <strong>{issue.severity.toUpperCase()}:</strong>{" "}
                        {issue.message}
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {optimizationMode !== "copy" && (
          <div className="simulation__comparison">
            <span className="simulation__diff-label">Feed patch suggestions</span>
            {feedSuggestions.length === 0 ? (
              <p>No feed updates suggested yet. Run a simulation to detect gaps.</p>
            ) : (
              <ul>
                {feedSuggestions.map((item) => (
                  <li key={item.signal}>
                    Include mention of <strong>{item.signal}</strong> →{" "}
                    {item.field}
                  </li>
                ))}
              </ul>
            )}
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
      </details>

      {optimizationMode === "feed" ? (
        <p className="panel__muted">
          Tone controls are hidden in feed-only mode.
        </p>
      ) : (
        <div className="simulation__tone">
          <span className="simulation__step-title">Step 4 · Tone and guardrails</span>
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
              title="Attach product data to pull tone from live brand copy."
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
      )}

      <div className="simulation__actions">
        <button
          type="button"
          className="button button--ghost"
          onClick={() => onOptimize(selectedProductId ?? undefined)}
          disabled={!canOptimize || loading}
        >
          {optimizationMode === "both"
            ? "Generate optimized copy + feed"
            : `Generate optimized ${optimizationMode === "feed" ? "feed" : "copy"}`}
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
