import React from "react";
import type { ExperimentVariant } from "../../lib/types";

type ExperimentVariantRunItemProps = {
  variant: ExperimentVariant;
  tested: boolean;
  hypothesisLabel: string;
  hypothesisStatement: Record<string, unknown> | null;
  hypothesisExpanded: boolean;
  copyExpanded: boolean;
  resolvedDescription: string | null;
  metricValues: Record<string, unknown> | null;
  runButtonProminent: boolean;
  running: boolean;
  canRun: boolean;
  renderMetricValue: (value: unknown, fallback?: string) => string;
  onToggleHypothesis: () => void;
  onToggleCopy: () => void;
  onRun: () => void;
};

export function ExperimentVariantRunItem({
  variant,
  tested,
  hypothesisLabel,
  hypothesisStatement,
  hypothesisExpanded,
  copyExpanded,
  resolvedDescription,
  metricValues,
  runButtonProminent,
  running,
  canRun,
  renderMetricValue,
  onToggleHypothesis,
  onToggleCopy,
  onRun,
}: ExperimentVariantRunItemProps) {
  return (
    <>
      <div className="panel__meta">
        <span>{variant.label}</span>
        <span className="panel__badge panel__badge--secondary">{variant.type}</span>
        <span
          className={`panel__badge ${
            tested ? "panel__badge--success" : "panel__badge--secondary"
          }`}
        >
          {tested ? "Tested" : "Draft"}
        </span>
        {variant.hypothesis_id ? (
          <span className="panel__badge panel__badge--secondary">{hypothesisLabel}</span>
        ) : null}
      </div>
      {variant.hypothesis_id ? (
        <div className="panel__actions">
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={onToggleHypothesis}
          >
            {hypothesisExpanded ? "Hide test idea details" : "View test idea details"}
          </button>
        </div>
      ) : null}
      {variant.hypothesis_id && hypothesisExpanded ? (
        <div className="panel__meta panel__meta--stack">
          <span className="panel__muted">If: {String(hypothesisStatement?.if ?? "—")}</span>
          <span className="panel__muted">Then: {String(hypothesisStatement?.then ?? "—")}</span>
          <span className="panel__muted">For: {String(hypothesisStatement?.for ?? "—")}</span>
        </div>
      ) : null}
      {resolvedDescription ? (
        <div className="panel__actions">
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={onToggleCopy}
          >
            {copyExpanded ? "Hide tested copy" : "View tested copy"}
          </button>
        </div>
      ) : (
        <span className="panel__muted">No copy payload yet.</span>
      )}
      {copyExpanded && resolvedDescription ? (
        <pre className="panel__pre">{resolvedDescription}</pre>
      ) : null}
      {tested && metricValues ? (
        <div className="panel__meta">
          <span className="panel__muted">
            Win rate: {renderMetricValue(metricValues.win_rate)}
          </span>
          <span className="panel__muted">
            Runs: {renderMetricValue(metricValues.total_runs)}
          </span>
          <span className="panel__muted">
            Confidence: {renderMetricValue(metricValues.posterior)}
          </span>
          <span className="panel__muted">
            Decision: {renderMetricValue(metricValues.decision_action)}
          </span>
        </div>
      ) : null}
      <button
        type="button"
        className={`panel__action ${
          runButtonProminent ? "panel__action--prominent" : "panel__action--ghost"
        }`}
        onClick={onRun}
        disabled={running || !canRun}
      >
        {running ? "Running…" : "Run variant test"}
      </button>
    </>
  );
}
