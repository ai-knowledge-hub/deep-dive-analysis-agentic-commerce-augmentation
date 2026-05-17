"use client";

import React, { forwardRef } from "react";
import type { ExperimentMetric, ExperimentVariant } from "../../lib/types";

type MetricTrend = "win_rate" | "avg_score";

type Props = {
  metricsHistory: ExperimentMetric[];
  recentMetrics: ExperimentMetric[];
  variants: ExperimentVariant[];
  metricsTrend: number[];
  metricsTrendMetric: MetricTrend;
  metricsHistoryExpanded: boolean;
  latestMetricCreatedAt?: string | null;
  renderMetricValue: (value: unknown, fallback?: string) => string;
  onTrendMetricChange: (metric: MetricTrend) => void;
  onHistoryExpandedChange: (expanded: boolean) => void;
  onOpenOverview: () => void;
};

export const ExperimentMetricsPanel = forwardRef<HTMLElement, Props>(
  function ExperimentMetricsPanel(
    {
      metricsHistory,
      recentMetrics,
      variants,
      metricsTrend,
      metricsTrendMetric,
      metricsHistoryExpanded,
      latestMetricCreatedAt,
      renderMetricValue,
      onTrendMetricChange,
      onHistoryExpandedChange,
      onOpenOverview,
    },
    ref,
  ) {
    return (
      <section className="panel__card panel__card--secondary" ref={ref}>
        <div className="panel__header">
          <h3>Metrics</h3>
          <div className="panel__meta">
            <span className="panel__muted">Experiment-scoped (compact)</span>
          </div>
        </div>
        <div className="panel__meta panel__meta--stack">
          <span className="panel__muted">
            Entries: {metricsHistory.length}
            {latestMetricCreatedAt
              ? ` · Last update: ${new Date(latestMetricCreatedAt).toLocaleString()}`
              : ""}
          </span>
          {renderSparkline(metricsTrend) ?? <span className="panel__muted">No trend yet.</span>}
        </div>
        <div className="panel__actions">
          <button
            type="button"
            className={`panel__action panel__action--ghost ${
              metricsTrendMetric === "win_rate" ? "is-active" : ""
            }`}
            onClick={() => onTrendMetricChange("win_rate")}
          >
            Win rate
          </button>
          <button
            type="button"
            className={`panel__action panel__action--ghost ${
              metricsTrendMetric === "avg_score" ? "is-active" : ""
            }`}
            onClick={() => onTrendMetricChange("avg_score")}
          >
            Avg score
          </button>
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={() => onHistoryExpandedChange(!metricsHistoryExpanded)}
            disabled={metricsHistory.length === 0}
          >
            {metricsHistoryExpanded ? "Hide history" : "Show history"}
          </button>
          <button type="button" className="panel__action panel__action--ghost" onClick={onOpenOverview}>
            Open Overview analytics
          </button>
        </div>
        {metricsHistory.length === 0 ? (
          <p className="panel__empty">No metrics history yet.</p>
        ) : !metricsHistoryExpanded ? (
          <p className="panel__muted">History is collapsed to keep this page focused on execution.</p>
        ) : (
          <ul className="panel__list">
            {recentMetrics.map((metric) => {
              const values = (metric.metrics ?? {}) as Record<string, unknown>;
              const variantLabel =
                variants.find((variant) => variant.id === metric.variant_id)?.label ??
                metric.variant_id;
              return (
                <li key={metric.id}>
                  <div className="panel__meta">
                    <span>{variantLabel}</span>
                    <span className="panel__muted">
                      {metric.created_at ? new Date(metric.created_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <span className="panel__muted">
                    Win rate: {renderMetricValue(values.win_rate)} · Avg score:{" "}
                    {renderMetricValue(values.avg_score)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    );
  },
);

function renderSparkline(values: number[]) {
  if (values.length === 0) return null;
  const width = 120;
  const height = 36;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const points = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  });
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke="rgba(28, 200, 134, 0.7)" strokeWidth="2" points={points.join(" ")} />
    </svg>
  );
}
