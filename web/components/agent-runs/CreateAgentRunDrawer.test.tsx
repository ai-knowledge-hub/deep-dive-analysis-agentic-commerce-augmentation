import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { CreateAgentRunDrawer, type CreateAgentRunForm } from "./CreateAgentRunDrawer";

const baseForm: CreateAgentRunForm = {
  experiment_id: "",
  requires_approval: true,
  run_mode: "plan_only",
  allowed_capabilities: ["request_synthetic_validation", "create_variant"],
  objective: {
    objective: "weighted_combo_confidence",
    weights: { exp: 0.55, syn: 0.35, obs: 0.1 },
  },
  budgets: {
    max_actions: 25,
    max_cost_usd: 5,
  },
  approval_policy: {
    require_approval_for: ["publish", "promote_prod"],
  },
};

describe("CreateAgentRunDrawer", () => {
  it("uses operator language for run setup fields", () => {
    render(
      <CreateAgentRunDrawer
        open
        experiments={[]}
        form={baseForm}
        loading={false}
        canCreate
        onClose={vi.fn()}
        onFormChange={vi.fn()}
        onCreate={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/Run objective/i)).toBeInTheDocument();
    expect(screen.getByText(/Advanced run setup/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Allowed actions/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Budget limits/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Approval rules/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Optional controls for allowed actions, budget limits, and approval rules/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Objective \(JSON\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Budgets \(JSON\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Approval policy \(JSON\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Allowed capabilities/i)).not.toBeInTheDocument();
  });

  it("keeps structured run settings editable without changing invalid drafts", () => {
    const onFormChange = vi.fn();
    render(
      <CreateAgentRunDrawer
        open
        experiments={[]}
        form={baseForm}
        loading={false}
        canCreate
        onClose={vi.fn()}
        onFormChange={onFormChange}
        onCreate={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Run objective/i), {
      target: { value: "not ready yet" },
    });
    expect(onFormChange).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Run objective/i), {
      target: { value: '{"objective":"maximize confidence"}' },
    });
    expect(onFormChange).toHaveBeenCalledWith({
      objective: { objective: "maximize confidence" },
    });
  });
});
