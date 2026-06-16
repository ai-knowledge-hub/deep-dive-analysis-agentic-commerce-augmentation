import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { ExperimentOutcomeReview } from "./ExperimentOutcomeReview";

describe("ExperimentOutcomeReview", () => {
  it("uses readable outcome metric labels", () => {
    render(
      <ExperimentOutcomeReview
        latestMetric={{
          total_runs: 3,
          wins: 2,
          win_rate: 0.67,
          win_rate_keyword: 0.5,
          win_rate_robust: 0.6,
          avg_score: 0.72,
          judge_consensus_win_rate: 0.7,
          snapshot_version: 4,
          posterior: 0.81,
          decision_action: "continue_experiment",
        }}
        experimentGapSummary={null}
        renderMetricValue={(value) => String(value)}
      />,
    );

    expect(screen.getByText(/Evidence set: 4/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence: 0.81/i)).toBeInTheDocument();
    expect(screen.getByText(/Keyword-match wins: 0.5/i)).toBeInTheDocument();
    expect(screen.getByText(/Reliable wins: 0.6/i)).toBeInTheDocument();
    expect(screen.getByText(/Judge agreement: 0.7/i)).toBeInTheDocument();
    expect(screen.getByText(/Recommended decision: continue experiment/i)).toBeInTheDocument();
    expect(screen.queryByText(/Win rate \(keyword\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Win rate \(robust\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Judge consensus/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Decision action/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Evidence version/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Posterior/i)).not.toBeInTheDocument();
  });
});
