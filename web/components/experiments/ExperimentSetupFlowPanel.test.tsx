import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ExperimentSetupFlowPanel } from "./ExperimentSetupFlowPanel";

describe("ExperimentSetupFlowPanel", () => {
  it("uses readable setup status labels", () => {
    render(
      <ExperimentSetupFlowPanel
        labMode="lab"
        collapsed
        hasProduct
        protocolSnapshotVersion={3}
        hypothesesReady
        onCollapsedChange={vi.fn()}
      >
        <div>Setup controls</div>
      </ExperimentSetupFlowPanel>,
    );

    expect(screen.getByText(/Evidence set:/i)).toBeInTheDocument();
    expect(screen.getByText(/Test ideas: ready/i)).toBeInTheDocument();
    expect(screen.queryByText(/Evidence protocol/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Protocol snapshot/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Hypotheses/i)).not.toBeInTheDocument();
  });

  it("exposes a focus target for setup shortcuts", () => {
    const ref = React.createRef<HTMLElement>();
    render(
      <ExperimentSetupFlowPanel
        ref={ref}
        labMode="lab"
        collapsed
        hasProduct
        protocolSnapshotVersion={3}
        hypothesesReady
        onCollapsedChange={vi.fn()}
      >
        <div>Setup controls</div>
      </ExperimentSetupFlowPanel>,
    );

    ref.current?.focus();

    expect(screen.getByLabelText(/Experiment setup/i)).toHaveFocus();
  });
});
