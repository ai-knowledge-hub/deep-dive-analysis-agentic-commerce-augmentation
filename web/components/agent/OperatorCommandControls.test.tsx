import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { OperatorCommandControls } from "./OperatorCommandControls";

describe("OperatorCommandControls", () => {
  it("keeps recovery commands primary and routes skill/template detail behind advanced controls", () => {
    render(
      <OperatorCommandControls
        run={{ id: "run-1", client_id: "client-1", status: "failed", state: "failed" }}
        selectedAction={{
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 1,
          status: "failed",
          capability_name: "run_variant",
        }}
        recoveryCapabilities={["review_validation_readiness"]}
        activeRecoveryCapability="review_validation_readiness"
        recoverySkillOptions={[
          {
            id: "request-validation-and-ingest-result",
            name: "Request Validation And Ingest Result",
            description: "Request validation and ingest the result.",
            version: "v1",
            tool_ids: ["validation.request_synthetic"],
            risk_class: "external_side_effect",
          },
        ]}
        activeRecoverySkill="request-validation-and-ingest-result"
        activeRecoveryTemplate={{
          id: "recovery.review_validation_readiness",
          capability_name: "review_validation_readiness",
          summary: "Re-check readiness gates before creating more recovery work.",
          default_inputs: { reason: "failed_run" },
        }}
        recoverySkillMetadata={{ skill_id: "request-validation-and-ingest-result" }}
        onRecoveryCapabilityChange={vi.fn()}
        onRecoverySkillChange={vi.fn()}
        onIssueCommand={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /Retry selected/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Recovery action/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Change plan/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Recovery target action/i)).toBeInTheDocument();
    expect(screen.getByText(/Advanced recovery routing/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Preferred recovery skill/i)).not.toBeNull();
    expect(screen.queryByText(/Recovery template:/i)).toBeInTheDocument();
    expect(screen.getByText(/Suggested inputs:/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Recovery target capability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Defaults:/i)).not.toBeInTheDocument();
  });

  it("uses readable empty recovery action wording", () => {
    render(
      <OperatorCommandControls
        run={{ id: "run-1", client_id: "client-1", status: "failed", state: "failed" }}
        selectedAction={null}
        recoveryCapabilities={[]}
        activeRecoveryCapability=""
        recoverySkillOptions={[]}
        activeRecoverySkill=""
        activeRecoveryTemplate={null}
        recoverySkillMetadata={{}}
        onRecoveryCapabilityChange={vi.fn()}
        onRecoverySkillChange={vi.fn()}
        onIssueCommand={vi.fn()}
      />,
    );

    expect(screen.getByText(/No recovery actions available/i)).toBeInTheDocument();
    expect(screen.queryByText(/No allowed capabilities/i)).not.toBeInTheDocument();
  });
});
