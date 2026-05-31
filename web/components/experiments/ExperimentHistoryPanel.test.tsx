import React, { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExperimentHistoryPanel } from "./ExperimentHistoryPanel";

describe("ExperimentHistoryPanel", () => {
  it("uses readable variant and simulation labels in run history", () => {
    render(
      <ExperimentHistoryPanel
        experiments={[]}
        runs={[
          {
            id: "run-1",
            experiment_id: "exp-1",
            variant_id: "variant-raw-123456",
            query_id: "query-1",
            simulation_run_id: "simulation-run-abcdef123456",
            snapshot_version: 3,
            hypothesis_id: "hypothesis-1",
          },
        ]}
        metricsCount={0}
        variantCount={1}
        historyCollapsed={false}
        selectedExperimentId={null}
        experimentSnapshots={{}}
        batteries={[]}
        savingExperimentId={null}
        queryMap={new Map([["query-1", "Best trail shoes"]])}
        variantLabelById={new Map([["variant-raw-123456", "Homepage benefit copy"]])}
        runGapDetails={new Map()}
        hypothesisLabelById={new Map([["hypothesis-1", "Price clarity test"]])}
        hypothesisStatementById={new Map()}
        expandedHypothesisId={null}
        runsSectionRef={createRef<HTMLDivElement>()}
        formatTimestamp={(value) => value ?? "Not set"}
        onToggleHistory={vi.fn()}
        onSelectExperiment={vi.fn()}
        onSaveExperimentDraft={vi.fn()}
        onScrollVariants={vi.fn()}
        onScrollRuns={vi.fn()}
        onScrollMetrics={vi.fn()}
        onToggleHypothesis={vi.fn()}
        onDeleteRun={vi.fn()}
      />,
    );

    expect(screen.getByText(/Variant: Homepage benefit copy/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open linked simulation/i })).toBeInTheDocument();
    expect(screen.getByText(/Ref: abcdef12/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence version: v3/i)).toBeInTheDocument();
    expect(screen.getByText(/Test idea: Price clarity test/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View test idea details/i })).toBeInTheDocument();
    expect(screen.queryByText(/variant-raw-123456/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/simulation-run-abcdef123456/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Snapshot:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Hypothesis:/i)).not.toBeInTheDocument();
  });
});
