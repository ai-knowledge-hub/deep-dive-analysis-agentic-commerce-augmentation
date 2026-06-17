import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ExternalAgentJobPanel } from "./ExternalAgentJobPanel";

describe("ExternalAgentJobPanel", () => {
  it("uses readable submitting-agent wording", () => {
    render(
      <ExternalAgentJobPanel
        externalAgentJob={{
          job: {
            id: "job-1",
            principal_id: "agent.partner",
            requested_tool_id: "experiment.run_variant",
            requested_skill_id: "optimize-product-representation",
            status: "submitted",
          },
          run: {
            id: "run-1",
            status: "running",
            state: "variants_ready",
          },
          receipts: [],
          latest_receipt: null,
          verification: null,
        }}
        verificationBusy={false}
        loading={false}
        onVerifyReceipt={vi.fn()}
      />,
    );

    expect(screen.getByText(/Submitting agent/i)).toBeInTheDocument();
    expect(screen.queryByText(/Agent identity/i)).not.toBeInTheDocument();
  });
});
