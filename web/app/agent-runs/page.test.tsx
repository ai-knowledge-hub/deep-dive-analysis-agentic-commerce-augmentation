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
const getExternalAgentJobForRunMock = vi.fn();
const verifyExternalAgentJobReceiptForRunMock = vi.fn();
const createAgentRunMock = vi.fn();
const decideAgentActionMock = vi.fn();
const controlAgentRunMock = vi.fn();
const listAgentRuntimeRegistryMock = vi.fn();
const listAgentRuntimeRegistryAuditMock = vi.fn();
const listAgentRuntimeRegistryReleasesMock = vi.fn();
const getAgentRuntimeRegistryReleaseMock = vi.fn();
const updateAgentRuntimeRegistryOwnershipMock = vi.fn();
const verifyAgentRuntimeRegistryApprovalReceiptMock = vi.fn();
const backfillAgentRuntimeRegistryPinsMock = vi.fn();
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
  getExternalAgentJobForRun: (...args: unknown[]) =>
    getExternalAgentJobForRunMock(...args),
  verifyExternalAgentJobReceiptForRun: (...args: unknown[]) =>
    verifyExternalAgentJobReceiptForRunMock(...args),
  createAgentRun: (...args: unknown[]) => createAgentRunMock(...args),
  decideAgentAction: (...args: unknown[]) => decideAgentActionMock(...args),
  controlAgentRun: (...args: unknown[]) => controlAgentRunMock(...args),
  listAgentRuntimeRegistry: (...args: unknown[]) => listAgentRuntimeRegistryMock(...args),
  listAgentRuntimeRegistryAudit: (...args: unknown[]) =>
    listAgentRuntimeRegistryAuditMock(...args),
  listAgentRuntimeRegistryReleases: (...args: unknown[]) =>
    listAgentRuntimeRegistryReleasesMock(...args),
  getAgentRuntimeRegistryRelease: (...args: unknown[]) =>
    getAgentRuntimeRegistryReleaseMock(...args),
  updateAgentRuntimeRegistryOwnership: (...args: unknown[]) =>
    updateAgentRuntimeRegistryOwnershipMock(...args),
  verifyAgentRuntimeRegistryApprovalReceipt: (...args: unknown[]) =>
    verifyAgentRuntimeRegistryApprovalReceiptMock(...args),
  backfillAgentRuntimeRegistryPins: (...args: unknown[]) =>
    backfillAgentRuntimeRegistryPinsMock(...args),
  issueAgentRunCommand: (...args: unknown[]) => issueAgentRunCommandMock(...args),
  preflightAgentRunCommand: (...args: unknown[]) =>
    preflightAgentRunCommandMock(...args),
  getRegistryWriteToken: () => undefined,
  setRegistryWriteToken: vi.fn(),
  clearRegistryWriteToken: vi.fn(),
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
    getExternalAgentJobForRunMock.mockReset();
    verifyExternalAgentJobReceiptForRunMock.mockReset();
    createAgentRunMock.mockReset();
    decideAgentActionMock.mockReset();
    controlAgentRunMock.mockReset();
    listAgentRuntimeRegistryMock.mockReset();
    listAgentRuntimeRegistryAuditMock.mockReset();
    listAgentRuntimeRegistryReleasesMock.mockReset();
    getAgentRuntimeRegistryReleaseMock.mockReset();
    updateAgentRuntimeRegistryOwnershipMock.mockReset();
    verifyAgentRuntimeRegistryApprovalReceiptMock.mockReset();
    backfillAgentRuntimeRegistryPinsMock.mockReset();
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
        {
          id: "registry-audit-2",
          event_type: "registry_pin_backfill_applied",
          previous_registry_fingerprint: null,
          registry_fingerprint: "abcdef1234567890",
          registry_version: "agent-runtime-static-v1",
          source: "operator_backfill",
          created_at: "2026-05-02T11:00:00Z",
          diff: {
            client_id: "client-a",
            runs: { matched: 2, updated: 2, sample_ids: ["run-old"] },
            actions: { matched: 3, updated: 3, sample_ids: ["action-old"] },
          },
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
    getExternalAgentJobForRunMock.mockResolvedValue({
      job: {
        id: "job-ext-1",
        principal_id: "agent-ext-1",
        agent_profile_id: "buyer-assistant-v1",
        idempotency_key: "job-key-1",
        status: "accepted",
        requested_tool_id: "experiment.run_variant",
        requested_skill_id: "optimize-product-representation",
      },
      run: {},
      receipts: [],
      latest_receipt: null,
      verification: null,
    });
    verifyExternalAgentJobReceiptForRunMock.mockResolvedValue({
      valid: true,
      valid_signature: true,
      valid_payload: true,
      valid_scope: true,
      blockers: [],
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
      registry_ownership_source: "persistent",
      execution_adapters: [
        {
          id: "protocol.checkout.v1",
          channel_type: "protocol",
          permission_scope: "protocol.checkout:write",
          effect_class: "external_side_effect",
          allowed_capabilities: [],
          status: "planned",
          external_side_effects: true,
          writes_external_system: true,
          requires_operator_review: true,
          contract_intent: "readiness_boundary",
          receipt_contract: {
            required: true,
            receipt_type: "external_write_execution",
            required_fields: ["approval_receipt_id"],
            evidence_fields: ["checkout_session_id"],
            must_link_run_event: true,
          },
        },
      ],
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
          ownership_source: "registry_default",
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
          ownership_source: "registry_default",
          effect_class: "write_low_risk",
        },
      ],
      skill_ids_by_tool: {
        "experiment.run_variant": ["optimize-product-representation"],
        "protocol.ucp.checkout": ["execute-governed-protocol-commerce"],
      },
      declared_non_executable_skill_tools: ["protocol.ucp.checkout"],
      readiness_boundaries: [
        {
          tool_id: "protocol.ucp.checkout",
          skill_ids: ["execute-governed-protocol-commerce"],
          executable: false,
          adapter_id: "protocol.checkout.v1",
          contract_intent: "readiness_boundary",
          blocked_reason: "readiness_boundary_only_no_transaction_execution",
        },
      ],
      skill_tool_mappings: [
        {
          tool_id: "experiment.run_variant",
          skill_ids: ["optimize-product-representation"],
          executable: true,
        },
        {
          tool_id: "protocol.ucp.checkout",
          skill_ids: ["execute-governed-protocol-commerce"],
          executable: false,
          adapter_id: "protocol.checkout.v1",
          contract_intent: "readiness_boundary",
          blocked_reason: "readiness_boundary_only_no_transaction_execution",
        },
      ],
      skill_selection_by_tool: {
        "experiment.run_variant": {
          default_skill_id: "optimize-product-representation",
          candidate_skill_ids: ["optimize-product-representation"],
        },
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
        {
          id: "registry-audit-2",
          event_type: "registry_pin_backfill_applied",
          previous_registry_fingerprint: null,
          registry_fingerprint: "abcdef1234567890",
          registry_version: "agent-runtime-static-v1",
          source: "operator_backfill",
          created_at: "2026-05-02T11:00:00Z",
          diff: {
            client_id: "client-a",
            runs: { matched: 2, updated: 2, sample_ids: ["run-old"] },
            actions: { matched: 3, updated: 3, sample_ids: ["action-old"] },
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
    getAgentRuntimeRegistryReleaseMock.mockResolvedValue({
      release: {
        id: "abcdef1234567890",
        registry_version: "agent-runtime-static-v1",
        registry_fingerprint: "abcdef1234567890",
        hash_algorithm: "sha256",
        source: "static_code",
        status: "active",
        created_at: "2026-05-02T10:00:00Z",
        counts: {
          skills: 1,
          tools: 1,
          capabilities: 1,
          policy_profiles: 1,
        },
        payload: {
          registry_version: "agent-runtime-static-v1",
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
              input_schema: {},
              output_schema: {},
              side_effects: [],
              review_checklist: [],
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
              input_schema: {},
              output_schema: {},
              side_effects: [],
              review_checklist: [],
              owner_principal_id: "platform.commerce-optimization",
              steward_team: "commerce-optimization",
              effect_class: "write_low_risk",
            },
          ],
          skill_ids_by_tool: {
            "experiment.run_variant": ["optimize-product-representation"],
          },
          skill_selection_by_tool: {
            "experiment.run_variant": {
              default_skill_id: "optimize-product-representation",
              candidate_skill_ids: ["optimize-product-representation"],
            },
          },
          policy_profiles: [
            {
              id: "human_approval_required",
              name: "Human approval",
              description: "Require operator approval.",
              auto_effect_classes: [],
            },
          ],
        },
        audit_events: [
          {
            id: "registry-audit-1",
            event_type: "registry_changed",
            previous_registry_fingerprint: "1111111111111111",
            registry_fingerprint: "abcdef1234567890",
            registry_version: "agent-runtime-static-v1",
            source: "static_code",
            created_at: "2026-05-02T10:00:00Z",
            diff: {
              tools: {
                added: ["experiment.run_variant"],
                removed: [],
                changed: ["validation.review_readiness"],
              },
              skills: {
                added: ["optimize-product-representation"],
                removed: [],
                changed: [],
              },
              capabilities: {
                added: ["run_variant"],
                removed: [],
                changed: [],
              },
              policy_profiles: { added: [], removed: [], changed: [] },
              skill_ids_by_tool_changed: true,
            },
          },
          {
            id: "registry-approval-1",
            event_type: "registry_ownership_approved",
            previous_registry_fingerprint: null,
            registry_fingerprint: "abcdef1234567890",
            registry_version: "agent-runtime-static-v1",
            source: "operator_approval",
            created_at: "2026-05-02T10:05:00Z",
            diff: {
              tool_id: "experiment.run_variant",
              approval_receipt: {
                receipt_id: "receipt-12345678",
                receipt_type: "registry_ownership_approval",
                actor_user_id: "user-a",
                tool_id: "experiment.run_variant",
                registry_version: "agent-runtime-static-v1",
                registry_fingerprint: "abcdef1234567890",
                signature: "payload.signature",
                signature_algorithm: "hmac-sha256",
              },
            },
          },
        ],
      },
    });
    backfillAgentRuntimeRegistryPinsMock.mockResolvedValue({
      client_id: "client-a",
      dry_run: true,
      registry_version: "agent-runtime-static-v1",
      registry_fingerprint: "abcdef1234567890",
      runs: { matched: 2, updated: 0, sample_ids: ["run-old"] },
      actions: { matched: 3, updated: 0, sample_ids: ["action-old"] },
    });
    updateAgentRuntimeRegistryOwnershipMock.mockResolvedValue({
      dry_run: true,
      preflight: {
        allowed: true,
        requires_confirmation: true,
        risk_level: "medium",
        effect_class: "registry_metadata_change",
        tool_id: "experiment.run_variant",
        blockers: [],
        warnings: [],
        changed_fields: ["owner_principal_id", "steward_team"],
        rollback_guidance: "Re-apply previous ownership values.",
        summary: "Registry ownership update will create a new active registry release.",
      },
      ownership: {
        tool_id: "experiment.run_variant",
        owner_principal_id: "platform.commerce-optimization",
        steward_team: "commerce-optimization",
        source: "registry_default",
      },
    });
    verifyAgentRuntimeRegistryApprovalReceiptMock.mockResolvedValue({
      verification: {
        valid: true,
        valid_signature: true,
        valid_payload: true,
        valid_audit_event: true,
        blockers: [],
        receipt_payload: {},
        audit_event: {
          id: "registry-approval-1",
          event_type: "registry_ownership_approved",
          registry_fingerprint: "abcdef1234567890",
          registry_version: "agent-runtime-static-v1",
          source: "operator_approval",
          diff: {},
        },
      },
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

  it("sorts run selection by operator attention", async () => {
    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-calm",
          experiment_id: "exp-calm",
          status: "completed",
          state: "finished",
          budgets: {},
          requires_approval: false,
        },
        {
          id: "run-approval",
          experiment_id: "exp-appr",
          status: "planned",
          state: "variants_ready",
          budgets: {},
          requires_approval: true,
        },
        {
          id: "run-failed",
          experiment_id: "exp-fail",
          status: "failed",
          state: "validation_failed",
          budgets: {},
          requires_approval: false,
        },
        {
          id: "run-running",
          experiment_id: "exp-run",
          status: "running",
          state: "executing",
          budgets: {},
          requires_approval: false,
        },
      ],
    });

    render(<AgentRunsPage />);

    await waitFor(() => expect(getAgentRunMock).toHaveBeenCalledWith("run-failed", expect.anything(), "user-a"));
    const rows = await screen.findAllByRole("button", { name: /Experiment exp-/i });

    expect(rows[0]).toHaveTextContent(/exp-fail/i);
    expect(rows[0]).toHaveTextContent(/Critical/i);
    expect(rows[1]).toHaveTextContent(/exp-appr/i);
    expect(rows[1]).toHaveTextContent(/Approval/i);
    expect(rows[2]).toHaveTextContent(/exp-run/i);
    expect(rows[2]).toHaveTextContent(/Watching/i);
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
    await userEvent.click(screen.getByText(/More timeline filters/i));
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
    await waitFor(() => expect(screen.getByText("Intervention needed")).toBeInTheDocument());
    expect(screen.getAllByRole("button", { name: /Open interventions/i }).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Run is failed\. Start a new run or move to a healthy run state\./i)
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });

  it("surfaces a primary approve action above run details", async () => {
    const user = userEvent.setup();
    getAgentRunMock.mockResolvedValueOnce({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "planned",
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
          rationale: "Run candidate after review.",
          confidence: 0.7,
          inputs: {},
          outputs: {},
        },
      ],
    });

    render(<AgentRunsPage />);

    expect(await screen.findByText("Approve the next action")).toBeInTheDocument();
    expect(screen.getAllByText(/Run candidate after review/i).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /Approve next action/i }));

    await waitFor(() =>
      expect(decideAgentActionMock).toHaveBeenCalledWith(
        "act-1",
        { decision: "approve" },
        "user-a",
      ),
    );
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
    expect(screen.getByText(/Selection: publish copy revision/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Open variant/i }));
    expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");

    await userEvent.click(screen.getByRole("button", { name: /Open metric/i }));
    expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");
    expect(screen.queryByRole("button", { name: /Variant: variant-/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Metric: metric-/i })).not.toBeInTheDocument();

    getAgentRunEventsMock.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /Focus validation-linked/i }));
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    payload = getAgentRunEventsMock.mock.calls.at(-1)?.[1] as Record<string, unknown>;
    expect(payload.capability_name).toBe("request_synthetic_validation");

    await userEvent.click(screen.getByRole("button", { name: /^Open validation$/i }));
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

    expect(await screen.findByText(/Advanced runtime details/i)).toBeInTheDocument();
    expect(screen.getByText(/Review the next proposed action first/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Start$/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByText(/Advanced runtime details/i));

    expect(await screen.findByText(/Skills and tools/i)).toBeInTheDocument();
    expect(screen.getByText(/Allowed actions: 1/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Registry-write access/i })).not.toBeVisible();
    await userEvent.click(screen.getByText(/Show setup and audit controls/i));
    expect(
      screen.getByRole("heading", { name: /Registry-write access/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Apply needs access/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Registry-write access key/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Access key/i)).toBeInTheDocument();
    expect(screen.queryByText(/Bearer token saved/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Registry-write bearer token/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Action: run variant/i)).toBeInTheDocument();
    expect(screen.getByText(/Execute one candidate variant against saved evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Tool contract: agent-runtime-static-v1/)).not.toBeVisible();
    await userEvent.click(screen.getByText(/Show governance and artifacts/i));
    expect(screen.getAllByText(/Skill: optimize product representation/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Tool: experiment run variant/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Effect: write low risk/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Optimize Product Representation/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/experiment.run_variant/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/write_low_risk/i).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Compare the metric against control before promotion/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Tool contract: agent-runtime-static-v1/)).toBeInTheDocument();
    expect(screen.getByText(/Run registry: agent-runtime-static-v1/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Fingerprint: abcdef123456/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Registry source: static_code/i)).toBeInTheDocument();
    expect(screen.getByText(/Release status: active/i)).toBeInTheDocument();
    expect(screen.getByText(/Source: registry_default/i)).toBeInTheDocument();
    expect(screen.getByText(/Non-executable protocol intelligence/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /protocol.checkout.v1 · external_side_effect · planned · readiness_boundary · approval: external_write_execution/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/cannot create checkout, payment, cart, account, or browser transaction actions/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/protocol.ucp.checkout/i)).toBeInTheDocument();
    expect(screen.getByText(/readiness_boundary · protocol.checkout.v1/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Market research only, no transaction execution/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/^non-executable$/i).length).toBeGreaterThan(0);
    updateAgentRuntimeRegistryOwnershipMock
      .mockResolvedValueOnce({
        dry_run: true,
        preflight: {
          allowed: true,
          requires_confirmation: true,
          risk_level: "medium",
          effect_class: "registry_metadata_change",
          tool_id: "experiment.run_variant",
          blockers: [],
          warnings: [],
          changed_fields: ["owner_principal_id", "steward_team"],
          rollback_guidance: "Re-apply previous ownership values.",
          summary: "Registry ownership update will create a new active registry release.",
        },
        ownership: {
          tool_id: "experiment.run_variant",
          owner_principal_id: "platform.commerce-optimization",
          steward_team: "commerce-optimization",
          source: "registry_default",
        },
      })
      .mockResolvedValueOnce({
        dry_run: false,
        preflight: {
          allowed: true,
          requires_confirmation: true,
          risk_level: "medium",
          effect_class: "registry_metadata_change",
          tool_id: "experiment.run_variant",
          blockers: [],
          warnings: [],
          changed_fields: ["owner_principal_id", "steward_team"],
          rollback_guidance: "Re-apply previous ownership values.",
          summary: "Registry ownership update will create a new active registry release.",
        },
        ownership: {
          tool_id: "experiment.run_variant",
          owner_principal_id: "platform.growth",
          steward_team: "growth-ops",
          source: "operator_override",
        },
        approval_receipt: {
          receipt_id: "receipt-12345678",
          receipt_type: "registry_ownership_approval",
          actor_user_id: "user-a",
          tool_id: "experiment.run_variant",
          registry_version: "agent-runtime-static-v1",
          registry_fingerprint: "fedcba9876543210",
          signature: "payload.signature",
          signature_algorithm: "hmac-sha256",
        },
        registry_version: "agent-runtime-static-v1",
        registry_fingerprint: "fedcba9876543210",
        registry_status: "active",
      });
    await userEvent.clear(screen.getByLabelText(/Owner identity/i));
    await userEvent.type(screen.getByLabelText(/Owner identity/i), "platform.growth");
    await userEvent.clear(screen.getByLabelText(/Steward team/i));
    await userEvent.type(screen.getByLabelText(/Steward team/i), "growth-ops");
    await userEvent.click(screen.getByRole("button", { name: /Preview ownership change/i }));
    expect(updateAgentRuntimeRegistryOwnershipMock).toHaveBeenCalledWith(
      "experiment.run_variant",
      {
        owner_principal_id: "platform.growth",
        steward_team: "growth-ops",
        dry_run: true,
        preflight_confirmed: false,
      },
      "user-a",
    );
    expect(await screen.findByText(/Safety check: medium risk/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Apply ownership/i }));
    expect(updateAgentRuntimeRegistryOwnershipMock).toHaveBeenLastCalledWith(
      "experiment.run_variant",
      {
        owner_principal_id: "platform.growth",
        steward_team: "growth-ops",
        dry_run: false,
        preflight_confirmed: true,
      },
      "user-a",
    );
    expect(await screen.findByText(/Ownership saved with approval record receipt-/i)).toBeInTheDocument();
    expect(screen.queryByText(/Owner principal/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Registry releases/i)).toBeInTheDocument();
    expect(screen.getByText(/3 skills · 12 tools · 12 capabilities/i)).toBeInTheDocument();
    expect(screen.getByText(/Backfilled 2 runs · 3 actions/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /View details/i }));
    expect(getAgentRuntimeRegistryReleaseMock).toHaveBeenCalledWith(
      "abcdef1234567890",
      { audit_limit: 5 },
      "user-a",
    );
    expect(await screen.findByText(/Release detail/i)).toBeInTheDocument();
    expect(
      screen.getAllByText((_, node) =>
        Boolean(
          node?.textContent?.includes(
            "Release contains 1 skills, 1 tools, and 1 policy profiles",
          ),
        ),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/Payload contains/i)).not.toBeInTheDocument();
    expect(screen.getByText(/2 audit events are tied to this release/i)).toBeInTheDocument();
    expect(screen.getByText(/Release diff/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Tools: \+experiment.run_variant, ~validation.review_readiness/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Approval record: receipt-12345678/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Verify approval/i }));
    expect(verifyAgentRuntimeRegistryApprovalReceiptMock).toHaveBeenCalledWith({
      approval_receipt: {
        receipt_id: "receipt-12345678",
        receipt_type: "registry_ownership_approval",
        actor_user_id: "user-a",
        tool_id: "experiment.run_variant",
        registry_version: "agent-runtime-static-v1",
        registry_fingerprint: "abcdef1234567890",
        signature: "payload.signature",
        signature_algorithm: "hmac-sha256",
      },
      registry_fingerprint: "abcdef1234567890",
      audit_event_id: "registry-approval-1",
      require_audit_event: true,
    });
    expect(await screen.findByText(/Approval verified against the release audit trail/i)).toBeInTheDocument();
    expect(screen.queryByText(/Verify receipt/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Signed ownership receipt/i)).not.toBeInTheDocument();
    backfillAgentRuntimeRegistryPinsMock
      .mockResolvedValueOnce({
        client_id: "client-a",
        dry_run: true,
        registry_version: "agent-runtime-static-v1",
        registry_fingerprint: "abcdef1234567890",
        runs: { matched: 2, updated: 0, sample_ids: ["run-old"] },
        actions: { matched: 3, updated: 0, sample_ids: ["action-old"] },
      })
      .mockResolvedValueOnce({
        client_id: "client-a",
        dry_run: false,
        registry_version: "agent-runtime-static-v1",
        registry_fingerprint: "abcdef1234567890",
        runs: { matched: 2, updated: 2, sample_ids: ["run-old"] },
        actions: { matched: 3, updated: 3, sample_ids: ["action-old"] },
      });
    await userEvent.click(screen.getByRole("button", { name: /Preview missing pins/i }));
    expect(backfillAgentRuntimeRegistryPinsMock).toHaveBeenCalledWith(
      { dry_run: true, limit: 200 },
      "user-a",
    );
    expect(await screen.findByText(/Preview found 5 records/i)).toBeInTheDocument();
    expect(screen.getByText(/Missing pins: 2 runs · 3 actions/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Apply backfill/i }));
    expect(backfillAgentRuntimeRegistryPinsMock).toHaveBeenCalledWith(
      { dry_run: false, limit: 200 },
      "user-a",
    );
    expect(await screen.findByText(/Backfill updated 5 records/i)).toBeInTheDocument();
    expect(screen.getByText(/Registry release trail/i)).toBeInTheDocument();
    expect(screen.getByText(/tools: \+1 -0 ~0/i)).toBeInTheDocument();
    expect(screen.getByText(/Release: abcdef123456/i)).toBeInTheDocument();
    expect(screen.getByText(/Tool version: v1/i)).toBeInTheDocument();
    expect(screen.getByText(/Skill version: v1/i)).toBeInTheDocument();
    expect(screen.getByText(/Owner: platform\.commerce-optimization/i)).toBeInTheDocument();
    expect(screen.getByText(/Steward: commerce-optimization/i)).toBeInTheDocument();
    expect(listAgentRuntimeRegistryMock).toHaveBeenCalledWith("user-a");
    expect(listAgentRuntimeRegistryAuditMock).toHaveBeenCalledWith({ limit: 5 }, "user-a");
    expect(listAgentRuntimeRegistryReleasesMock).toHaveBeenCalledWith(
      { limit: 5 },
      "user-a",
    );
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

    await screen.findByText(/Selection: run variant/i);
    await userEvent.click(screen.getByRole("button", { name: /Approve selected/i }));

    expect(preflightAgentRunCommandMock).toHaveBeenCalledWith(
      "run-1",
      {
        command_type: "approve",
        action_id: "action-1",
        message: "Approve run variant",
      },
      "user-a",
    );
    await waitFor(() => expect(issueAgentRunCommandMock).toHaveBeenCalled());
    expect(issueAgentRunCommandMock).toHaveBeenCalledWith(
      "run-1",
      {
        command_type: "approve",
        action_id: "action-1",
        message: "Approve run variant",
      },
      "user-a",
    );
  });

  it("shows protocol discovery provenance for selected actions", async () => {
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "completed",
        state: "protocol_discovery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "auto_execute_safe",
        allowed_capabilities: ["discover_protocol_candidates"],
      },
      actions: [
        {
          id: "action-discovery",
          agent_run_id: "run-1",
          sequence: 1,
          status: "executed",
          capability_name: "discover_protocol_candidates",
          capability_version: "v1",
          rationale: "Find protocol candidates.",
          inputs: { query: "blue running shoe" },
          outputs: {
            summary: {
              count: 3,
              source_counts: {
                acp_product_feed: 2,
                ucp_local_metadata: 1,
              },
              readiness_summary: {
                status: "needs_review",
                score: 67,
                candidate_count: 3,
                ready_candidates: 1,
                warning_candidates: 1,
                blocked_candidates: 1,
                live_source_count: 2,
                local_source_count: 1,
                top_blockers: [
                  {
                    message: "Missing UCP business profile for brand.",
                  },
                ],
              },
            },
          },
          tool_id: "protocol.discover_candidates",
          skill_id: "discover-protocol-candidates",
          registry_version: "agent-runtime-static-v1",
          registry_fingerprint: "abcdef1234567890",
          tool_version: "v1",
          skill_version: "v1",
          effect_class: "read",
        },
      ],
    });

    render(<AgentRunsPage />);

    expect(await screen.findByText(/Discovery provenance/i)).toBeInTheDocument();
    expect(screen.getByText(/ACP product feed: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/UCP local metadata: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Protocol readiness/i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Needs review/i)).toBeInTheDocument();
    expect(screen.getByText(/Score: 67\/100/i)).toBeInTheDocument();
    expect(screen.getByText(/Candidates: 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Ready: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Review: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Blocked: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence: 2 live \/ 1 local/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Why: Missing UCP business profile for brand/i),
    ).toBeInTheDocument();
  });

  it("shows protocol readiness issues for selected actions", async () => {
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "completed",
        state: "protocol_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "auto_execute_safe",
        allowed_capabilities: ["check_protocol_readiness"],
      },
      actions: [
        {
          id: "action-readiness",
          agent_run_id: "run-1",
          sequence: 1,
          status: "executed",
          capability_name: "check_protocol_readiness",
          capability_version: "v1",
          rationale: "Check protocol readiness.",
          inputs: { product_id: "product-a", protocols: ["ucp"] },
          outputs: {
            protocol_readiness: [
              {
                protocol: "ucp",
                product_id: "product-a",
                issue_count: 1,
                ready: false,
                issues: [
                  {
                    field: "ucp_profile",
                    message: "Missing UCP business profile for brand.",
                  },
                ],
              },
            ],
          },
          tool_id: "protocol.readiness_check",
          skill_id: "discover-protocol-candidates",
          registry_version: "agent-runtime-static-v1",
          registry_fingerprint: "abcdef1234567890",
          tool_version: "v1",
          skill_version: "v1",
          effect_class: "read",
        },
      ],
    });

    render(<AgentRunsPage />);

    expect(
      await screen.findByText("Protocol readiness", { selector: ".panel__subheading" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Needs review/i)).toBeInTheDocument();
    expect(screen.getByText(/Score: 0\/100/i)).toBeInTheDocument();
    expect(screen.getByText(/Protocols: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Issues: 1/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Why: Missing UCP business profile for brand/i),
    ).toBeInTheDocument();
  });

  it("surfaces external-agent job context and verifies the latest receipt", async () => {
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-ext-1",
        experiment_id: "exp-1",
        status: "planned",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "auto_execute_safe",
        allowed_capabilities: ["run_variant"],
        principal_type: "external_agent",
        principal_id: "agent-ext-1",
        agent_profile_id: "buyer-assistant-v1",
      },
      actions: [],
    });
    getExternalAgentJobForRunMock.mockResolvedValue({
      job: {
        id: "job-ext-123456",
        principal_id: "agent-ext-1",
        agent_profile_id: "buyer-assistant-v1",
        idempotency_key: "retry-safe-key",
        status: "accepted",
        requested_tool_id: "experiment.run_variant",
        requested_skill_id: "optimize-product-representation",
      },
      run: {},
      receipts: [
        {
          receipt_type: "external_agent_job_accepted",
          status: "accepted",
          receipt_context_hash: "hash-123456789",
        },
      ],
      latest_receipt: {
        receipt_type: "external_agent_job_accepted",
        status: "accepted",
        receipt_context_hash: "hash-123456789",
      },
      verification: {
        valid: false,
        valid_signature: false,
        valid_payload: false,
        valid_scope: false,
        blockers: ["Receipt signature is invalid."],
      },
      activity_items: [
        {
          type: "run_event",
          subtype: "action_executed",
          capability_name: "check_protocol_readiness",
          domain_summary: {
            domain: "protocol_readiness",
            readiness_status: "needs_review",
            readiness_score: 0,
            protocol_count: 1,
            issue_count: 2,
            top_issues: [
              {
                field: "ucp_profile",
                message: "Missing UCP business profile for brand.",
              },
            ],
            receipt_id: "receipt-protocol-readiness",
          },
        },
      ],
    });

    render(<AgentRunsPage />);

    expect(await screen.findByText(/Job supervision/i)).toBeInTheDocument();
    expect(
      screen.getAllByText((_, node) =>
        Boolean(node?.textContent?.includes("Handoff status: accepted")),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/agent-ext-1/i)).not.toBeVisible();
    expect(screen.getByText(/retry-safe-key/i)).not.toBeVisible();
    expect(
      screen.getAllByText((_, node) =>
        Boolean(node?.textContent?.includes("Requested action: experiment run variant")),
      ).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, node) =>
        Boolean(node?.textContent?.includes("Skill: optimize product representation")),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/Latest handoff: external agent job accepted/i)).toBeInTheDocument();
    expect(screen.getByText(/Handoff needs check/i)).toBeInTheDocument();
    expect(screen.queryByText(/hash-123456789/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Show handoff details/i)).toBeInTheDocument();
    expect(screen.getByText(/agent-ext-1/i)).not.toBeVisible();
    expect(screen.getByText(/retry-safe-key/i)).not.toBeVisible();
    expect(
      screen.getAllByText((_, node) =>
        Boolean(node?.textContent?.includes("Job reference: job-ext-123456")),
      ).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, node) =>
        Boolean(node?.textContent?.includes("Handoff records: 1")),
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/external_agent_job_accepted/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/external machine principal/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Latest receipt/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Idempotency/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Handoff verification is invalid/i)).toBeInTheDocument();
    expect(screen.queryByText(/Receipt signature/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Protocol activity/i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Needs review/i)).toBeInTheDocument();
    expect(screen.getByText(/Score: 0\/100/i)).toBeInTheDocument();
    expect(screen.getByText(/Protocols: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Issues: 2/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Why: Missing UCP business profile for brand/i),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Verify handoff/i }));
    expect(verifyExternalAgentJobReceiptForRunMock).toHaveBeenCalledWith(
      "run-ext-1",
      "user-a",
    );
  });
});
