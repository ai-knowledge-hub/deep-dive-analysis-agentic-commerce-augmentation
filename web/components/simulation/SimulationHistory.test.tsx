import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { SimulationHistory } from "./SimulationHistory";

describe("SimulationHistory", () => {
  it("shows readable product names instead of raw product ids", () => {
    render(
      <SimulationHistory
        runs={[
          {
            id: "sim-1",
            query: "Find the best commuter backpack",
            winner_id: "prod-1",
            product_id: "prod-2",
            created_at: "2026-01-02T00:00:00Z",
          },
        ]}
        productLabels={{
          "prod-1": "Everyday Pack",
          "prod-2": "Travel Pack",
        }}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText(/Winner: Everyday Pack/i)).toBeInTheDocument();
    expect(screen.getByText(/Linked product: Travel Pack/i)).toBeInTheDocument();
    expect(screen.queryByText(/prod-1/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/prod-2/i)).not.toBeInTheDocument();
  });

  it("uses a readable fallback for products outside the current list", () => {
    render(
      <SimulationHistory
        runs={[
          {
            id: "sim-2",
            query: "Compare premium running shoes",
            winner_id: "prod-archived",
            product_id: "prod-archived",
          },
        ]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getAllByText(/Product not in current list/i)).toHaveLength(2);
    expect(screen.queryByText(/prod-archived/i)).not.toBeInTheDocument();
  });
});
