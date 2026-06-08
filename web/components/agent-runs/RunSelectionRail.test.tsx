import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { RunSelectionRail } from "./RunSelectionRail";

describe("RunSelectionRail", () => {
  it("uses readable run labels and state labels", () => {
    render(
      <RunSelectionRail
        runs={[
          {
            id: "run-1",
            experiment_id: "exp-12345678",
            status: "running",
            state: "variants_ready",
            requires_approval: false,
            created_at: "2026-01-02T00:00:00Z",
          },
          {
            id: "run-2",
            experiment_id: "exp-87654321",
            status: "running",
            state: "variants_ready",
            requires_approval: false,
            created_at: "2026-01-03T00:00:00Z",
          },
        ]}
        selectedRunId="run-1"
        runCounters={{
          total: 2,
          running: 2,
          planned: 0,
          failed: 0,
          completed: 0,
          approvals: 0,
        }}
        onSelectRun={vi.fn()}
      />,
    );

    expect(screen.getAllByText(/Experiment run · started/i)).toHaveLength(2);
    expect(screen.getByText(/started 1\/2\/2026/i)).toBeInTheDocument();
    expect(screen.getByText(/started 1\/3\/2026/i)).toBeInTheDocument();
    expect(screen.getAllByText(/running · variants ready/i)).toHaveLength(2);
    expect(screen.getByText(/Summary/i)).toBeInTheDocument();
    expect(screen.queryByText(/exp-12345678/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/exp-87654321/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/run-1/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/run-2/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/variants_ready/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Snapshot/i)).not.toBeInTheDocument();
  });
});
