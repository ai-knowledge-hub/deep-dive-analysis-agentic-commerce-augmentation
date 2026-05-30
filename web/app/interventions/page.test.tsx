import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InterventionsPage from "./page";

const pushMock = vi.fn();
const listAgentRunsMock = vi.fn();
const getAgentRunMock = vi.fn();
const getAgentRunEventsMock = vi.fn();
const decideAgentActionMock = vi.fn();
const controlAgentRunMock = vi.fn();
const issueAgentRunCommandMock = vi.fn();
const preflightAgentRunCommandMock = vi.fn();
const listAgentRuntimeRegistryMock = vi.fn();
let searchParamsValue = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams(searchParamsValue),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { id: "user-a" } }),
}));

vi.mock("../../components/layout/Sidebar", () => ({
  Sidebar: () => null,
}));

vi.mock("../../components/layout/DetailHeader", () => ({
  DetailHeader: ({
    title,
    backLabel,
    onBack,
    actions,
  }: {
    title: string;
    backLabel?: string;
    onBack?: () => void;
    actions?: ReactNode;
  }) => (
    <header>
      <h1>{title}</h1>
      {backLabel && onBack ? <button onClick={onBack}>{backLabel}</button> : null}
      {actions}
    </header>
  ),
}));

vi.mock("../../lib/api", () => ({
  listAgentRuns: (...args: unknown[]) => listAgentRunsMock(...args),
  getAgentRun: (...args: unknown[]) => getAgentRunMock(...args),
  getAgentRunEvents: (...args: unknown[]) => getAgentRunEventsMock(...args),
  decideAgentAction: (...args: unknown[]) => decideAgentActionMock(...args),
  controlAgentRun: (...args: unknown[]) => controlAgentRunMock(...args),
  issueAgentRunCommand: (...args: unknown[]) => issueAgentRunCommandMock(...args),
  listAgentRuntimeRegistry: (...args: unknown[]) => listAgentRuntimeRegistryMock(...args),
  preflightAgentRunCommand: (...args: unknown[]) =>
    preflightAgentRunCommandMock(...args),
}));

describe("InterventionsPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    listAgentRunsMock.mockReset();
    getAgentRunMock.mockReset();
    getAgentRunEventsMock.mockReset();
    decideAgentActionMock.mockReset();
    controlAgentRunMock.mockReset();
    issueAgentRunCommandMock.mockReset();
    preflightAgentRunCommandMock.mockReset();
    listAgentRuntimeRegistryMock.mockReset();
    searchParamsValue = "";

    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-1",
          experiment_id: "exp-failed",
          harness_id: "safe_autonomy_b2b",
          policy_profile_id: "human_approval_required",
          run_mode: "plan_only",
          status: "failed",
          state: "validation_completed",
        },
        {
          id: "run-2",
          experiment_id: "exp-approve",
          harness_id: "safe_autonomy_b2b",
          policy_profile_id: "human_approval_required",
          run_mode: "plan_only",
          status: "planned",
          state: "variants_ready",
        },
        {
          id: "run-3",
          experiment_id: "exp-retry",
          harness_id: "safe_autonomy_b2b",
          policy_profile_id: "human_approval_required",
          run_mode: "plan_only",
          status: "planned",
          state: "variants_ready",
        },
        {
          id: "run-4",
          experiment_id: "exp-active",
          harness_id: "operator_supervised",
          policy_profile_id: "human_approval_required",
          run_mode: "auto_execute_safe",
          status: "running",
          state: "experiment_run_completed",
        },
      ],
    });

    listAgentRuntimeRegistryMock.mockResolvedValue({
      skills: [],
      tools: [],
      capabilities: [],
      skill_ids_by_tool: {},
      policy_profiles: [],
      harness_profiles: [
        {
          id: "safe_autonomy_b2b",
          name: "Safe Autonomy B2B",
          description: "Auto-executes low-risk work and escalates risky changes.",
          default_run_mode: "auto_execute_safe",
          default_policy_profile_id: "human_approval_required",
          retry_strategy: "last_safe_checkpoint",
          fallback_order: ["registry_recovery_template", "operator_intervention"],
          approval_strategy: "auto_low_risk_human_governed_high_risk",
          memory_policy: "trace_scoped",
          stopping_conditions: ["budget_exhausted", "policy_violation"],
        },
        {
          id: "operator_supervised",
          name: "Operator Supervised",
          description: "Keeps execution gated by a human operator.",
          default_run_mode: "plan_only",
          default_policy_profile_id: "human_approval_required",
          retry_strategy: "manual_review",
          fallback_order: ["operator_intervention"],
          approval_strategy: "human_approval_required",
          memory_policy: "trace_scoped",
          stopping_conditions: ["operator_pause"],
        },
      ],
    });

    getAgentRunMock.mockImplementation(async (runId: string) => {
      if (runId === "run-2") {
        return {
          run: { id: runId },
          actions: [
            {
              id: "act-approve",
              sequence: 1,
              status: "proposed",
              capability_name: "publish_copy_revision",
              rationale: "Publish the winning revision.",
            },
          ],
        };
      }
      if (runId === "run-3") {
        return {
          run: { id: runId },
          actions: [
            {
              id: "act-approved",
              sequence: 1,
              status: "approved",
              capability_name: "run_variant",
              rationale: "Ready for the next run step.",
            },
          ],
        };
      }
      return { run: { id: runId }, actions: [] };
    });

    getAgentRunEventsMock.mockImplementation(async (runId: string) => {
      if (runId === "run-1") {
        return {
          events: [
            {
              id: "evt-failed",
              status: "failed",
              note: "Validation provider failed.",
              timestamp: "2026-03-18T10:00:00Z",
            },
          ],
        };
      }
      if (runId === "run-2") {
        return {
          events: [
            {
              id: "evt-policy",
              status: "failed",
              is_policy_event: true,
              note: "Policy blocked publishing without review.",
              timestamp: "2026-03-18T11:00:00Z",
            },
          ],
        };
      }
      if (runId === "run-4") {
        return {
          events: [
            {
              id: "evt-running",
              status: "executing",
              note: "Executing active step.",
              timestamp: "2026-03-18T12:00:00Z",
            },
          ],
        };
      }
      if (runId === "run-3") {
        return {
          events: [
            {
              id: "evt-retry-proposed",
              event_type: "action_retry_proposed",
              status: "proposed",
              capability_name: "run_variant",
              effect_class: "write_low_risk",
              note: "Retry action proposed by operator chat",
              timestamp: "2026-03-18T11:30:00Z",
            },
            {
              id: "evt-recovery-proposed",
              action_id: "act-failed-source",
              event_type: "action_recovery_proposed",
              status: "proposed",
              capability_name: "recommend_next_action",
              effect_class: "recommend",
              note: "Recovery action proposed by operator change-plan command",
              anchors: {
                rollback_guidance:
                  "Low-risk writes can usually be superseded by a later action.",
                compensating_actions: [
                  {
                    label: "Ask policy for the safest compensating next action",
                    capability_name: "recommend_next_action",
                  },
                ],
              },
              timestamp: "2026-03-18T11:31:00Z",
            },
          ],
        };
      }
      return { events: [] };
    });

    decideAgentActionMock.mockResolvedValue({
      action: { id: "act-approve", status: "approved" },
    });
    controlAgentRunMock.mockResolvedValue({
      run: { id: "run-3" },
      message: "Queued control action.",
    });
    issueAgentRunCommandMock.mockResolvedValue({
      command: {
        id: "evt-command",
        run_id: "run-3",
        sequence: 0,
        event_type: "operator_command_change_plan",
        status: "completed",
      },
      run: { id: "run-3" },
    });
    preflightAgentRunCommandMock.mockResolvedValue({
      preflight: {
        allowed: true,
        command_type: "change_plan",
        risk_level: "medium",
        requires_confirmation: true,
        requires_approval: true,
        effect_class: "recommend",
        tool_id: "policy.recommend_next_action",
        skill_id: "recommend",
        side_effects: ["create_experiment_recommendation"],
        blockers: [],
        warnings: [
          "Change-plan creates a proposed recovery action for operator review.",
        ],
        rollback_guidance:
          "Low-risk writes can usually be superseded by a later action.",
        summary: "Preflight passed with medium risk.",
      },
      run: { id: "run-3" },
      action: null,
    });
  });

  it("renders escalation, approval, retry, and pause queues", async () => {
    render(<InterventionsPage />);

    await waitFor(() => expect(listAgentRunsMock).toHaveBeenCalled());
    expect(listAgentRuntimeRegistryMock).toHaveBeenCalledWith("user-a");

    expect(
      await screen.findByText(/Experiment exp-fail needs manual recovery/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/approve publish_copy_revision/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Experiment exp-retr is ready to resume/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Experiment exp-retr has a retry proposal/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Experiment exp-retr has a recovery proposal/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Recovery path: Low-risk writes can usually be superseded/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Recovery action: Ask policy for the safest/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Execution posture/i)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Safe Autonomy B2B/i)[0]).toBeInTheDocument();
    expect(
      screen.getAllByText(/tool contract recovery template -> operator intervention/i)[0],
    ).toBeInTheDocument();
    expect(screen.getByText(/last safe checkpoint/i)).toBeInTheDocument();
    expect(screen.getByText(/operator pause/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Experiment exp-acti is executing/i),
    ).toBeInTheDocument();
  });

  it("approves queued actions from the interventions queue", async () => {
    const user = userEvent.setup();
    render(<InterventionsPage />);

    await screen.findByText(/approve publish_copy_revision/i);
    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(decideAgentActionMock).toHaveBeenCalledWith(
        "act-approve",
        { decision: "approve" },
        "user-a",
      );
    });
  });

  it("runs resume and pause controls from the interventions queue", async () => {
    const user = userEvent.setup();
    render(<InterventionsPage />);

    await screen.findByText(/Experiment exp-retr is ready to resume/i);

    await user.click(screen.getByRole("button", { name: "Resume run" }));
    await waitFor(() => {
      expect(controlAgentRunMock).toHaveBeenCalledWith("run-3", "start", "user-a");
    });

    await user.click(screen.getByRole("button", { name: "Pause run" }));
    await waitFor(() => {
      expect(controlAgentRunMock).toHaveBeenCalledWith("run-4", "pause", "user-a");
    });
  });

  it("creates recovery proposals from command-originated recommendations", async () => {
    const user = userEvent.setup();
    render(<InterventionsPage />);

    await screen.findByText(/Recovery action: Ask policy for the safest/i);
    await user.click(
      screen.getByRole("button", { name: /Create recovery proposal/i }),
    );

    await waitFor(() => {
      expect(preflightAgentRunCommandMock).toHaveBeenCalledWith(
        "run-3",
        {
          command_type: "change_plan",
          action_id: "act-failed-source",
          message: "Ask policy for the safest compensating next action",
          metadata: {
            recovery_strategy: "compensating_action",
            capability_name: "recommend_next_action",
            source_event_id: "evt-recovery-proposed",
            compensating_priority: undefined,
            compensating_rationale: undefined,
            inputs: { experiment_id: "exp-retry" },
          },
        },
        "user-a",
      );
    });
    expect(await screen.findByText(/safety check passed with medium risk/i)).toBeInTheDocument();
    expect(screen.getByText(/Click again to confirm recovery proposal creation/i)).toBeInTheDocument();
    expect(issueAgentRunCommandMock).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: /Confirm recovery proposal/i }),
    );

    await waitFor(() => {
      expect(issueAgentRunCommandMock).toHaveBeenCalledWith(
        "run-3",
        {
          command_type: "change_plan",
          action_id: "act-failed-source",
          message: "Ask policy for the safest compensating next action",
          metadata: {
            recovery_strategy: "compensating_action",
            capability_name: "recommend_next_action",
            source_event_id: "evt-recovery-proposed",
            compensating_priority: undefined,
            compensating_rationale: undefined,
            inputs: { experiment_id: "exp-retry" },
          },
        },
        "user-a",
      );
    });
    expect(
      await screen.findByText(/Recovery proposal created for recommend_next_action/i),
    ).toBeInTheDocument();
  });

  it("scopes interventions to the selected run when run_id is provided", async () => {
    searchParamsValue = "run_id=run-2";
    const user = userEvent.setup();
    render(<InterventionsPage />);

    expect(await screen.findByText(/Run-scoped view/i)).toBeInTheDocument();
    expect(screen.getByText(/approve publish_copy_revision/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/Experiment exp-fail needs manual recovery/i),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Back to selected run/i }));
    expect(pushMock).toHaveBeenCalledWith("/runs?run_id=run-2");
  });
});
