"use client";

import React, { forwardRef, type ReactNode } from "react";

type Props = {
  labMode: "lab" | "manual";
  variantCount: number;
  selectedExperimentId: string | null;
  isRecommending: boolean;
  onRecommendNextTest: () => void;
  children: ReactNode;
};

export const VariantsIterationPanel = forwardRef<HTMLElement, Props>(
  function VariantsIterationPanel(
    {
      labMode,
      variantCount,
      selectedExperimentId,
      isRecommending,
      onRecommendNextTest,
      children,
    },
    ref,
  ) {
    return (
      <section className="panel__card panel__card--primary panel__card--full-row" ref={ref}>
        <div className="panel__header">
          <h3>{labMode === "lab" ? "Variants and Iteration" : "Variants"}</h3>
          <div className="panel__meta">
            {variantCount > 0 ? <span className="panel__badge">{variantCount}</span> : null}
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onRecommendNextTest}
              disabled={!selectedExperimentId || isRecommending}
            >
              {isRecommending ? "Recommending…" : "Recommend next test"}
            </button>
          </div>
        </div>
        <p className="panel__muted">
          Variants are copy candidates tested against the same query battery.
        </p>
        <p className="panel__subheading">Step 4 · Create variants</p>
        <p className="panel__step-helper">
          {labMode === "lab"
            ? "Automation-first: generate candidate copy, then create and run quickly."
            : "Choose a source, shape candidate copy, then add the variant."}
        </p>
        <div className="variant-flow">
          <span className="variant-flow__step is-active">1. Define</span>
          <span className="variant-flow__step is-active">2. Create</span>
          <span className={`variant-flow__step ${variantCount > 0 ? "is-active" : ""}`}>
            3. Run
          </span>
        </div>
        {children}
      </section>
    );
  },
);
