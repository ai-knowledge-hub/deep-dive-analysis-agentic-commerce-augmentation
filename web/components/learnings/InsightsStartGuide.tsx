"use client";

import React from "react";

export type InsightRecommendation = {
  title: string;
  summary: string;
  href: string;
  cta: string;
};

type Props = {
  recommendation: InsightRecommendation | null;
  onOpenRecommendation: (href: string) => void;
  onOpenRuns: () => void;
};

export function InsightsStartGuide({
  recommendation,
  onOpenRecommendation,
  onOpenRuns,
}: Props) {
  const title = recommendation
    ? `Start with ${recommendation.title.toLowerCase()}`
    : "Start with supervised execution";
  const summary =
    recommendation?.summary ||
    "Current signals look stable. Use Runs to keep supervised execution moving.";
  const cta = recommendation?.cta || "Open runs";

  return (
    <section className="control-surface control-grid__full agent-start-guide">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Start here</span>
          <h3 className="control-section__title">{title}</h3>
          <div className="control-section__summary">
            Insights keeps one recommended follow-up above the learning detail.
          </div>
        </div>
        <span className="control-chip control-chip--attention">Next</span>
      </div>
      <div className="panel__notice panel__notice--info">{summary}</div>
      <div className="panel__actions">
        <button
          type="button"
          className="button button--primary"
          onClick={() => {
            if (recommendation) {
              onOpenRecommendation(recommendation.href);
            } else {
              onOpenRuns();
            }
          }}
        >
          {cta}
        </button>
      </div>
    </section>
  );
}
