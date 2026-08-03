import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { AgentOperatorModePanel } from "./AgentOperatorModePanel";

describe("AgentOperatorModePanel", () => {
  it("uses readable run state and mode labels", () => {
    render(
      <AgentOperatorModePanel
        latestAgentRun={{
          id: "run-1",
          client_id: "client-1",
          experiment_id: "exp-1",
          status: "running",
          state: "variants_ready",
          run_mode: "auto_execute_safe",
          requires_approval: true,
        }}
        hasSelectedExperiment
        onOpenRuns={vi.fn()}
      />,
    );

    expect(screen.getByText(/running · variants ready/i)).toBeInTheDocument();
    expect(screen.getByText(/auto execute safe/i)).toBeInTheDocument();
    expect(screen.getByText(/saved evidence, baseline-first, approvals/i)).toBeInTheDocument();
    expect(screen.queryByText(/variants_ready/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/auto_execute_safe/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/frozen snapshots/i)).not.toBeInTheDocument();
  });
});
