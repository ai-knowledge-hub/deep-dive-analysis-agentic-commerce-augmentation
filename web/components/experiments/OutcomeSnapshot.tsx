import React from "react";

type OutcomeSnapshotView = {
  runVariantLabel: string;
  runQueryLabel: string;
  runCreatedAt: string | null;
  winRate: string;
  avgScore: string;
  validationState: string;
  snapshotVersion: number | null;
};

type OutcomeSnapshotProps = {
  snapshot: OutcomeSnapshotView;
  hasValidationSignals: boolean;
  onOpenValidation: () => void;
};

export function OutcomeSnapshot({
  snapshot,
  hasValidationSignals,
  onOpenValidation,
}: OutcomeSnapshotProps) {
  return (
    <section className="panel__notice panel__notice--info outcome-snapshot">
      <div className="panel__meta">
        <strong>Outcome summary</strong>
        <span className="panel__badge panel__badge--secondary">Unified view</span>
      </div>
      <div className="outcome-snapshot__grid">
        <div className="outcome-snapshot__item">
          <span className="outcome-snapshot__label">Latest run</span>
          <span className="outcome-snapshot__value">{snapshot.runVariantLabel}</span>
          <span className="panel__muted">
            Query: {snapshot.runQueryLabel}
            {snapshot.runCreatedAt ? ` · ${new Date(snapshot.runCreatedAt).toLocaleString()}` : ""}
          </span>
        </div>
        <div className="outcome-snapshot__item">
          <span className="outcome-snapshot__label">Key metrics</span>
          <span className="outcome-snapshot__value">Win rate: {snapshot.winRate}</span>
          <span className="panel__muted">Avg score: {snapshot.avgScore}</span>
        </div>
        <div className="outcome-snapshot__item">
          <span className="outcome-snapshot__label">Validation state</span>
          <span className="outcome-snapshot__value">{snapshot.validationState}</span>
          <span className="panel__muted">
            Evidence protocol:{" "}
            {snapshot.snapshotVersion && snapshot.snapshotVersion > 0
              ? `v${snapshot.snapshotVersion}`
              : "pending"}
          </span>
          {!hasValidationSignals ? (
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onOpenValidation}
            >
              Go to Validation
            </button>
          ) : (
            <span className="panel__muted">Signals are being tracked.</span>
          )}
        </div>
      </div>
    </section>
  );
}
