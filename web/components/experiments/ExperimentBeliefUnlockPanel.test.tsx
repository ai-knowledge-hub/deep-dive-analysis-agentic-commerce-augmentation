import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ExperimentBeliefUnlockPanel } from "./ExperimentBeliefUnlockPanel";

describe("ExperimentBeliefUnlockPanel", () => {
  it("exposes a focus target for insights shortcuts", () => {
    const ref = React.createRef<HTMLElement>();

    render(
      <ExperimentBeliefUnlockPanel
        ref={ref}
        brandId="brand-1"
        validationSummary={{
          total_logged: 0,
          verified_runs: 0,
          correct_runs: 0,
          accuracy: 0,
          unlock_ready: false,
          progress: 0.4,
          accuracy_target: 0.8,
        }}
        viewMode="list"
        onViewModeChange={vi.fn()}
        onUseBelief={vi.fn()}
      />,
    );

    ref.current?.focus();

    expect(screen.getByLabelText(/Experiment insights/i)).toHaveFocus();
  });
});
