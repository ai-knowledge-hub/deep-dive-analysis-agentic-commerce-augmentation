import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { ExperimentOutcomeReview } from "./ExperimentOutcomeReview";

describe("ExperimentOutcomeReview", () => {
  it("uses readable confidence and evidence labels", () => {
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
          decision_action: "continue",
        }}
        experimentGapSummary={null}
        renderMetricValue={(value) => String(value)}
      />,
    );

    expect(screen.getByText(/Evidence version: 4/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence: 0.81/i)).toBeInTheDocument();
    expect(screen.queryByText(/Snapshot version/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Posterior/i)).not.toBeInTheDocument();
  });
});
