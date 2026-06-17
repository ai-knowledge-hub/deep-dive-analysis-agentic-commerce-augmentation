import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { EvidencePanel } from "./EvidencePanel";

describe("EvidencePanel", () => {
  it("uses readable empty-state wording", () => {
    render(<EvidencePanel analysis={null} />);

    expect(screen.getByText(/No evidence yet/i)).toBeInTheDocument();
    expect(screen.getByText(/collect product evidence/i)).toBeInTheDocument();
    expect(screen.queryByText(/No Evidence Data/i)).not.toBeInTheDocument();
  });

  it("uses summary wording for evidence outcomes and diagnostics", () => {
    render(
      <EvidencePanel
        analysis={{
          intent: { label: "best trail shoes", confidence: 0.8 },
          goals: ["clear waterproof protection"],
          evidence_products: [
            {
              id: "product-1",
              name: "Trail shoe",
              description: "Waterproof trail shoe",
              source: "search",
              confidence: 0.9,
            },
          ],
          profiles: [],
          alignment_scores: [
            {
              product_id: "product-1",
              score: 0.74,
              matched_capabilities: ["waterproof protection"],
              alignment_reasoning: "Strong match for weather protection.",
            },
          ],
        }}
        signalExtraction={{
          intent_signals: ["clear waterproof protection"],
          winner_signals: ["waterproof protection"],
          missing_signals: ["fast delivery"],
        }}
        targetProductId="product-1"
        targetProductName="Trail shoe"
        targetProductCopy="Waterproof trail shoe for rough paths."
        sourceSessionId="session-12345678"
      />,
    );

    expect(screen.getByText(/Outcome summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence source: connected chat/i)).toBeInTheDocument();
    expect(screen.queryByText(/Source session/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/session-12345678/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Outcome snapshot/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Step 2 .* Explanation/i }));

    expect(screen.getByText(/Your copy summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Alignment score distribution/i)).toBeInTheDocument();
    expect(screen.getByText(/Intent and goal signals/i)).toBeInTheDocument();
    expect(screen.queryByText(/Our copy snapshot/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Intent\/Goal signals/i)).not.toBeInTheDocument();
  });

  it("routes the fresh-evidence action to chat instead of simulation", () => {
    const onOpenChat = vi.fn();
    const onOpenSimulation = vi.fn();

    render(
      <EvidencePanel
        analysis={{
          intent: { label: "best trail shoes", confidence: 0.8 },
          goals: ["clear waterproof protection"],
          evidence_products: [],
          profiles: [],
          alignment_scores: [],
        }}
        onOpenChat={onOpenChat}
        onOpenSimulation={onOpenSimulation}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Open chat for fresh evidence/i }));

    expect(onOpenChat).toHaveBeenCalledTimes(1);
    expect(onOpenSimulation).not.toHaveBeenCalled();
  });
});
