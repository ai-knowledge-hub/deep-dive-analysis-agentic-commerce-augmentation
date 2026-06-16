import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { SimulationPanel } from "./SimulationPanel";

const baseProps = {
  products: [],
  canRun: true,
  canOptimize: false,
  canRetest: false,
  onRun: vi.fn(),
  onOptimize: vi.fn(),
  onRetest: vi.fn(),
  onSelectProduct: vi.fn(),
};

describe("SimulationPanel", () => {
  it("uses readable wording for connected evidence source", () => {
    render(
      <SimulationPanel
        {...baseProps}
        sourceSessionId="session-12345678"
        scenarioValue="Find waterproof trail shoes."
      />,
    );

    expect(screen.getByText(/Scenario filled from connected evidence/i)).toBeInTheDocument();
    expect(screen.queryByText(/sourced from session/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/session-12345678/i)).not.toBeInTheDocument();
  });

  it("shows product names in score details instead of raw product ids", async () => {
    const user = userEvent.setup();
    render(
      <SimulationPanel
        {...baseProps}
        products={[
          { id: "prod-1", name: "Everyday Pack", description: "Daily carry" },
          { id: "prod-2", name: "Travel Pack", description: "Trip carry" },
        ]}
        run={{
          run_id: "sim-1",
          result: {
            winner_id: "prod-1",
            scores: [
              { product_id: "prod-1", score: 0.82 },
              { product_id: "prod-2", score: 0.64 },
            ],
          },
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /See all product scores/i }));
    const dialog = screen.getByRole("dialog");

    expect(within(dialog).getByText(/Everyday Pack/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/Travel Pack/i)).toBeInTheDocument();
    expect(within(dialog).queryByText(/^prod-1$/i)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/^prod-2$/i)).not.toBeInTheDocument();
  });

  it("shows product names in lift summary instead of raw winner ids", () => {
    render(
      <SimulationPanel
        {...baseProps}
        products={[
          { id: "prod-1", name: "Everyday Pack", description: "Daily carry" },
          { id: "prod-2", name: "Travel Pack", description: "Trip carry" },
        ]}
        run={{
          run_id: "sim-1",
          result: {
            winner_id: "prod-1",
            scores: [{ product_id: "prod-1", score: 0.7 }],
          },
        }}
        optimized={{
          run_id: "sim-1",
          optimized: {
            id: "prod-1",
            before: "Original copy",
            after: "Improved copy",
          },
        }}
        retest={{
          run_id: "sim-1",
          result: {
            winner_id: "prod-2",
            scores: [
              { product_id: "prod-1", score: 0.75 },
              { product_id: "prod-2", score: 0.8 },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText(/Winner before/i).nextSibling).toHaveTextContent("Everyday Pack");
    expect(screen.getByText(/Winner after/i).nextSibling).toHaveTextContent("Travel Pack");
    expect(screen.queryByText(/^prod-1$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^prod-2$/i)).not.toBeInTheDocument();
  });
});
