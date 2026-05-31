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
});
