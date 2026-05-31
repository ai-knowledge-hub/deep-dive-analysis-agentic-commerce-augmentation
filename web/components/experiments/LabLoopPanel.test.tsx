import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { LabLoopPanel } from "./LabLoopPanel";

describe("LabLoopPanel", () => {
  it("uses test idea wording in lab automation copy", () => {
    render(
      <LabLoopPanel
        labMode="lab"
        selectedExperimentId="exp-1"
        batteryLinked
        variantCount={2}
        runCount={0}
        metricCount={0}
        beliefCount={0}
        labAutoRunEnabled={false}
        showManualControls={false}
        currentFlowStep={1}
        activeFlowSteps={[]}
        labLoopSteps={[]}
        lastRun={null}
        variantLabelById={new Map()}
        latestBelief={null}
        latestBeliefSummary="No beliefs yet"
        nextFlowAction={{
          label: "Save evidence set",
          helper: "Run the baseline or control variant.",
        }}
        showValidationCheckpoint={false}
        onLabAutoRunEnabledChange={vi.fn()}
        onShowManualControlsChange={vi.fn()}
        onSwitchToManual={vi.fn()}
        onOpenBeliefsTimeline={vi.fn()}
        onUseLatestBelief={vi.fn()}
        onRunNextFlowAction={vi.fn()}
        onOpenValidation={vi.fn()}
      />,
    );

    expect(screen.getByText(/baseline\/test-idea variants/i)).toBeInTheDocument();
    expect(screen.getByText(/Auto-run baseline \+ test idea/i)).toBeInTheDocument();
    expect(screen.queryByText(/baseline\/hypothesis/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/baseline \+ hypothesis/i)).not.toBeInTheDocument();
  });
});
