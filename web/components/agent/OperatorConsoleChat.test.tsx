import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

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

  it("exposes structured navigation actions for approvals, policy, and next action", async () => {
    const user = userEvent.setup();
    const onFocusApprovals = vi.fn();
    const onFocusPolicy = vi.fn();
    const onFocusValidationLinked = vi.fn();
    const onJumpToNextAction = vi.fn();
    const onOpenInterventionsForRun = vi.fn();
    const onOpenExperiment = vi.fn();

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
            validation_job_id: "job-1",
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
        }}
        nextRecommendedAction={{
          action: {
            id: "action-1",
            agent_run_id: "run-1",
            sequence: 1,
            status: "proposed",
            capability_name: "publish_copy_revision",
          },
          guardrails: [],
          hint: "Approve once legal review is complete.",
        }}
        onFocusApprovals={onFocusApprovals}
        onFocusPolicy={onFocusPolicy}
        onFocusValidationLinked={onFocusValidationLinked}
        onJumpToNextAction={onJumpToNextAction}
        onOpenInterventionsForRun={onOpenInterventionsForRun}
        onOpenExperiment={onOpenExperiment}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Focus approvals/i }));
    expect(onFocusApprovals).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /Focus policy events/i }));
    expect(onFocusPolicy).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /Jump to next action/i }));
    expect(onJumpToNextAction).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /Focus validation-linked/i }));
    expect(onFocusValidationLinked).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /Open interventions/i }));
    expect(onOpenInterventionsForRun).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /Open experiment context/i }));
    expect(onOpenExperiment).toHaveBeenCalledTimes(1);
  });

  it("issues state-changing operator commands with action context", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue(undefined);

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
          },
        ]}
        events={[]}
        selectedAction={{
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 1,
          status: "proposed",
          capability_name: "publish_copy_revision",
        }}
        nextRecommendedAction={{
          action: null,
          guardrails: [],
          hint: "No next action.",
        }}
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Approve selected/i }));

    expect(onIssueCommand).toHaveBeenCalledWith({
      command_type: "approve",
      action_id: "action-1",
      message: "Approve publish_copy_revision",
    });
    expect(await screen.findByText(/Command receipt recorded: approve/i)).toBeInTheDocument();
  });
});
