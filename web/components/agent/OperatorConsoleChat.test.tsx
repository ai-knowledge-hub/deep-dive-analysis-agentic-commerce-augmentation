import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it } from "vitest";

import { OperatorConsoleChat } from "./OperatorConsoleChat";

describe("OperatorConsoleChat", () => {
  it("surfaces richer run context and explains the selected action with policy detail", async () => {
    const user = userEvent.setup();

    render(
      <OperatorConsoleChat
        run={{
          id: "run-1",
          experiment_id: "exp-12345678",
          status: "planned",
          state: "variants_ready",
          run_mode: "auto_execute_safe",
        }}
        actions={[
          {
            id: "action-1",
            agent_run_id: "run-1",
            sequence: 1,
            status: "proposed",
            capability_name: "publish_copy_revision",
            rationale: "Winning evidence is strong enough to publish.",
          },
          {
            id: "action-2",
            agent_run_id: "run-1",
            sequence: 2,
            status: "approved",
            capability_name: "run_variant",
          },
        ]}
        events={[
          {
            id: "event-1",
            run_id: "run-1",
            sequence: 1,
            event_type: "policy",
            status: "failed",
            capability_name: "publish_copy_revision",
            note: "Policy blocked publishing until legal review is complete.",
            is_policy_event: true,
            timestamp: "2026-03-24T10:00:00Z",
          },
        ]}
        selectedAction={{
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 1,
          status: "proposed",
          capability_name: "publish_copy_revision",
          rationale: "Winning evidence is strong enough to publish.",
        }}
        nextRecommendedAction={{
          action: {
            id: "action-1",
            agent_run_id: "run-1",
            sequence: 1,
            status: "proposed",
            capability_name: "publish_copy_revision",
            rationale: "Winning evidence is strong enough to publish.",
          },
          guardrails: ["Legal review is required before publishing."],
          hint: "Wait for legal sign-off before approval.",
        }}
      />,
    );

    expect(screen.getByText(/Selection: publish_copy_revision/i)).toBeInTheDocument();
    expect(screen.getByText(/Policy: 1/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Explain selected action/i }));

    expect(
      screen.getByText(/Latest policy note: Policy blocked publishing until legal review is complete\./i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Risk profile is high risk\./i)).toBeInTheDocument();
  });
});
