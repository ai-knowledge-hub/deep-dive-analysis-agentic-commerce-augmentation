/**
 * Evidence Panel Component
 *
 * Main panel for displaying evidence analysis and explanation.
 */

"use client";

import React, { useState } from "react";
import type { EvidenceAnalyzeResponse, EvidenceSignalExtraction } from "../../lib/types";
import { EvidenceCard } from "./EvidenceCard";

type Props = {
  analysis?: EvidenceAnalyzeResponse | null;
  signalExtraction?: EvidenceSignalExtraction | null;
  targetProductId?: string;
  targetProductName?: string;
  targetProductCopy?: string;
  targetProductUrl?: string;
  onOpenSimulation?: () => void;
  usePageScroll?: boolean;
};

export function EvidencePanel({
  analysis,
  signalExtraction,
  targetProductId,
  targetProductName,
  targetProductCopy,
  targetProductUrl,
  onOpenSimulation,
  usePageScroll = false,
}: Props) {
  const [activeTab, setActiveTab] = useState<
    "evidence" | "explanation" | "actions"
  >("evidence");

  const hasData = Boolean(analysis);
  if (!hasData) {
    return (
      <div className="panel__card">
        <div className="panel__header">
          <h3>Evidence Discovery</h3>
        </div>
        <div className="empty-state">
          <div className="empty-state__icon">🔍</div>
          <h4 className="empty-state__title">No Evidence Data</h4>
          <p className="empty-state__description">
            Run a chat query to generate evidence-based product discovery results.
          </p>
        </div>

        <style jsx>{`
          .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 4rem 2rem;
            text-align: center;
          }

          .empty-state__icon {
            font-size: 4rem;
            margin-bottom: 1rem;
            opacity: 0.5;
          }

          .empty-state__title {
            margin: 0 0 0.75rem 0;
            font-size: 1.25rem;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
          }

          .empty-state__description {
            margin: 0 0 1.5rem 0;
            font-size: 0.9375rem;
            color: rgba(255, 255, 255, 0.6);
            max-width: 500px;
            line-height: 1.6;
          }

        `}</style>
      </div>
    );
  }

  const evidenceProducts = analysis?.evidence_products ?? [];
  const alignmentScores = analysis?.alignment_scores ?? [];
  const scoreMap = new Map(
    alignmentScores.map((score) => [score.product_id, score]),
  );
  const normalizedEvidenceProducts = evidenceProducts.map((product) => {
    const score = scoreMap.get(product.id);
    const metadata = {
      ...(product.metadata ?? {}),
      alignment_score:
        (product.metadata as Record<string, unknown>)?.alignment_score ??
        score?.score,
      alignment_reasoning:
        (product.metadata as Record<string, unknown>)?.alignment_reasoning ??
        score?.alignment_reasoning,
    };
    const name = product.name?.trim() ? product.name : product.description;
    const description =
      product.description?.trim() || product.raw_text || product.name;
    return {
      ...product,
      name,
      description,
      confidence:
        typeof product.confidence === "number" ? product.confidence : 0.5,
      metadata,
    };
  });
  const sortedScores = [...alignmentScores].sort(
    (a, b) => (b.score ?? 0) - (a.score ?? 0),
  );
  const averageScore =
    alignmentScores.length > 0
      ? alignmentScores.reduce((sum, item) => sum + (item.score ?? 0), 0) /
        alignmentScores.length
      : 0;

  const normalizedName = (targetProductName ?? "").toLowerCase().trim();
  const matchedProduct =
    normalizedEvidenceProducts.find((product) =>
      targetProductId ? product.id === targetProductId : false,
    ) ??
    normalizedEvidenceProducts.find((product) =>
      normalizedName
        ? product.name.toLowerCase().includes(normalizedName)
        : false,
    ) ??
    null;
  const matchedScore = matchedProduct
    ? scoreMap.get(matchedProduct.id)?.score ?? null
    : null;
  const rank =
    matchedProduct && sortedScores.length > 0
      ? sortedScores.findIndex((item) => item.product_id === matchedProduct.id) + 1
      : null;
  const topScore = sortedScores[0];
  const topLabel = topScore
    ? normalizedEvidenceProducts.find((item) => item.id === topScore.product_id)
        ?.name
    : null;

  const matchedCapabilities =
    (scoreMap.get(matchedProduct?.id ?? "")?.matched_capabilities ?? []).filter(
      Boolean,
    );
  const winnerCapabilities =
    (scoreMap.get(topScore?.product_id ?? "")?.matched_capabilities ?? []).filter(
      Boolean,
    );
  const goalSignals = analysis?.goals ?? [];
  const intentSignals =
    signalExtraction?.intent_signals?.length
      ? signalExtraction.intent_signals
      : goalSignals;
  const copyText = (targetProductCopy ?? "").toLowerCase();
  const detectSignal = (signal: string) => {
    const tokens = signal
      .toLowerCase()
      .split(/\s+/)
      .filter((token) => token.length > 3);
    if (!tokens.length) return false;
    return tokens.every((token) => copyText.includes(token));
  };
  const detectedSignals = intentSignals.filter((signal) => detectSignal(signal));
  const missingGoalSignals = intentSignals.filter(
    (signal) => !detectedSignals.includes(signal),
  );
  const winnerSignals =
    signalExtraction?.winner_signals?.length
      ? signalExtraction.winner_signals
      : winnerCapabilities;

  const missingSignals =
    signalExtraction?.missing_signals?.length
      ? signalExtraction.missing_signals
      : winnerCapabilities.filter((cap) => !matchedCapabilities.includes(cap));
  const extraSignals =
    signalExtraction?.winner_signals?.length
      ? detectedSignals.filter((signal) => !winnerSignals.includes(signal))
      : matchedCapabilities.filter((cap) => !winnerCapabilities.includes(cap));
  const scoreDeficit =
    matchedScore !== null && topScore?.score
      ? Math.max(topScore.score - matchedScore, 0)
      : topScore?.score ?? null;
  const counterfactualLift =
    scoreDeficit !== null
      ? Math.min(scoreDeficit * 0.6 + missingSignals.length * 0.05, 0.4)
      : null;

  const intentConfidence = analysis?.intent?.confidence ?? 0.6;
  const explicitnessScore = (signal: string) => {
    const hasNumber = /\d/.test(signal);
    const hasCurrency = /£|\$|€/.test(signal);
    const hasUnit = /(size|mm|cm|kg|lb|budget|price|under|within)/i.test(signal);
    const length = Math.min(signal.split(/\s+/).length / 6, 1);
    const numericBoost = hasNumber || hasCurrency ? 0.2 : 0;
    const unitBoost = hasUnit ? 0.15 : 0;
    return Math.min(1, 0.3 + length + numericBoost + unitBoost);
  };

  const intentSignalsWeighted = intentSignals.map((signal) => ({
    signal,
    weight: Math.min(1, intentConfidence * explicitnessScore(signal)),
  }));

  const evidenceSignalsWeighted = winnerSignals.map((signal) => {
    const frequency = alignmentScores.filter((score) =>
      (score.matched_capabilities ?? []).includes(signal),
    ).length;
    const freqScore = alignmentScores.length
      ? frequency / alignmentScores.length
      : 0;
    const alignmentWeight = topScore?.score ?? 0.3;
    return {
      signal,
      weight: Math.min(1, freqScore * (0.6 + alignmentWeight * 0.4)),
    };
  });

  const copyPresenceWeighted = [
    ...new Set([...intentSignals, ...winnerSignals]),
  ].map(
    (signal) => ({
      signal,
      present: detectSignal(signal),
    }),
  );

  const specificityScore = intentSignalsWeighted.reduce(
    (sum, item) => sum + item.weight,
    0,
  );
  const breadthScore = evidenceSignalsWeighted.reduce(
    (sum, item) => sum + item.weight,
    0,
  );
  const specificityRatio =
    specificityScore + breadthScore > 0
      ? specificityScore / (specificityScore + breadthScore)
      : 0.5;

  const coverageCount = evidenceProducts.length;
  const focusScore = matchedScore ?? averageScore;
  let tradeoffMessage =
    "Balance specificity and breadth by testing adjacent intents without losing core intent fit.";
  if (!matchedProduct) {
    tradeoffMessage =
      "Your product is not yet discovered. Prioritize specificity to enter the set, then broaden.";
  } else if (rank && rank <= 3) {
    tradeoffMessage =
      "You rank strongly for this intent. Consider broadening signals to cover nearby queries.";
  } else if (rank) {
    tradeoffMessage =
      "You appear but not at the top. Tighten intent-specific signals to climb rank.";
  }

  const histogramBuckets = [
    { label: "0-20%", min: 0, max: 0.2 },
    { label: "20-40%", min: 0.2, max: 0.4 },
    { label: "40-60%", min: 0.4, max: 0.6 },
    { label: "60-80%", min: 0.6, max: 0.8 },
    { label: "80-100%", min: 0.8, max: 1.0 },
  ];
  const histogram = histogramBuckets.map((bucket) => {
    const count = alignmentScores.filter(
      (score) =>
        (score.score ?? 0) >= bucket.min && (score.score ?? 0) < bucket.max,
    ).length;
    return { ...bucket, count };
  });
  const maxBucket = Math.max(1, ...histogram.map((b) => b.count));

  const winners = sortedScores.slice(0, 3).map((score) => {
    const product = normalizedEvidenceProducts.find(
      (item) => item.id === score.product_id,
    );
    return {
      id: score.product_id,
      name: product?.name ?? "Top result",
      score: score.score ?? 0,
      reasoning: score.alignment_reasoning ?? "Aligned with core intent signals.",
      matched: score.matched_capabilities ?? [],
    };
  });

  return (
    <>
      <div className="evidence-summary">
        <div className="summary-card">
          <div className="summary-card__title">Evidence Set</div>
          <div className="summary-card__value">
            {evidenceProducts.length} products
          </div>
          <div className="summary-card__meta">
            Sources:{" "}
            {Array.from(
              new Set(evidenceProducts.map((item) => item.source || "unknown")),
            )
              .slice(0, 3)
              .join(", ") || "—"}
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-card__title">Rank & Alignment</div>
          {matchedProduct ? (
            <>
              <div className="summary-card__value">
                #{rank ?? "—"}{" "}
                <span className="summary-card__subtle">
                  {matchedScore !== null
                    ? `• ${(matchedScore * 100).toFixed(0)}% align`
                    : ""}
                </span>
              </div>
              <div className="summary-card__meta">
                Top result: {topLabel ?? "—"}
              </div>
            </>
          ) : (
            <>
              <div className="summary-card__value">Not discovered</div>
              <div className="summary-card__meta">
                Run simulation to improve alignment signals.
              </div>
              {onOpenSimulation ? (
                <button
                  type="button"
                  className="button button--primary-subtle"
                  onClick={onOpenSimulation}
                >
                  Open Simulation
                </button>
              ) : null}
            </>
          )}
        </div>

        <div className="summary-card">
          <div className="summary-card__title">Specificity vs Breadth</div>
          <div className="summary-card__value">
            Focus {(focusScore * 100).toFixed(0)}%
          </div>
          <div className="summary-card__meta">
            Coverage: {coverageCount} discovered
          </div>
          <p className="summary-card__note">{tradeoffMessage}</p>
        </div>

        <div className="summary-card summary-card--analysis">
          <div className="summary-card__title">Winner vs Our Copy</div>
          {matchedProduct ? (
            <>
              <div className="summary-card__value">
                Score deficit{" "}
                {scoreDeficit !== null
                  ? `• ${(scoreDeficit * 100).toFixed(0)}%`
                  : "—"}
              </div>
              <div className="summary-card__meta">
                Missing signals:{" "}
                {missingSignals.length
                  ? missingSignals.slice(0, 3).join(", ")
                  : "None detected"}
              </div>
              {extraSignals.length > 0 && (
                <div className="summary-card__meta">
                  Unique to us: {extraSignals.slice(0, 2).join(", ")}
                </div>
              )}
              {counterfactualLift !== null && (
                <p className="summary-card__note">
                  Counterfactual lift estimate: +{Math.round(counterfactualLift * 100)}
                  % if we add the top missing signals.
                </p>
              )}
            </>
          ) : (
            <>
              <div className="summary-card__value">Not discovered</div>
              <div className="summary-card__meta">
                Missing signals:{" "}
                {missingGoalSignals.slice(0, 3).join(", ") ||
                  missingSignals.slice(0, 3).join(", ") ||
                  "—"}
              </div>
              {counterfactualLift !== null && (
                <p className="summary-card__note">
                  Counterfactual lift estimate: +{Math.round(counterfactualLift * 100)}
                  % if we add top signals.
                </p>
              )}
            </>
          )}
        </div>
      </div>

      <div
        className={`evidence-panel${usePageScroll ? " evidence-panel--page" : ""}`}
      >
        <div className="evidence-panel__header">
          <div className="header-title">
            <h3>Evidence Discovery</h3>
            <span className="header-badge">
              {evidenceProducts.length} products
            </span>
          </div>
          <div className="header-tabs">
            <button
              type="button"
              className={`tab ${activeTab === "evidence" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("evidence")}
            >
              Evidence
              {evidenceProducts.length > 0 && (
                <span className="tab-badge">{evidenceProducts.length}</span>
              )}
            </button>
            <button
              type="button"
              className={`tab ${activeTab === "explanation" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("explanation")}
            >
              Explanation
            </button>
            <button
              type="button"
              className={`tab ${activeTab === "actions" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("actions")}
            >
              Next actions
            </button>
          </div>
        </div>

        <div className="evidence-panel__content">
          {activeTab === "evidence" && (
            <div className="evidence-grid">
              {normalizedEvidenceProducts.map((product, index) => {
                const productScore = scoreMap.get(product.id);
                const whySummary =
                  productScore?.alignment_reasoning ??
                  "Aligned with core intent signals.";
                const highlights = productScore?.matched_capabilities ?? [];
                return (
                  <EvidenceCard
                    key={product.id}
                    product={product}
                    optimizedDescription={undefined}
                    showOptimization={false}
                    index={index}
                    whySummary={whySummary}
                    highlightSignals={highlights}
                  />
                );
              })}
            </div>
          )}

          {activeTab === "explanation" && (
            <div className="explanation-content">
              <div className="explain-grid">
                <div className="explain-card">
                  <div className="explain-card__title">Alignment Score distribution</div>
                  <div className="histogram">
                    {histogram.map((bucket) => (
                      <div key={bucket.label} className="histogram__row">
                        <span className="histogram__label">{bucket.label}</span>
                        <div className="histogram__bar">
                          <span
                            className="histogram__fill"
                            style={{
                              width: `${(bucket.count / maxBucket) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="histogram__count">{bucket.count}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="explain-card">
                  <div className="explain-card__title">Why they win</div>
                  <div className="winner-list">
                    {winners.map((winner) => (
                      <div key={winner.id} className="winner-item">
                        <div className="winner-item__header">
                          <span className="winner-item__name">{winner.name}</span>
                          <span className="winner-item__score">
                            {(winner.score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="winner-item__reason">{winner.reasoning}</p>
                        {winner.matched.length > 0 && (
                          <div className="signal-list">
                            {winner.matched.slice(0, 4).map((signal) => (
                              <span
                                key={signal}
                                className="signal-chip"
                                title={signal}
                              >
                                {signal}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="explain-card">
                  <div className="explain-card__title">Signal deltas</div>
                  <div className="signal-columns">
                    <div>
                      <div className="signal-heading">Missing in our copy</div>
                      <div className="signal-list">
                        {(missingGoalSignals.length
                          ? missingGoalSignals
                          : ["No gaps detected"]
                        ).map((signal) => (
                          <span
                            key={signal}
                            className="signal-chip muted"
                            title={signal}
                          >
                            {signal}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="signal-heading">Unique to our copy</div>
                      <div className="signal-list">
                        {(extraSignals.length
                          ? extraSignals
                          : ["No unique signals"]
                        ).map((signal) => (
                          <span
                            key={signal}
                            className="signal-chip neutral"
                            title={signal}
                          >
                            {signal}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="explain-card">
                  <div className="explain-card__title">Our copy snapshot</div>
                  <p className="copy-block">
                    {targetProductCopy
                      ? targetProductCopy
                      : "No stored copy found for this product yet."}
                  </p>
                  {targetProductUrl && (
                    <a
                      className="copy-link"
                      href={targetProductUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Source URL →
                    </a>
                  )}
                  <div>
                    <div className="signal-heading">Signals detected</div>
                    <div className="signal-list">
                      {(detectedSignals.length
                        ? detectedSignals
                        : ["No clear signals detected"]
                      ).map((signal) => (
                        <span
                          key={signal}
                          className="signal-chip neutral"
                          title={signal}
                        >
                          {signal}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="explain-grid explain-grid--signals">
                <div className="explain-card">
                  <div className="explain-card__title">Intent/Goal signals</div>
                  <p className="explain-card__note">
                    Derived from the clarified intent. Higher weight = more explicit in
                    the query.
                  </p>
                  <div className="signal-list">
                    {(intentSignalsWeighted.length
                      ? intentSignalsWeighted
                      : [{ signal: "No intent signals", weight: 0 }]
                    ).map((item) => (
                      <span
                        key={item.signal}
                        className="signal-chip"
                        title={item.signal}
                      >
                        {item.signal} · {Math.round(item.weight * 100)}%
                      </span>
                    ))}
                  </div>
                  <div className="signal-legend">
                    <span className="signal-legend__label">Weight</span>
                    <span className="signal-legend__detail">
                      Confidence × explicitness in the query
                    </span>
                  </div>
                </div>
                <div className="explain-card">
                  <div className="explain-card__title">Evidence signals</div>
                  <p className="explain-card__note">
                    Extracted from top-ranked products. Higher weight = more frequent
                    among winners.
                  </p>
                  <div className="signal-list">
                    {(evidenceSignalsWeighted.length
                      ? evidenceSignalsWeighted
                      : [{ signal: "No evidence signals", weight: 0 }]
                    ).map((item) => (
                      <span
                        key={item.signal}
                        className="signal-chip neutral"
                        title={item.signal}
                      >
                        {item.signal} · {Math.round(item.weight * 100)}%
                      </span>
                    ))}
                  </div>
                  <div className="signal-legend">
                    <span className="signal-legend__label">Weight</span>
                    <span className="signal-legend__detail">
                      Frequency among winners × alignment score
                    </span>
                  </div>
                </div>
                <div className="explain-card">
                  <div className="explain-card__title">Copy presence</div>
                  <p className="explain-card__note">
                    Whether our current copy already contains each signal.
                  </p>
                  <div className="signal-list">
                    {(copyPresenceWeighted.length
                      ? copyPresenceWeighted
                      : [{ signal: "No copy signals", present: false }]
                    ).map((item) => (
                      <span
                        key={item.signal}
                        className={`signal-chip ${item.present ? "" : "muted"}`}
                        title={item.signal}
                      >
                        {item.signal} · {item.present ? "Yes" : "No"}
                      </span>
                    ))}
                  </div>
                  <div className="signal-legend">
                    <span className="signal-legend__label">Signal check</span>
                    <span className="signal-legend__detail">
                      Phrase-level coverage in current copy
                    </span>
                  </div>
                </div>
                <div className="explain-card">
                  <div className="explain-card__title">Specificity vs breadth</div>
                  <p className="explain-card__note">
                    Specificity helps you win the exact intent; breadth expands adjacent
                    discovery.
                  </p>
                  <div className="signal-list">
                    <span className="signal-chip">
                      Specificity · {Math.round(specificityRatio * 100)}%
                    </span>
                    <span className="signal-chip neutral">
                      Breadth · {Math.round((1 - specificityRatio) * 100)}%
                    </span>
                  </div>
                  <p className="summary-card__note">
                    Intent signals drive specificity; evidence signals drive breadth.
                  </p>
                  <div className="signal-legend">
                    <span className="signal-legend__label">Interpretation</span>
                    <span className="signal-legend__detail">
                      High specificity = tight intent fit; high breadth = wider reach
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "actions" && (
            <div className="actions-content">
              <div className="action-card">
                <div className="action-card__title">Recommended next test</div>
                <p className="action-card__text">
                  Prioritize the top missing signals, then re-run simulation to
                  validate lift.
                </p>
                <div className="signal-list">
                  {missingSignals.slice(0, 4).map((signal) => (
                    <span key={signal} className="signal-chip" title={signal}>
                      {signal}
                    </span>
                  ))}
                </div>
                {counterfactualLift !== null && (
                  <p className="action-card__note">
                    Estimated lift: +{Math.round(counterfactualLift * 100)}%
                  </p>
                )}
                {onOpenSimulation && (
                  <button
                    type="button"
                    className="button button--primary-subtle"
                    onClick={onOpenSimulation}
                  >
                    Open simulation
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .evidence-summary {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 16px;
          margin-bottom: 16px;
        }

        .evidence-panel {
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          min-height: 0;
          width: 100%;
          flex: 1;
        }

        .summary-card {
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          padding: 14px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .explain-grid {
          display: grid;
          gap: 16px;
          grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .explain-grid--signals {
          margin-top: 16px;
        }

        @media (max-width: 1200px) {
          .explain-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        @media (max-width: 720px) {
          .explain-grid {
            grid-template-columns: 1fr;
          }
        }

        .explain-card__note {
          margin: 0 0 10px;
          font-size: 0.82rem;
          color: rgba(255, 255, 255, 0.6);
          line-height: 1.45;
        }

        .signal-legend {
          margin-top: 10px;
          padding-top: 10px;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          font-size: 0.78rem;
          color: rgba(255, 255, 255, 0.55);
        }

        .signal-legend__label {
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-size: 0.68rem;
          color: rgba(255, 255, 255, 0.45);
        }

        .summary-card__title {
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
        }

        .summary-card__value {
          font-size: 1.1rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
        }

        .summary-card__subtle {
          font-size: 0.85rem;
          color: rgba(140, 255, 208, 0.8);
        }

        .summary-card__meta {
          font-size: 0.8rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .summary-card__note {
          margin: 0;
          font-size: 0.78rem;
          color: rgba(255, 255, 255, 0.6);
          line-height: 1.4;
        }

        .evidence-panel__header {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.03);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .header-title {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .header-title h3 {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
        }

        .header-badge {
          padding: 0.25rem 0.75rem;
          background: rgba(28, 200, 134, 0.08);
          border: 1px solid rgba(28, 200, 134, 0.25);
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 700;
          color: rgba(140, 255, 208, 0.85);
        }

        .header-tabs {
          display: flex;
          gap: 0.5rem;
          overflow-x: auto;
        }

        .tab {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.75rem 1.25rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          color: rgba(255, 255, 255, 0.7);
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }

        .tab:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.05);
          color: rgba(255, 255, 255, 0.9);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .tab--active {
          background: rgba(12, 20, 18, 0.8);
          border-color: rgba(28, 200, 134, 0.4);
          color: rgba(255, 255, 255, 0.95);
          box-shadow: 0 0 0 1px rgba(28, 200, 134, 0.2);
        }

        .tab:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .tab-badge {
          padding: 0.125rem 0.5rem;
          background: rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          font-size: 0.75rem;
          font-weight: 700;
        }

        .tab--active .tab-badge {
          background: rgba(28, 200, 134, 0.15);
          color: rgba(140, 255, 208, 0.9);
        }

        .tab-indicator {
          font-size: 0.875rem;
        }

        .evidence-panel__content {
          padding: 2rem;
          flex: 1;
          min-height: 0;
          overflow-y: auto;
        }

        .evidence-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
          gap: 1.25rem;
        }

        @media (max-width: 768px) {
          .evidence-grid {
            grid-template-columns: 1fr;
          }
        }

        .evidence-panel__content::-webkit-scrollbar {
          width: 0;
          height: 0;
        }

        .evidence-panel__content {
          scrollbar-width: none;
        }

        .evidence-panel--page .evidence-panel__content {
          overflow: visible;
          flex: 0 0 auto;
          max-height: none;
        }

        .evidence-panel--page {
          overflow: visible;
          flex: 0 0 auto;
          min-height: auto;
        }

        @media (max-width: 1024px) {
          .evidence-panel__content {
            padding: 1.5rem;
          }
        }

        @media (max-width: 768px) {
          .evidence-panel {
            overflow: visible;
          }

          .evidence-panel__content {
            overflow: visible;
            padding: 1.25rem;
          }

          .evidence-summary {
            grid-template-columns: 1fr;
          }

          .evidence-panel__header {
            padding: 1.25rem;
          }

          .header-tabs {
            flex-wrap: wrap;
          }
        }

        @media (max-height: 820px) {
          .evidence-panel {
            overflow: visible;
          }

          .evidence-panel__content {
            max-height: none;
            overflow: visible;
          }
        }

        .explanation-content,
        .actions-content {
          max-width: 100%;
          margin: 0 auto;
          width: 100%;
        }


        .explain-card,
        .action-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 10px;
          padding: 1.25rem;
          display: flex;
          flex-direction: column;
          gap: 0.85rem;
          min-height: 320px;
        }

        .explain-card__title,
        .action-card__title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: rgba(255, 255, 255, 0.6);
          font-weight: 600;
        }

        .histogram {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .histogram__row {
          display: grid;
          grid-template-columns: 60px 1fr 30px;
          gap: 0.5rem;
          align-items: center;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .histogram__bar {
          height: 6px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.05);
          overflow: hidden;
        }

        .histogram__fill {
          display: block;
          height: 100%;
          background: rgba(28, 200, 134, 0.5);
        }

        .winner-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .winner-item__header {
          display: flex;
          justify-content: space-between;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.85);
        }

        .winner-item__reason {
          margin: 0;
          font-size: 0.85rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .signal-columns {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
          gap: 1rem;
          align-items: start;
          flex: 1;
          min-height: 0;
        }

        .signal-columns > div {
          display: flex;
          flex-direction: column;
          min-height: 0;
        }

        .signal-heading {
          font-size: 0.75rem;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.5);
          margin-bottom: 0.5rem;
        }

        .signal-list {
          display: flex;
          flex-wrap: wrap;
          gap: 0.4rem;
          overflow-y: auto;
          padding-right: 0.25rem;
          min-width: 0;
          align-items: flex-start;
          flex: 1;
        }

        .signal-chip {
          padding: 0.3rem 0.6rem;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.08);
          color: rgba(255, 255, 255, 0.78);
          font-size: 0.75rem;
          text-transform: none;
          letter-spacing: 0.01em;
          max-width: 100%;
          white-space: normal;
          line-height: 1.35;
          overflow-wrap: anywhere;
          display: inline-flex;
          align-items: flex-start;
          text-align: left;
        }

        .signal-chip.muted {
          background: rgba(255, 255, 255, 0.03);
          border-color: rgba(255, 255, 255, 0.08);
          color: rgba(255, 255, 255, 0.55);
        }

        .signal-chip.neutral {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(255, 255, 255, 0.12);
          color: rgba(255, 255, 255, 0.68);
        }

        .action-card__text {
          font-size: 0.9rem;
          color: rgba(255, 255, 255, 0.7);
          margin: 0;
        }

        .action-card__note {
          font-size: 0.8rem;
          color: rgba(140, 255, 208, 0.8);
          margin: 0;
        }

        .signal-list::-webkit-scrollbar {
          width: 0;
          height: 0;
        }

        .signal-list {
          scrollbar-width: none;
        }

        .copy-block {
          margin: 0;
          font-size: 0.88rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.7);
          white-space: pre-wrap;
        }

        .copy-link {
          color: rgba(140, 255, 208, 0.85);
          text-decoration: none;
          font-weight: 600;
          font-size: 0.8rem;
        }

        .copy-link:hover {
          color: rgba(140, 255, 208, 1);
          text-decoration: underline;
        }

        .tab-empty {
          padding: 4rem 2rem;
          text-align: center;
          color: rgba(255, 255, 255, 0.6);
        }

        .tab-empty p {
          margin: 0 0 0.5rem 0;
        }

        .tab-empty__hint {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.4);
        }
      `}</style>
    </>
  );
}
