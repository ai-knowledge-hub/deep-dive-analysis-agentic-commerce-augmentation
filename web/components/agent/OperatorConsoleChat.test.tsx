import { render, screen, waitFor } from "@testing-library/react";
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

  it("requires a second confirmation after high-risk command preflight", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue(undefined);
    const onPreflightCommand = vi.fn().mockResolvedValue({
      allowed: true,
      command_type: "approve",
      risk_level: "high",
      requires_confirmation: true,
      requires_approval: true,
      effect_class: "write_high_risk",
      tool_id: "copy.publish_revision",
      skill_id: "promote-and-publish-approved-copy",
      side_effects: ["update_product_description"],
      blockers: [],
      warnings: ["This command may publish product copy."],
      rollback_guidance: "High-risk writes may need a compensating action.",
      summary: "Preflight passed with high risk.",
    });

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
        onPreflightCommand={onPreflightCommand}
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Approve selected/i }));

    expect(onPreflightCommand).toHaveBeenCalledTimes(1);
    expect(onIssueCommand).not.toHaveBeenCalled();
    expect(await screen.findByText(/Click the command again to confirm/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Approve selected/i }));

    await waitFor(() => expect(onIssueCommand).toHaveBeenCalledTimes(1));
  });

  it("issues retry as an explicit confirmed command for failed actions", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue(undefined);
    const onPreflightCommand = vi.fn().mockResolvedValue({
      allowed: true,
      command_type: "retry",
      risk_level: "medium",
      requires_confirmation: true,
      requires_approval: true,
      effect_class: "write_low_risk",
      tool_id: "experiment.run_variant",
      skill_id: "optimize-product-representation",
      side_effects: ["create_experiment_run"],
      blockers: [],
      warnings: [],
      rollback_guidance: "Low-risk writes can usually be superseded by a later action.",
      summary: "Preflight passed with medium risk.",
    });

    render(
      <OperatorConsoleChat
        run={{
          id: "run-1",
          experiment_id: "exp-12345678",
          status: "failed",
          state: "experiment_run_completed",
          run_mode: "auto_execute_safe",
        }}
        actions={[
          {
            id: "action-1",
            agent_run_id: "run-1",
            sequence: 1,
            status: "failed",
            capability_name: "run_variant",
          },
        ]}
        events={[]}
        selectedAction={{
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 1,
          status: "failed",
          capability_name: "run_variant",
        }}
        nextRecommendedAction={{
          action: null,
          guardrails: [],
          hint: "No next action.",
        }}
        onPreflightCommand={onPreflightCommand}
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Retry selected/i }));

    expect(onIssueCommand).not.toHaveBeenCalled();
    expect(await screen.findByText(/Click the command again to confirm/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Retry selected/i }));

    await waitFor(() =>
      expect(onIssueCommand).toHaveBeenCalledWith({
        command_type: "retry",
        action_id: "action-1",
        message: "Retry run_variant",
      }),
    );
  });
});
