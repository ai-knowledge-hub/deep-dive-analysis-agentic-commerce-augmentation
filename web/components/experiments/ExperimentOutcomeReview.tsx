import React from "react";

type SignalCount = { signal: string; count: number };

type ExperimentGapSummary = {
  missing: SignalCount[];
  winner: SignalCount[];
  summaries: string[];
  total: number;
};

type ExperimentOutcomeReviewProps = {
  latestMetric: Record<string, unknown> | null;
  experimentGapSummary: ExperimentGapSummary | null;
  renderMetricValue: (value: unknown, fallback?: string) => string;
};

function formatDecisionValue(
  value: unknown,
  renderMetricValue: (value: unknown, fallback?: string) => string,
) {
  return renderMetricValue(value, "-").replace(/[._-]+/g, " ");
}

export function ExperimentOutcomeReview({
  latestMetric,
  experimentGapSummary,
  renderMetricValue,
}: ExperimentOutcomeReviewProps) {
  return (
    <div className="panel__grid">
      <div className="panel__column">
        <h4 className="panel__subtitle">Step 6 · Review outcomes and metrics</h4>
        {latestMetric ? (
          <ul className="panel__list panel__list--compact">
            <li>Total runs: {renderMetricValue(latestMetric.total_runs, "-")}</li>
            <li>Wins: {renderMetricValue(latestMetric.wins, "-")}</li>
            <li>Win rate: {renderMetricValue(latestMetric.win_rate, "-")}</li>
            <li>
              Keyword-match wins: {renderMetricValue(latestMetric.win_rate_keyword, "-")}
            </li>
            <li>Reliable wins: {renderMetricValue(latestMetric.win_rate_robust, "-")}</li>
            <li>Average score: {renderMetricValue(latestMetric.avg_score, "-")}</li>
            <li>
              Judge agreement: {renderMetricValue(latestMetric.judge_consensus_win_rate, "-")}
            </li>
            <li>Evidence set: {renderMetricValue(latestMetric.snapshot_version, "-")}</li>
            <li>Confidence: {renderMetricValue(latestMetric.posterior, "-")}</li>
            <li>
              Recommended decision:{" "}
              {formatDecisionValue(latestMetric.decision_action, renderMetricValue)}
            </li>
          </ul>
        ) : (
          <p className="panel__muted">Run a variant to generate metrics.</p>
        )}
      </div>
      <div className="panel__column">
        <div className="panel__meta">
          <h4 className="panel__subtitle">Why we lost (experiment deltas)</h4>
          {experimentGapSummary?.total ? (
            <span className="panel__badge panel__badge--secondary">
              {experimentGapSummary.total} linked runs
            </span>
          ) : null}
        </div>
        {!experimentGapSummary || experimentGapSummary.total === 0 ? (
          <p className="panel__muted">
            Run a variant with linked simulations to see gap signals.
          </p>
        ) : (
          <div className="panel__grid">
            <div className="panel__column">
              <h4 className="panel__subtitle">Top missing signals</h4>
              {experimentGapSummary.missing.length === 0 ? (
                <p className="panel__muted">No missing signals yet.</p>
              ) : (
                <ul className="panel__list panel__list--compact">
                  {experimentGapSummary.missing.map((item) => (
                    <li key={`missing-${item.signal}`}>
                      {item.signal} · {item.count}x
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="panel__column">
              <h4 className="panel__subtitle">Winner signals</h4>
              {experimentGapSummary.winner.length === 0 ? (
                <p className="panel__muted">No winner signals yet.</p>
              ) : (
                <ul className="panel__list panel__list--compact">
                  {experimentGapSummary.winner.map((item) => (
                    <li key={`winner-${item.signal}`}>
                      {item.signal} · {item.count}x
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {experimentGapSummary.summaries.length > 0 ? (
              <div className="panel__column">
                <h4 className="panel__subtitle">Gap summaries</h4>
                <ul className="panel__list panel__list--compact">
                  {experimentGapSummary.summaries.map((summary, index) => (
                    <li key={`summary-${index}`}>{summary}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
