import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { ExecutionControlsSummary } from "./ExecutionControlsSummary";

describe("ExecutionControlsSummary", () => {
  it("uses readable execution state and mode labels", () => {
    render(
      <ExecutionControlsSummary
        selectedRun={{
          id: "run-1",
          client_id: "client-1",
          experiment_id: "exp-1",
          status: "running",
          state: "retrieval_snapshots_ready",
          requires_approval: true,
          run_mode: "auto_execute_safe",
        }}
        flowSteps={[
          {
            id: "retrieval_snapshots_ready",
            label: "Evidence saved",
            status: "Current",
            className: "is-current",
          },
          {
            id: "hypotheses_ready",
            label: "Test ideas ready",
            status: "Pending",
            className: "",
          },
          {
            id: "posterior_updated",
            label: "Confidence updated",
            status: "Pending",
            className: "",
          },
        ]}
      />,
    );

    expect(screen.getByText(/Current: Evidence saved/i)).toBeInTheDocument();
    expect(screen.getByText(/Mode: auto execute safe/i)).toBeInTheDocument();
    expect(screen.getByText(/Test ideas ready/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence updated/i)).toBeInTheDocument();
    expect(screen.queryByText(/retrieval_snapshots_ready/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/hypotheses_ready/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/posterior_updated/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/auto_execute_safe/i)).not.toBeInTheDocument();
  });
});
