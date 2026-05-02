import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentRunsPage from "./page";

const pushMock = vi.fn();
const replaceMock = vi.fn();

const listAgentRunsMock = vi.fn();
const listExperimentsMock = vi.fn();
const getAgentRunMock = vi.fn();
const getAgentRunEventsMock = vi.fn();
const createAgentRunMock = vi.fn();
const decideAgentActionMock = vi.fn();
const controlAgentRunMock = vi.fn();
const listAgentRuntimeRegistryMock = vi.fn();
const listAgentRuntimeRegistryAuditMock = vi.fn();
const listAgentRuntimeRegistryReleasesMock = vi.fn();
const issueAgentRunCommandMock = vi.fn();
const preflightAgentRunCommandMock = vi.fn();
let searchParamsValue = "experiment_id=exp-1";

const localStorageMock = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
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
    actions,
  }: {
    title: string;
    actions?: ReactNode;
  }) => (
    <header>
      <h1>{title}</h1>
      {actions}
    </header>
  ),
}));

vi.mock("../../lib/api", () => ({
  listAgentRuns: (...args: unknown[]) => listAgentRunsMock(...args),
  listExperiments: (...args: unknown[]) => listExperimentsMock(...args),
  getAgentRun: (...args: unknown[]) => getAgentRunMock(...args),
  getAgentRunEvents: (...args: unknown[]) => getAgentRunEventsMock(...args),
  createAgentRun: (...args: unknown[]) => createAgentRunMock(...args),
  decideAgentAction: (...args: unknown[]) => decideAgentActionMock(...args),
  controlAgentRun: (...args: unknown[]) => controlAgentRunMock(...args),
  listAgentRuntimeRegistry: (...args: unknown[]) => listAgentRuntimeRegistryMock(...args),
  listAgentRuntimeRegistryAudit: (...args: unknown[]) =>
    listAgentRuntimeRegistryAuditMock(...args),
  listAgentRuntimeRegistryReleases: (...args: unknown[]) =>
    listAgentRuntimeRegistryReleasesMock(...args),
  issueAgentRunCommand: (...args: unknown[]) => issueAgentRunCommandMock(...args),
  preflightAgentRunCommand: (...args: unknown[]) =>
    preflightAgentRunCommandMock(...args),
}));

describe("AgentRunsPage timeline presets", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: localStorageMock,
      configurable: true,
    });
    localStorageMock.getItem.mockReset();
    localStorageMock.setItem.mockReset();
    localStorageMock.removeItem.mockReset();
    localStorageMock.clear.mockReset();
    pushMock.mockReset();
    replaceMock.mockReset();
    listAgentRunsMock.mockReset();
    listExperimentsMock.mockReset();
    getAgentRunMock.mockReset();
    getAgentRunEventsMock.mockReset();
    createAgentRunMock.mockReset();
    decideAgentActionMock.mockReset();
    controlAgentRunMock.mockReset();
    listAgentRuntimeRegistryMock.mockReset();
    listAgentRuntimeRegistryAuditMock.mockReset();
    listAgentRuntimeRegistryReleasesMock.mockReset();
    issueAgentRunCommandMock.mockReset();
    preflightAgentRunCommandMock.mockReset();
    searchParamsValue = "experiment_id=exp-1";
    window.localStorage.clear();

    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-1",
          experiment_id: "exp-1",
          status: "planned",
          state: "battery_ready",
          budgets: {},
          requires_approval: true,
          run_mode: "plan_only",
          allowed_capabilities: ["run_variant"],
          principal_type: "human",
          policy_profile_id: "human_approval_required",
          registry_version: "agent-runtime-static-v1",
          registry_fingerprint: "abcdef1234567890",
        },
      ],
    });
    listExperimentsMock.mockResolvedValue({ experiments: [] });
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "planned",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "plan_only",
        allowed_capabilities: ["run_variant"],
        principal_type: "human",
        policy_profile_id: "human_approval_required",
        trace_id: "trace_1234567890",
        registry_version: "agent-runtime-static-v1",
        registry_fingerprint: "abcdef1234567890",
      },
      actions: [],
    });
    getAgentRunEventsMock.mockResolvedValue({
      events: [],
      page: {
        before_cursor: null,
        after_cursor: null,
        has_more_before: false,
        has_more_after: false,
      },
    });
    createAgentRunMock.mockResolvedValue({ run: { id: "run-2" } });
    decideAgentActionMock.mockResolvedValue({});
    controlAgentRunMock.mockResolvedValue({});
    issueAgentRunCommandMock.mockResolvedValue({
      command: { id: "evt-command", run_id: "run-1", sequence: 0, event_type: "operator_command_approve", status: "completed" },
      run: { id: "run-1" },
    });
    preflightAgentRunCommandMock.mockResolvedValue({
      preflight: {
        allowed: true,
        command_type: "approve",
        risk_level: "low",
        requires_confirmation: false,
        requires_approval: true,
        side_effects: [],
        blockers: [],
        warnings: [],
        rollback_guidance: "No direct side effects are expected from this command.",
        summary: "Preflight passed with low risk.",
      },
    });
    listAgentRuntimeRegistryMock.mockResolvedValue({
      registry_version: "agent-runtime-static-v1",
      registry_fingerprint: "abcdef1234567890",
      registry_hash_algorithm: "sha256",
      registry_snapshot_id: "abcdef1234567890",
      registry_snapshot_created_at: "2026-05-02T10:00:00Z",
      registry_source: "static_code",
      registry_status: "active",
      skills: [
        {
          id: "optimize-product-representation",
          name: "Optimize Product Representation",
          description: "Improve product representation.",
          version: "v1",
          tool_ids: ["experiment.run_variant"],
          risk_class: "write_low_risk",
        },
      ],
      tools: [
        {
          id: "experiment.run_variant",
          capability_name: "run_variant",
          summary: "Execute one candidate variant against frozen snapshots.",
          default_version: "v1",
          input_schema: {
            type: "object",
            required: ["experiment_id"],
            properties: { experiment_id: { type: "string" } },
          },
          output_schema: {
            type: "object",
            properties: { metric_id: { type: "string" } },
          },
          side_effects: ["create_experiment_run"],
          review_checklist: ["Compare the metric against control before promotion."],
          owner_principal_id: "platform.commerce-optimization",
          steward_team: "commerce-optimization",
          effect_class: "write_low_risk",
        },
      ],
      capabilities: [
        {
          name: "run_variant",
          tool_id: "experiment.run_variant",
          summary: "Execute one candidate variant against frozen snapshots.",
          default_version: "v1",
          input_schema: {
            type: "object",
            required: ["experiment_id"],
            properties: { experiment_id: { type: "string" } },
          },
          output_schema: {
            type: "object",
            properties: { metric_id: { type: "string" } },
          },
          side_effects: ["create_experiment_run"],
          review_checklist: ["Compare the metric against control before promotion."],
          owner_principal_id: "platform.commerce-optimization",
          steward_team: "commerce-optimization",
          effect_class: "write_low_risk",
        },
      ],
      skill_ids_by_tool: {
        "experiment.run_variant": ["optimize-product-representation"],
      },
      policy_profiles: [],
    });
    listAgentRuntimeRegistryAuditMock.mockResolvedValue({
      events: [
        {
          id: "registry-audit-1",
          event_type: "registry_changed",
          previous_registry_fingerprint: "1111111111111111",
          registry_fingerprint: "abcdef1234567890",
          registry_version: "agent-runtime-static-v1",
          source: "static_code",
          created_at: "2026-05-02T10:00:00Z",
          diff: {
            tools: { added: ["experiment.run_variant"], removed: [], changed: [] },
            skills: { added: [], removed: [], changed: [] },
            capabilities: { added: [], removed: [], changed: [] },
            policy_profiles: { added: [], removed: [], changed: [] },
            skill_ids_by_tool_changed: true,
          },
        },
      ],
    });
    listAgentRuntimeRegistryReleasesMock.mockResolvedValue({
      releases: [
        {
          id: "abcdef1234567890",
          registry_version: "agent-runtime-static-v1",
          registry_fingerprint: "abcdef1234567890",
          hash_algorithm: "sha256",
          source: "static_code",
          status: "active",
          created_at: "2026-05-02T10:00:00Z",
          counts: {
            skills: 3,
            tools: 12,
            capabilities: 12,
            policy_profiles: 3,
          },
        },
      ],
    });
  });

  it("applies Policy failures preset to event query payload", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Policy failures \(24h\)/i });

    getAgentRunEventsMock.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /Policy failures \(24h\)/i }));

    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    const lastCall = getAgentRunEventsMock.mock.calls.at(-1);
    expect(lastCall).toBeTruthy();
    const payload = lastCall?.[1] as Record<string, unknown>;
    expect(payload.event_type).toBe("policy");
    expect(payload.status).toBe("failed");
    expect(typeof payload.since).toBe("string");
  });

  it("applies Commands preset to event query payload", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Commands \(24h\)/i });

    getAgentRunEventsMock.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /Commands \(24h\)/i }));

    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    const payload = getAgentRunEventsMock.mock.calls.at(-1)?.[1] as Record<
      string,
      unknown
    >;
    expect(payload.event_type).toBe("command");
    expect(payload.status).toBe("all");
    expect(typeof payload.since).toBe("string");
  });

  it("shows custom view badge when filters diverge from presets", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Policy failures \(24h\)/i });

    await userEvent.click(screen.getByRole("button", { name: /Policy failures \(24h\)/i }));
    await userEvent.selectOptions(
      screen.getByLabelText(/Timeline status filter/i),
      "executed",
    );

    await waitFor(() => {
      expect(screen.getByText("Custom view")).toBeInTheDocument();
    });
  });

  it("syncs timeline preset state into URL query params", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Policy failures \(24h\)/i });

    replaceMock.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /Policy failures \(24h\)/i }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    const calls = replaceMock.mock.calls.map((call) => String(call?.[0] ?? ""));
    expect(
      calls.some(
        (value) =>
          value.includes("timeline_preset=policy_failures_24h") &&
          value.includes("timeline_event_type=policy"),
      ),
    ).toBe(true);
  });

  it("requests centered recovery when deep-linked event is outside current window", async () => {
    searchParamsValue = "experiment_id=exp-1&event_id=evt-404";
    getAgentRunEventsMock
      .mockResolvedValueOnce({
        events: [],
        page: {
          before_cursor: null,
          after_cursor: null,
          has_more_before: false,
          has_more_after: false,
        },
      })
      .mockResolvedValue({
        events: [],
        page: {
          before_cursor: null,
          after_cursor: null,
          has_more_before: false,
          has_more_after: false,
        },
      });

    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await waitFor(() => {
      const calls = getAgentRunEventsMock.mock.calls;
      expect(
        calls.some((call) => {
          const payload = call?.[1] as Record<string, unknown> | undefined;
          return payload?.event_id === "evt-404" && payload?.around === 240;
        }),
      ).toBe(true);
    });
  });

  it("shows guardrail reason and disables approve for proposed action when run is failed", async () => {
    getAgentRunMock.mockResolvedValueOnce({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "failed",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "plan_only",
      },
      actions: [
        {
          id: "act-1",
          sequence: 1,
          status: "proposed",
          capability_name: "run_variant",
          capability_version: "v1",
          rationale: "run candidate",
          confidence: 0.7,
          inputs: {},
          outputs: {},
        },
      ],
    });

    render(<AgentRunsPage />);
    await waitFor(() => expect(screen.getByText("Next recommended action")).toBeInTheDocument());
    expect(
      screen.getAllByText(/Run is failed\. Start a new run or move to a healthy run state\./i)
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });

  it("lets operator chat drive timeline filters and next-action selection", async () => {
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "planned",
        state: "variants_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "auto_execute_safe",
      },
      actions: [
        {
          id: "act-1",
          sequence: 1,
          status: "proposed",
          capability_name: "publish_copy_revision",
          capability_version: "v1",
          rationale: "publish candidate",
          confidence: 0.8,
          variant_id: "variant-1",
          outputs: { metric_id: "metric-1" },
          inputs: {},
        },
        {
          id: "act-2",
          sequence: 2,
          status: "approved",
          capability_name: "request_synthetic_validation",
          capability_version: "v1",
          rationale: "validation candidate",
          confidence: 0.7,
          validation_job_id: "job-1",
          inputs: {},
          outputs: {},
        },
      ],
    });
    getAgentRunEventsMock.mockResolvedValue({
      events: [
        {
          id: "evt-1",
          status: "failed",
          event_type: "policy",
          capability_name: "publish_copy_revision",
          is_policy_event: true,
          note: "Policy requires review.",
          timestamp: "2026-03-31T10:00:00Z",
        },
      ],
      page: {
        before_cursor: null,
        after_cursor: null,
        has_more_before: false,
        has_more_after: false,
      },
    });

    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());

    await userEvent.click(screen.getAllByRole("button", { name: /^Open experiment$/i })[0]);
    expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");

    getAgentRunEventsMock.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /Focus policy events/i }));
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    let payload = getAgentRunEventsMock.mock.calls.at(-1)?.[1] as Record<string, unknown>;
    expect(payload.event_type).toBe("policy");
    expect(payload.status).toBe("failed");

    getAgentRunEventsMock.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /Focus approvals/i }));
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    payload = getAgentRunEventsMock.mock.calls.at(-1)?.[1] as Record<string, unknown>;
    expect(payload.event_type).toBe("all");
    expect(payload.status).toBe("proposed");

    await userEvent.click(screen.getByRole("button", { name: /Jump to next action/i }));
    expect(screen.getByText(/Selection: publish_copy_revision/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Variant: variant-/i }));
    expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");

    await userEvent.click(screen.getByRole("button", { name: /Metric: metric-1/i }));
    expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");

    getAgentRunEventsMock.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /Focus validation-linked/i }));
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    payload = getAgentRunEventsMock.mock.calls.at(-1)?.[1] as Record<string, unknown>;
    expect(payload.capability_name).toBe("request_synthetic_validation");

    await userEvent.click(screen.getByRole("button", { name: /Open validation/i }));
    expect(pushMock).toHaveBeenCalledWith("/validation?experiment_id=exp-1&run_id=run-1");

    await userEvent.click(screen.getByRole("button", { name: /Open interventions/i }));
    expect(pushMock).toHaveBeenCalledWith("/interventions?run_id=run-1");

    await userEvent.click(screen.getByRole("button", { name: /Open experiment context/i }));
    expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");
  });

  it("shows the selected run skills and tool registry contract", async () => {
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "planned",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "plan_only",
        allowed_capabilities: ["run_variant"],
      },
      actions: [
        {
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 1,
          status: "proposed",
          capability_name: "run_variant",
          capability_version: "v1",
          rationale: "Run variant.",
          inputs: { experiment_id: "exp-1" },
          outputs: {},
          tool_id: "experiment.run_variant",
          skill_id: "optimize-product-representation",
          registry_version: "agent-runtime-static-v1",
          registry_fingerprint: "abcdef1234567890",
          tool_version: "v1",
          skill_version: "v1",
          effect_class: "write_low_risk",
        },
      ],
    });

    render(<AgentRunsPage />);

    expect(await screen.findByText(/Skills and tools/i)).toBeInTheDocument();
    expect(screen.getByText(/Optimize Product Representation/i)).toBeInTheDocument();
    expect(screen.getAllByText(/experiment.run_variant/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/write_low_risk/i).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Execute one candidate variant against frozen snapshots/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Compare the metric against control before promotion/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Registry: agent-runtime-static-v1/)).toBeInTheDocument();
    expect(screen.getByText(/Run registry: agent-runtime-static-v1/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Fingerprint: abcdef123456/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Registry source: static_code/i)).toBeInTheDocument();
    expect(screen.getByText(/Release status: active/i)).toBeInTheDocument();
    expect(screen.getByText(/Registry releases/i)).toBeInTheDocument();
    expect(screen.getByText(/3 skills · 12 tools · 12 capabilities/i)).toBeInTheDocument();
    expect(screen.getByText(/Registry release trail/i)).toBeInTheDocument();
    expect(screen.getByText(/tools: \+1 -0 ~0/i)).toBeInTheDocument();
    expect(screen.getByText(/Receipt fingerprint: abcdef123456/i)).toBeInTheDocument();
    expect(screen.getByText(/Tool version: v1/i)).toBeInTheDocument();
    expect(screen.getByText(/Skill version: v1/i)).toBeInTheDocument();
    expect(screen.getByText(/Owner: platform\.commerce-optimization/i)).toBeInTheDocument();
    expect(screen.getByText(/Steward: commerce-optimization/i)).toBeInTheDocument();
    expect(listAgentRuntimeRegistryMock).toHaveBeenCalled();
    expect(listAgentRuntimeRegistryAuditMock).toHaveBeenCalledWith({ limit: 5 });
    expect(listAgentRuntimeRegistryReleasesMock).toHaveBeenCalledWith({ limit: 5 });
  });

  it("routes operator chat steering commands through the command API", async () => {
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "planned",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "plan_only",
        allowed_capabilities: ["run_variant"],
      },
      actions: [
        {
          id: "action-1",
          agent_run_id: "run-1",
          sequence: 1,
          status: "proposed",
          capability_name: "run_variant",
          capability_version: "v1",
          rationale: "Run variant.",
          inputs: {},
          outputs: {},
          tool_id: "experiment.run_variant",
          skill_id: "optimize-product-representation",
          effect_class: "write_low_risk",
        },
      ],
    });

    render(<AgentRunsPage />);

    await screen.findByText(/Selection: run_variant/i);
    await userEvent.click(screen.getByRole("button", { name: /Approve selected/i }));

    expect(preflightAgentRunCommandMock).toHaveBeenCalledWith(
      "run-1",
      {
        command_type: "approve",
        action_id: "action-1",
        message: "Approve run_variant",
      },
      "user-a",
    );
    await waitFor(() => expect(issueAgentRunCommandMock).toHaveBeenCalled());
    expect(issueAgentRunCommandMock).toHaveBeenCalledWith(
      "run-1",
      {
        command_type: "approve",
        action_id: "action-1",
        message: "Approve run_variant",
      },
      "user-a",
    );
  });
});
