import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { FlowStatusPanel } from "./FlowStatusPanel";

describe("FlowStatusPanel", () => {
  it("renders readable flow step labels", () => {
    render(
      <FlowStatusPanel
        labMode="manual"
        currentFlowStep={6}
        activeFlowSteps={[
          { id: 6, label: "Experiment run completed", done: false },
          { id: 7, label: "Validation completed", done: false },
        ]}
        labLoopSteps={[]}
        lastRun={null}
        latestBelief={null}
        latestBeliefSummary="No beliefs yet"
        nextFlowAction={{
          label: "Complete experiment run",
          helper: "Run the selected variant before validation.",
        }}
        showValidationCheckpoint={false}
        onOpenBeliefsTimeline={vi.fn()}
        onUseLatestBelief={vi.fn()}
        onRunNextFlowAction={vi.fn()}
        onOpenValidation={vi.fn()}
      />,
    );

    expect(screen.getByText(/Experiment run completed/i)).toBeInTheDocument();
    expect(screen.queryByText(/experiment_run_completed/i)).not.toBeInTheDocument();
  });

  it("uses variant labels instead of raw variant ids for the last run", () => {
    render(
      <FlowStatusPanel
        labMode="manual"
        currentFlowStep={6}
        activeFlowSteps={[]}
        labLoopSteps={[]}
        lastRun={{
          id: "run-1",
          experiment_id: "exp-1",
          variant_id: "variant-raw-123456",
          query_id: "query-1",
          created_at: "2026-05-31T10:00:00Z",
        }}
        variantLabelById={new Map([["variant-raw-123456", "Homepage benefit copy"]])}
        latestBelief={null}
        latestBeliefSummary="No beliefs yet"
        nextFlowAction={{
          label: "Complete experiment run",
          helper: "Run the selected variant before validation.",
        }}
        showValidationCheckpoint={false}
        onOpenBeliefsTimeline={vi.fn()}
        onUseLatestBelief={vi.fn()}
        onRunNextFlowAction={vi.fn()}
        onOpenValidation={vi.fn()}
      />,
    );

    expect(screen.getByText(/Variant: Homepage benefit copy/i)).toBeInTheDocument();
    expect(screen.queryByText(/variant-raw-123456/i)).not.toBeInTheDocument();
  });

  it("uses a readable fallback when the last run variant label is missing", () => {
    render(
      <FlowStatusPanel
        labMode="manual"
        currentFlowStep={6}
        activeFlowSteps={[]}
        labLoopSteps={[]}
        lastRun={{
          id: "run-1",
          experiment_id: "exp-1",
          variant_id: "variant-raw-123456",
          query_id: "query-1",
          created_at: "2026-05-31T10:00:00Z",
        }}
        variantLabelById={new Map()}
        latestBelief={null}
        latestBeliefSummary="No beliefs yet"
        nextFlowAction={{
          label: "Complete experiment run",
          helper: "Run the selected variant before validation.",
        }}
        showValidationCheckpoint={false}
        onOpenBeliefsTimeline={vi.fn()}
        onUseLatestBelief={vi.fn()}
        onRunNextFlowAction={vi.fn()}
        onOpenValidation={vi.fn()}
      />,
    );

    expect(screen.getByText(/Variant: Selected variant/i)).toBeInTheDocument();
    expect(screen.queryByText(/variant-raw-123456/i)).not.toBeInTheDocument();
  });
});
