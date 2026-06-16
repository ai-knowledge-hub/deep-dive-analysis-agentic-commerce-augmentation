"use client";

import React, { forwardRef } from "react";
import { BrandBeliefs } from "../beliefs/BrandBeliefs";
import type { BrandBelief, ValidationSummary } from "../../lib/types";

type BeliefViewMode = "list" | "timeline" | "trends";

type Props = {
  brandId: string | null | undefined;
  clientId?: string;
  userId?: string;
  validationSummary: ValidationSummary | null;
  viewMode: BeliefViewMode;
  onViewModeChange: (mode: BeliefViewMode) => void;
  onUseBelief: (belief: BrandBelief) => void;
};

export const ExperimentBeliefUnlockPanel = forwardRef<HTMLElement, Props>(
  function ExperimentBeliefUnlockPanel(
    { brandId, clientId, userId, validationSummary, viewMode, onViewModeChange, onUseBelief },
    ref,
  ) {
    if (!brandId) return null;

    if (validationSummary?.unlock_ready) {
      return (
        <section ref={ref} tabIndex={-1} aria-label="Experiment insights">
          <BrandBeliefs
            brandId={brandId}
            clientId={clientId}
            userId={userId}
            limit={50}
            onUseBelief={(belief) => onUseBelief(belief as BrandBelief)}
            viewMode={viewMode}
            onViewModeChange={onViewModeChange}
          />
        </section>
      );
    }

    const progress = Math.round((validationSummary?.progress ?? 0) * 100);

    return (
      <section ref={ref} className="panel__card" tabIndex={-1} aria-label="Experiment insights">
        <div className="panel__header">
          <h3>Pattern Insights (Locked)</h3>
          <span className="panel__badge panel__badge--secondary">Locked</span>
        </div>
        <p className="panel__muted">
          Insights appear after enough experiment evidence accumulates.
        </p>
        <div className="progress-bar">
          <div className="progress-bar__fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="panel__muted">Progress: {progress}%</p>
      </section>
    );
  },
);
