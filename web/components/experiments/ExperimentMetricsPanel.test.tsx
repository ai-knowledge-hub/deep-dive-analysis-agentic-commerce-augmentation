import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ExperimentMetricsPanel } from "./ExperimentMetricsPanel";

describe("ExperimentMetricsPanel", () => {
  it("exposes a focus target for metrics shortcuts", () => {
    const ref = React.createRef<HTMLElement>();

    render(
      <ExperimentMetricsPanel
        ref={ref}
        metricsHistory={[]}
        recentMetrics={[]}
        variants={[]}
        metricsTrend={[]}
        metricsTrendMetric="win_rate"
        metricsHistoryExpanded={false}
        renderMetricValue={(value, fallback = "—") =>
          value === undefined || value === null ? fallback : String(value)
        }
        onTrendMetricChange={vi.fn()}
        onHistoryExpandedChange={vi.fn()}
        onOpenOverview={vi.fn()}
      />,
    );

    ref.current?.focus();

    expect(screen.getByLabelText(/Experiment metrics/i)).toHaveFocus();
  });
});
