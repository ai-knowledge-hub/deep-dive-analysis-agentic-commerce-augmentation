import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { SelectedActionDetailPanel } from "./SelectedActionDetailPanel";

describe("SelectedActionDetailPanel", () => {
  it("explains action diffs without payload wording", () => {
    render(
      <SelectedActionDetailPanel
        selectedAction={{
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 2,
          status: "executed",
          capability_name: "run_variant",
          rationale: "Run the selected variant.",
          variant_id: "variant-12345678",
          validation_job_id: "validation-job-12345678",
          inputs: {},
          outputs: { metric_id: "metric-12345678" },
        }}
        selectedCapabilitySpec={null}
        ownershipForm={{ owner_principal_id: "", steward_team: "" }}
        ownershipPreflight={null}
        ownershipBusy={false}
        ownershipNotice={null}
        actionDiffs={{
          previousAction: null,
          previousSameCapability: null,
          vsPreviousAction: {
            added: ["metric_id"],
            changed: [],
            removed: [],
          },
          vsPreviousCapability: {
            added: [],
            changed: ["score"],
            removed: [],
          },
        }}
        shortKeyList={(keys) => (keys.length ? keys.join(", ") : "None")}
        onOwnershipFormChange={vi.fn()}
        onClearOwnershipPreflight={vi.fn()}
        onSubmitRegistryOwnership={vi.fn()}
        onOpenExperimentArtifact={vi.fn()}
        onOpenValidationArtifact={vi.fn()}
        onOpenDetailedDiff={vi.fn()}
      />,
    );

    expect(screen.getByText(/changed result fields/i)).toBeInTheDocument();
    expect(screen.getByText("Linked work")).toBeInTheDocument();
    expect(screen.getByText(/Change preview/i)).toBeInTheDocument();
    expect(screen.getByText(/vs previous similar action/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open change details/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open variant/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open validation result/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open metric/i })).toBeInTheDocument();
    expect(screen.queryByText(/Linked artifacts/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Artifact diff preview/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/previous same capability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/output payload keys/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Variant: variant/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Validation job:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Metric: metric/i)).not.toBeInTheDocument();
  });
});
