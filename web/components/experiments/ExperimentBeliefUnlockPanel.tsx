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

export const ExperimentBeliefUnlockPanel = forwardRef<HTMLDivElement, Props>(
  function ExperimentBeliefUnlockPanel(
    { brandId, clientId, userId, validationSummary, viewMode, onViewModeChange, onUseBelief },
    ref,
  ) {
    if (!brandId) return null;

    if (validationSummary?.unlock_ready) {
      return (
        <div ref={ref}>
          <BrandBeliefs
            brandId={brandId}
            clientId={clientId}
            userId={userId}
            limit={50}
            onUseBelief={(belief) => onUseBelief(belief as BrandBelief)}
            viewMode={viewMode}
            onViewModeChange={onViewModeChange}
          />
        </div>
      );
    }

    const progress = Math.round((validationSummary?.progress ?? 0) * 100);

    return (
      <section className="panel__card">
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
