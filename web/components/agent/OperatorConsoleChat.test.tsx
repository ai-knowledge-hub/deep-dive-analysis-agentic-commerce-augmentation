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
          client_id: "client-1",
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

    expect(screen.getByText(/Selection: publish copy revision/i)).toBeInTheDocument();
    expect(screen.queryByText(/Selection: publish_copy_revision/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Policy: 1/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Explain run/i }));
    expect(screen.getByText(/progressed to variants ready/i)).toBeInTheDocument();
    expect(screen.queryByText(/variants_ready/i)).not.toBeInTheDocument();

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
          client_id: "client-1",
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
          client_id: "client-1",
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
      message: "Approve publish copy revision",
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
          client_id: "client-1",
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
          client_id: "client-1",
          experiment_id: "exp-12345678",
          status: "failed",
          state: "experiment_run_completed",
          run_mode: "auto_execute_safe",
          allowed_capabilities: [
            "recommend_next_action",
            "review_validation_readiness",
          ],
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
        message: "Retry run variant",
        metadata: { retry_strategy: "same_action" },
      }),
    );
  });

  it("issues checkpoint retry and change-plan recovery commands with metadata", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue(undefined);
    const runtimeRegistry = {
      registry_version: "agent-runtime-static-v1",
      skills: [
        {
          id: "request-validation-and-ingest-result",
          name: "Request Validation And Ingest Result",
          description: "Request validation and ingest result.",
          version: "v1",
          tool_ids: ["validation.review_readiness"],
          risk_class: "external_side_effect",
        },
        {
          id: "promote-and-publish-approved-copy",
          name: "Promote And Publish Approved Copy",
          description: "Promote validated variants and publish approved copy changes.",
          version: "v1",
          tool_ids: ["validation.review_readiness"],
          risk_class: "write_high_risk",
        },
      ],
      tools: [],
      capabilities: [
        {
          name: "review_validation_readiness",
          tool_id: "validation.review_readiness",
        },
      ],
      skill_ids_by_tool: {
        "validation.review_readiness": [
          "request-validation-and-ingest-result",
          "promote-and-publish-approved-copy",
        ],
      },
      skill_selection_by_tool: {
        "validation.review_readiness": {
          default_skill_id: "request-validation-and-ingest-result",
          candidate_skill_ids: [
            "request-validation-and-ingest-result",
            "promote-and-publish-approved-copy",
          ],
        },
      },
      recovery_templates: [
        {
          id: "recovery.review_validation_readiness",
          capability_name: "review_validation_readiness",
          tool_id: "validation.review_readiness",
          effect_class: "read",
          summary: "Re-check readiness gates before creating more recovery work.",
          default_inputs: {},
          operator_notes: [
            "Recovery proposals are created for operator review; they do not execute immediately.",
          ],
          side_effects: ["read_validation_and_metrics"],
        },
      ],
      policy_profiles: [],
    };

    render(
      <OperatorConsoleChat
        run={{
          id: "run-1",
          client_id: "client-1",
          experiment_id: "exp-12345678",
          status: "failed",
          state: "experiment_run_completed",
          run_mode: "auto_execute_safe",
          allowed_capabilities: [
            "recommend_next_action",
            "review_validation_readiness",
          ],
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
        runtimeRegistry={runtimeRegistry}
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
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Retry checkpoint/i }));
    expect(onIssueCommand).toHaveBeenCalledWith({
      command_type: "retry",
      action_id: "action-1",
      message: "Retry run variant from checkpoint",
      metadata: { retry_strategy: "last_safe_checkpoint" },
    });

    await user.click(screen.getByRole("button", { name: /Recovery action/i }));
    expect(onIssueCommand).toHaveBeenCalledWith({
      command_type: "retry",
      action_id: "action-1",
      message: "Create recovery action for run variant",
      metadata: {
        retry_strategy: "create_recovery_action",
        capability_name: "recommend_next_action",
      },
    });

    await user.selectOptions(
      screen.getByLabelText(/Recovery target capability/i),
      "review_validation_readiness",
    );
    expect(
      screen.getByText(/Recovery template: recovery.review_validation_readiness/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Re-check readiness gates before creating more recovery work/i),
    ).toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText(/Preferred recovery skill/i),
      "promote-and-publish-approved-copy",
    );
    await user.click(screen.getByRole("button", { name: /Change plan/i }));
    expect(onIssueCommand).toHaveBeenCalledWith({
      command_type: "change_plan",
      action_id: "action-1",
      message: "Create a recovery plan proposal",
      metadata: {
        recovery_strategy: "propose_next_action",
        capability_name: "review_validation_readiness",
        skill_id: "promote-and-publish-approved-copy",
        preferred_skill_id: "promote-and-publish-approved-copy",
        inputs: { experiment_id: "exp-12345678" },
      },
    });
  });

  it("summarizes command outcomes from the runtime response", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue({
      command: {
        id: "evt-command",
        run_id: "run-1",
        sequence: 0,
        event_type: "operator_command_start",
        status: "completed",
      },
      run: {
        id: "run-1",
        status: "running",
        state: "variants_ready",
      },
      message: "Run resumed.",
      preflight: {
        allowed: true,
        command_type: "start",
        risk_level: "low",
        requires_confirmation: false,
        requires_approval: true,
        side_effects: [],
        blockers: [],
        warnings: [],
        rollback_guidance: "Resume with start once the operator is ready.",
        summary: "Preflight passed with low risk.",
      },
    });

    render(
      <OperatorConsoleChat
        run={{
          id: "run-1",
          client_id: "client-1",
          experiment_id: "exp-12345678",
          status: "paused",
          state: "variants_ready",
          run_mode: "auto_execute_safe",
        }}
        actions={[]}
        events={[]}
        selectedAction={null}
        nextRecommendedAction={{
          action: null,
          guardrails: [],
          hint: "No next action.",
        }}
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Start run/i }));

    expect(await screen.findByText(/Command completed: start/i)).toBeInTheDocument();
    expect(screen.getByText(/Run resumed/i)).toBeInTheDocument();
    expect(screen.getByText(/Run is running in variants ready state/i)).toBeInTheDocument();
    expect(screen.queryByText(/variants_ready/i)).not.toBeInTheDocument();
  });

  it("adds artifact-specific guidance to command outcomes", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue({
      command: {
        id: "evt-command",
        run_id: "run-1",
        sequence: 0,
        event_type: "operator_command_step",
        status: "completed",
      },
      run: {
        id: "run-1",
        status: "planned",
        state: "experiment_run_completed",
      },
      action: {
        id: "action-1",
        agent_run_id: "run-1",
        sequence: 1,
        status: "executed",
        capability_name: "run_variant",
        variant_id: "variant-1",
        validation_job_id: "job-1",
        snapshot_version: 7,
        rollback_guidance:
          "Low-risk writes can usually be superseded by a later action.",
        compensating_actions: [
          {
            label: "Ask policy for the safest compensating next action",
            capability_name: "recommend_next_action",
          },
        ],
        outputs: {
          new_metric_id: "metric-1",
        },
      },
      preflight: {
        allowed: true,
        command_type: "step",
        risk_level: "medium",
        requires_confirmation: true,
        requires_approval: true,
        side_effects: [],
        blockers: [],
        warnings: [],
        rollback_guidance: "Low-risk writes can usually be superseded by a later action.",
        summary: "Preflight passed with medium risk.",
      },
    });

    render(
      <OperatorConsoleChat
        run={{
          id: "run-1",
          client_id: "client-1",
          experiment_id: "exp-12345678",
          status: "running",
          state: "variants_ready",
          run_mode: "auto_execute_safe",
        }}
        actions={[]}
        events={[]}
        selectedAction={null}
        nextRecommendedAction={{
          action: null,
          guardrails: [],
          hint: "No next action.",
        }}
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Step run/i }));

    expect(await screen.findByText(/Review metric metric-1/i)).toBeInTheDocument();
    expect(screen.getByText(/Compare variant variant-1/i)).toBeInTheDocument();
    expect(screen.getByText(/Open validation job job-1/i)).toBeInTheDocument();
    expect(screen.getByText(/Recovery guidance: Low-risk writes/i)).toBeInTheDocument();
    expect(screen.getByText(/Recovery action: Ask policy/i)).toBeInTheDocument();
  });

  it("preflights and confirms step and cancel commands", async () => {
    const user = userEvent.setup();
    const onIssueCommand = vi.fn().mockResolvedValue(undefined);
    const onPreflightCommand = vi.fn().mockResolvedValue({
      allowed: true,
      command_type: "step",
      risk_level: "medium",
      requires_confirmation: true,
      requires_approval: true,
      side_effects: [],
      blockers: [],
      warnings: [],
      rollback_guidance: "Low-risk writes can usually be superseded by a later action.",
      summary: "Preflight passed with medium risk.",
    });

    render(
      <OperatorConsoleChat
        run={{
          id: "run-1",
          client_id: "client-1",
          experiment_id: "exp-12345678",
          status: "running",
          state: "variants_ready",
          run_mode: "auto_execute_safe",
        }}
        actions={[]}
        events={[]}
        selectedAction={null}
        nextRecommendedAction={{
          action: null,
          guardrails: [],
          hint: "No next action.",
        }}
        onPreflightCommand={onPreflightCommand}
        onIssueCommand={onIssueCommand}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Step run/i }));
    expect(onIssueCommand).not.toHaveBeenCalled();
    expect(await screen.findByText(/Click the command again to confirm/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Step run/i }));
    await waitFor(() =>
      expect(onIssueCommand).toHaveBeenCalledWith({
        command_type: "step",
        action_id: undefined,
        message: "Step this run",
      }),
    );

    onPreflightCommand.mockResolvedValue({
      allowed: true,
      command_type: "cancel",
      risk_level: "high",
      requires_confirmation: true,
      requires_approval: true,
      side_effects: [],
      blockers: [],
      warnings: ["Canceling a run is terminal."],
      rollback_guidance: "Cancel is terminal. Create a new run to continue.",
      summary: "Preflight passed with high risk.",
    });

    await user.click(screen.getByRole("button", { name: /Cancel run/i }));
    await user.click(screen.getByRole("button", { name: /Cancel run/i }));

    await waitFor(() =>
      expect(onIssueCommand).toHaveBeenCalledWith({
        command_type: "cancel",
        action_id: undefined,
        message: "Cancel this run",
      }),
    );
  });
});
