import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { RunSelectionRail } from "./RunSelectionRail";

describe("RunSelectionRail", () => {
  it("uses readable run state labels", () => {
    render(
      <RunSelectionRail
        runs={[
          {
            id: "run-1",
            experiment_id: "exp-12345678",
            status: "running",
            state: "variants_ready",
            requires_approval: false,
          },
        ]}
        selectedRunId="run-1"
        runCounters={{
          total: 1,
          running: 1,
          planned: 0,
          failed: 0,
          completed: 0,
          approvals: 0,
        }}
        onSelectRun={vi.fn()}
      />,
    );

    expect(screen.getByText(/running · variants ready/i)).toBeInTheDocument();
    expect(screen.queryByText(/variants_ready/i)).not.toBeInTheDocument();
  });
});
