"use client";

import React from "react";
import { formatOperatorIdentifier } from "../../lib/operatorDisplayLanguage";
import type { ExperimentRecommendation, NextTestRecommendation } from "../../lib/types";

type Props = {
  open: boolean;
  recommendations: ExperimentRecommendation[];
  runningVariantId: string | null;
  canRunVariantTests: boolean;
  isSubmitting: boolean;
  isCreatingSuggestedVariant: boolean;
  onOpenChange: (open: boolean) => void;
  onRunRecommendation: (variantId?: string | null) => void;
  onCreateVariantFromRecommendation: (recommendation: NextTestRecommendation) => void;
};

export function OrchestratorRecommendationsPanel({
  open,
  recommendations,
  runningVariantId,
  canRunVariantTests,
  isSubmitting,
  isCreatingSuggestedVariant,
  onOpenChange,
  onRunRecommendation,
  onCreateVariantFromRecommendation,
}: Props) {
  return (
    <section className="panel__card panel__card--secondary panel__card--full-row">
      <div className="panel__header">
        <h3>Orchestrator Recommendations</h3>
        <button
          type="button"
          className="panel__action panel__action--ghost"
          onClick={() => onOpenChange(!open)}
        >
          {open ? "Hide details" : "Show details"}
        </button>
      </div>
      <p className="panel__subheading">Optional guidance</p>
      <p className="panel__muted">
        Suggested next actions based on current variant outcomes and run history.
      </p>
      {!open ? (
        <p className="panel__muted">Recommendations are collapsed to keep focus on execution steps.</p>
      ) : recommendations.length === 0 ? (
        <p className="panel__empty">No recommendations yet.</p>
      ) : (
        <ul className="panel__list panel__list--compact">
          {recommendations.map((rec) => (
            <li key={rec.id}>
              <div className="panel__meta">
                <span>{rec.recommendation.reason}</span>
                <span className="panel__badge panel__badge--secondary">
                  {formatOperatorIdentifier(rec.recommendation.action)}
                </span>
              </div>
              <span className="panel__muted">
                {rec.created_at ? new Date(rec.created_at).toLocaleDateString() : ""}
              </span>
              {rec.recommendation.action === "run_variant" ? (
                <div className="panel__actions">
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={() => onRunRecommendation(rec.recommendation.variant_id)}
                    disabled={
                      runningVariantId === rec.recommendation.variant_id || !canRunVariantTests
                    }
                  >
                    {runningVariantId === rec.recommendation.variant_id
                      ? "Running…"
                      : "Run next test"}
                  </button>
                </div>
              ) : rec.recommendation.action === "create_variant" ? (
                <div className="panel__actions">
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={() => onCreateVariantFromRecommendation(rec.recommendation)}
                    disabled={isSubmitting}
                  >
                    {isCreatingSuggestedVariant ? (
                      <>
                        Creating variant<span className="button__dots" />
                      </>
                    ) : (
                      "Create + run variant"
                    )}
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
