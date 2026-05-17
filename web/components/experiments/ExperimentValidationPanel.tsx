"use client";

import React from "react";
import type { ValidationSummary } from "../../lib/types";

type Props = {
  hasValidationSignals: boolean;
  validationSummary: ValidationSummary | null;
  onOpenValidation: () => void;
  onBackToVariants: () => void;
};

export function ExperimentValidationPanel({
  hasValidationSignals,
  validationSummary,
  onOpenValidation,
  onBackToVariants,
}: Props) {
  return (
    <section className="panel__card panel__card--primary panel__card--full-row">
      <div className="panel__header">
        <h3>Step 7 · Validate synthetic and observed results</h3>
        <span
          className={`panel__badge ${
            hasValidationSignals ? "panel__badge--success" : "panel__badge--secondary"
          }`}
        >
          {hasValidationSignals ? "Validation started" : "Validation pending"}
        </span>
      </div>
      <p className="panel__muted">
        Validation is required to ground lab signals with observed evidence and build decision trust.
      </p>
      <div className="panel__meta panel__meta--stack">
        <span className="panel__muted">
          Logged: {validationSummary?.total_logged ?? 0} · Verified:{" "}
          {validationSummary?.verified_runs ?? 0} · Accuracy:{" "}
          {typeof validationSummary?.accuracy === "number"
            ? `${Math.round(validationSummary.accuracy * 100)}%`
            : "—"}
        </span>
        <span className="panel__muted">
          Observed logs: {validationSummary?.observed_signals_logged ?? 0} · Observed accuracy:{" "}
          {typeof validationSummary?.observed_accuracy === "number"
            ? `${Math.round(validationSummary.observed_accuracy * 100)}%`
            : "—"}
        </span>
      </div>
      <div className="panel__actions">
        <button
          type="button"
          className="panel__action panel__action--prominent"
          onClick={onOpenValidation}
        >
          Open Validation
        </button>
        <button type="button" className="panel__action panel__action--ghost" onClick={onBackToVariants}>
          Back to variants (Step 8)
        </button>
      </div>
    </section>
  );
}
