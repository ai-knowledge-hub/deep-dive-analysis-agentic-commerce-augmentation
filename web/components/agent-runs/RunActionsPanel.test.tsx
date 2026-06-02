import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { RunActionsPanel } from "./RunActionsPanel";

const baseBudgetTelemetry = {
  maxActions: 10,
  maxVariantRuns: 3,
  maxCostUsd: 5,
  executedActions: 1,
  executedVariantRuns: 0,
  totalCostUsd: 0.5,
  actionPct: 10,
  variantPct: 0,
  costPct: 10,
};

const baseBudgetState = {
  actionSeverity: "ok" as const,
  variantSeverity: "ok" as const,
  costSeverity: "ok" as const,
  actionBlocked: false,
  variantBlocked: false,
  costBlocked: false,
};

describe("RunActionsPanel", () => {
  it("keeps action decisions primary and hides technical detail behind disclosures", () => {
    render(
      <RunActionsPanel
        actions={[
          {
            id: "action-1",
            sequence: 1,
            status: "proposed",
            capability_name: "run_variant",
            capability_version: "v1",
            rationale: "Run the next variant against saved evidence.",
            inputs: {},
            outputs: {},
            skill_id: "optimize-product-representation",
            tool_id: "experiment.run_variant",
          },
        ]}
        selectedAction={null}
        actionCounters={{
          proposed: 1,
          approved: 0,
          executing: 0,
          executed: 0,
          failed: 0,
        }}
        budgetTelemetry={baseBudgetTelemetry}
        budgetState={baseBudgetState}
        loading={false}
        getGuardrailReasonsForAction={() => []}
        onSelectAction={vi.fn()}
        onDecision={vi.fn()}
        formatJsonPreview={() => "{}"}
      />,
    );

    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Why")).toBeInTheDocument();
    expect(screen.getByText("Decision")).toBeInTheDocument();
    expect(screen.getByText(/Run the next variant/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByText(/Action health and budgets/i)).toBeInTheDocument();
    expect(screen.getByText(/Technical mapping/i)).toBeInTheDocument();
    expect(screen.queryByText("Capability")).not.toBeInTheDocument();
    expect(screen.queryByText("Rationale")).not.toBeInTheDocument();
    expect(screen.queryByText("Actions")).not.toBeInTheDocument();
  });

  it("uses action data wording for completed action exports", () => {
    render(
      <RunActionsPanel
        actions={[
          {
            id: "action-1",
            sequence: 1,
            status: "executed",
            capability_name: "run_variant",
            rationale: "Finished the saved test run.",
            inputs: { variant: "A" },
            outputs: { metric_id: "metric-1" },
          },
        ]}
        selectedAction={null}
        actionCounters={{
          proposed: 0,
          approved: 0,
          executing: 0,
          executed: 1,
          failed: 0,
        }}
        budgetTelemetry={baseBudgetTelemetry}
        budgetState={baseBudgetState}
        loading={false}
        getGuardrailReasonsForAction={() => []}
        onSelectAction={vi.fn()}
        onDecision={vi.fn()}
        formatJsonPreview={() => "{}"}
      />,
    );

    expect(screen.getByRole("button", { name: /Copy action data/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Copy payload/i })).not.toBeInTheDocument();
  });
});
