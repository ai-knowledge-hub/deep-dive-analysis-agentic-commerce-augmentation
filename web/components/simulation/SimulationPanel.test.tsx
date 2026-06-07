import { render, screen } from "@testing-library/react";
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
});
