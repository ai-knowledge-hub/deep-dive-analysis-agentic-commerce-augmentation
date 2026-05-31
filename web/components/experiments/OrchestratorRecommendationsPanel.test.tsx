import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { OrchestratorRecommendationsPanel } from "./OrchestratorRecommendationsPanel";

describe("OrchestratorRecommendationsPanel", () => {
  it("shows readable recommendation action labels", () => {
    render(
      <OrchestratorRecommendationsPanel
        open
        recommendations={[
          {
            id: "rec-1",
            experiment_id: "exp-1",
            recommendation: {
              experiment_id: "exp-1",
              action: "run_variant",
              reason: "Run the strongest candidate.",
              variant_id: "variant-1",
            },
            created_at: "2026-03-18T10:00:00Z",
          },
        ]}
        runningVariantId={null}
        canRunVariantTests
        isSubmitting={false}
        isCreatingSuggestedVariant={false}
        onOpenChange={vi.fn()}
        onRunRecommendation={vi.fn()}
        onCreateVariantFromRecommendation={vi.fn()}
      />,
    );

    expect(screen.getByText(/run variant/i)).toBeInTheDocument();
    expect(screen.queryByText(/run_variant/i)).not.toBeInTheDocument();
  });
});
