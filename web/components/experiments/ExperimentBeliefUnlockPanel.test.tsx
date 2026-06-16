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
        validationSummary={{ unlock_ready: false, progress: 0.4 }}
        viewMode="list"
        onViewModeChange={vi.fn()}
        onUseBelief={vi.fn()}
      />,
    );

    ref.current?.focus();

    expect(screen.getByLabelText(/Experiment insights/i)).toHaveFocus();
  });
});
