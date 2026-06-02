import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ExperimentVariantRunItem } from "./ExperimentVariantRunItem";

describe("ExperimentVariantRunItem", () => {
  it("uses confidence wording for metric output", () => {
    render(
      <ExperimentVariantRunItem
        variant={{
          id: "variant-1",
          experiment_id: "exp-1",
          label: "Homepage benefit copy",
          type: "copy",
        }}
        tested
        hypothesisLabel="Test idea 1"
        hypothesisStatement={null}
        hypothesisExpanded={false}
        copyExpanded={false}
        resolvedDescription={null}
        metricValues={{
          win_rate: 0.6,
          total_runs: 5,
          posterior: 0.74,
          decision_action: "continue",
        }}
        runButtonProminent={false}
        running={false}
        canRun
        renderMetricValue={(value) => String(value)}
        onToggleHypothesis={vi.fn()}
        onToggleCopy={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(screen.getByText(/Confidence: 0.74/i)).toBeInTheDocument();
    expect(screen.queryByText(/Posterior/i)).not.toBeInTheDocument();
  });

  it("uses test idea wording for linked variant details", () => {
    render(
      <ExperimentVariantRunItem
        variant={{
          id: "variant-1",
          experiment_id: "exp-1",
          label: "Homepage benefit copy",
          type: "copy",
          hypothesis_id: "hypothesis-1",
        }}
        tested={false}
        hypothesisLabel="Price clarity test"
        hypothesisStatement={{ if: "Price clarity improves trust" }}
        hypothesisExpanded={false}
        copyExpanded={false}
        resolvedDescription="Clear pricing copy"
        metricValues={null}
        runButtonProminent={false}
        running={false}
        canRun
        renderMetricValue={(value) => String(value)}
        onToggleHypothesis={vi.fn()}
        onToggleCopy={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /View test idea details/i })).toBeInTheDocument();
    expect(screen.queryByText(/hypothesis details/i)).not.toBeInTheDocument();
  });

  it("uses tested copy wording when a variant has no copy details", () => {
    render(
      <ExperimentVariantRunItem
        variant={{
          id: "variant-1",
          experiment_id: "exp-1",
          label: "Homepage benefit copy",
          type: "copy",
        }}
        tested={false}
        hypothesisLabel={null}
        hypothesisStatement={null}
        hypothesisExpanded={false}
        copyExpanded={false}
        resolvedDescription={null}
        metricValues={null}
        runButtonProminent={false}
        running={false}
        canRun
        renderMetricValue={(value) => String(value)}
        onToggleHypothesis={vi.fn()}
        onToggleCopy={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(screen.getByText(/No tested copy yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/No copy payload yet/i)).not.toBeInTheDocument();
  });
});
