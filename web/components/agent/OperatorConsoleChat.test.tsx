import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmOperatorConversationCommand,
  listOperatorConversationCommands,
  sendOperatorConversationMessageStream,
} from "../../lib/api";
import type { OperatorConversationResponse } from "../../lib/operatorConversationTypes";
import { OperatorConsoleChat } from "./OperatorConsoleChat";

vi.mock("../../lib/api", () => ({
  confirmOperatorConversationCommand: vi.fn(),
  listOperatorConversationCommands: vi.fn(),
  sendOperatorConversationMessageStream: vi.fn(),
}));

const sendMessage = vi.mocked(sendOperatorConversationMessageStream);
const confirmCommand = vi.mocked(confirmOperatorConversationCommand);
const listCommands = vi.mocked(listOperatorConversationCommands);

const run = {
  id: "run-1",
  client_id: "client-1",
  experiment_id: "exp-1",
  status: "running",
  state: "active",
  run_mode: "observe",
};

function response(overrides: Partial<OperatorConversationResponse> = {}) {
  return {
    contract: "operator-conversation-response.v1",
    session_id: "session-1",
    run_id: "run-1",
    intent: "explain_run",
    answer: "The verified run is active.",
    verified_facts: [
      {
        id: "run.lifecycle",
        category: "run",
        text: "Run is active.",
        source: "/runs?run_id=run-1",
        provenance: { record_type: "agent_run", record_id: "run-1" },
      },
    ],
    inference: { kind: "validated_fact_selection", model_prose_exposed: false },
    recommendation: null,
    evidence: [],
    navigation: [{ label: "Run workspace", href: "/runs?run_id=run-1" }],
    freshness: {
      state: "current",
      data_state: "complete",
      snapshot_cursor: "cursor-1",
      latest_cursor: "cursor-1",
      snapshot_digest: "a".repeat(64),
    },
    warnings: [],
    snapshot: {
      contract: "operator-execution-snapshot.v1",
      digest: "a".repeat(64),
      fetched_at: "2026-09-27T10:00:00Z",
      scope: { tenant_id: "client-1", principal_id: "human:user-1" },
      run,
      actions: [],
      events: [],
      event_page: { after_cursor: "cursor-1" },
      approvals: [],
      effects: [],
      experiment: null,
      validation_jobs: [],
      completion: { authoritative_decision: null },
      completeness: { events_complete: true },
    },
    read_only: true,
    ...overrides,
  } satisfies OperatorConversationResponse;
}

const baseProps = {
  run,
  actions: [],
  events: [],
  userId: "user-1",
  selectedAction: null,
  nextRecommendedAction: { action: null, guardrails: [], hint: "" },
};

function commandProposal(proposalId: string) {
  return {
    contract: "workflow.operator-command-proposal.v1" as const,
    proposal_id: proposalId,
    proposal_digest: "b".repeat(64),
    tenant_id: "client-1",
    principal_id: "human:user-1",
    run_id: "run-1",
    command_type: "pause" as const,
    parameters: {},
    source: {
      active_graph_revision: 2,
      run_status: "running",
      run_state: "active",
      snapshot_digest: "a".repeat(64),
    },
    preflight: {
      digest: "c".repeat(64),
      result: {
        allowed: true,
        risk_level: "low",
        blockers: [],
        warnings: [],
        summary: "Pause is available.",
      },
    },
    idempotency_key: `operator-pause:${proposalId}`,
    issued_at: "2026-09-30T10:00:00Z",
    expires_at: "2020-09-30T10:05:00Z",
    consequences: ["Autonomous progress stops."],
  };
}

describe("OperatorConsoleChat", () => {
  beforeEach(() => {
    sendMessage.mockReset();
    confirmCommand.mockReset();
    listCommands.mockReset();
    listCommands.mockResolvedValue({
      contract: "operator-command-record-list.v1",
      run_id: "run-1",
      records: [],
      count: 0,
      total_count: 0,
      page: {
        limit: 50,
        returned_count: 0,
        total_count: 0,
        has_more: false,
        next_cursor: null,
      },
      completeness: {
        state: "complete",
        included_count: 0,
        total_count: 0,
        reason: null,
      },
    });
    sendMessage.mockImplementation(async (_runId, _message, _sessionId, handlers) => {
      handlers.onStatus?.("building_verified_snapshot");
      handlers.onDelta?.("The verified run is active.");
      return response();
    });
  });

  it("sends free-form questions to the run-grounded streaming gateway", async () => {
    const user = userEvent.setup();
    render(<OperatorConsoleChat {...baseProps} />);

    await user.type(
      screen.getByLabelText(/Ask about the selected run/i),
      "What evidence supports this result?",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("The verified run is active.")).toBeInTheDocument();
    expect(sendMessage).toHaveBeenCalledWith(
      "run-1",
      "What evidence supports this result?",
      null,
      expect.any(Object),
      expect.any(AbortSignal),
    );
    expect(screen.getByText(/Evidence view aaaaaaaaaaaa · current · Data complete · Cursor cursor-1/i)).toBeInTheDocument();
    await user.click(screen.getByText(/Verified facts/i));
    expect(screen.getByRole("link", { name: "Source" })).toHaveAttribute(
      "href",
      "/runs?run_id=run-1",
    );
    expect(screen.getByRole("link", { name: "Run workspace" })).toHaveAttribute(
      "href",
      "/runs?run_id=run-1",
    );
  });

  it("routes quick prompts through the same gateway and carries the session", async () => {
    const user = userEvent.setup();
    render(<OperatorConsoleChat {...baseProps} />);

    await user.click(screen.getByRole("button", { name: "Explain run" }));
    await screen.findByText("The verified run is active.");
    await user.click(screen.getByRole("button", { name: "Summarize failures" }));

    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(2));
    expect(sendMessage.mock.calls[1][2]).toBe("session-1");
  });

  it("does not expose approval controls or pause without a server proposal", () => {
    render(<OperatorConsoleChat {...baseProps} />);

    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pause/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retry/i })).not.toBeInTheDocument();
    expect(screen.getByText(/require a separate confirmation/i)).toBeInTheDocument();
  });

  it("requires exact cancel confirmation and shows the terminal receipt", async () => {
    const user = userEvent.setup();
    const proposal = {
      ...commandProposal("proposal-cancel"),
      contract: "workflow.operator-command-proposal.v3" as const,
      command_type: "cancel" as const,
      predicted_run_status: "canceled" as const,
      source: { ...commandProposal("proposal-cancel").source, run_mode: "auto_execute_safe" as const },
      consequences: ["Cancellation is terminal: this run cannot be resumed.", "Completed effects are preserved."],
    };
    sendMessage.mockResolvedValueOnce(response({ intent: "cancel_run", interaction_mode: "proposal", command_proposal: proposal }));
    const receipt = {
      contract: "workflow.operator-command-receipt.v3" as const,
      receipt_id: "receipt-cancel", proposal_id: proposal.proposal_id,
      proposal_digest: proposal.proposal_digest, run_id: run.id,
      command_type: "cancel" as const, outcome: "canceled" as const,
      resulting_run_status: "canceled" as const, run_mode: "auto_execute_safe" as const,
      event_ids: { command: "cancel-command", lifecycle: "cancel-lifecycle", stopping_condition: null },
      acknowledgement: "control_plane_canceled" as const,
      propagation_state: "runtime_propagation_not_certified" as const,
      completed_at: "2026-10-03T10:00:00Z", receipt_digest: "d".repeat(64),
    };
    confirmCommand.mockResolvedValueOnce({ contract: "operator-command-confirmation.v1", run_id: run.id,
      proposal_id: proposal.proposal_id, command: {}, run: { ...run, status: "canceled" }, receipt });
    render(<OperatorConsoleChat {...baseProps} />);
    await user.type(screen.getByLabelText(/Ask about the selected run/i), "Cancel this run");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByRole("region", { name: "Cancel proposal" })).toBeInTheDocument();
    expect(screen.getByText(/Cancellation is terminal/i)).toBeInTheDocument();
    expect(confirmCommand).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm cancel" }));
    await waitFor(() => expect(confirmCommand).toHaveBeenCalledWith(run.id, proposal.proposal_id, proposal.proposal_digest, "cancel"));
    expect(await screen.findByText(/Cancellation acknowledged/i)).toBeInTheDocument();
    expect(screen.getByText(/Recorded outcome: canceled/i)).toBeInTheDocument();
    expect(screen.queryByText(/Pause acknowledged/i)).not.toBeInTheDocument();
  });

  it("requires an explicit click before confirming the exact pause proposal", async () => {
    const user = userEvent.setup();
    const proposal = {
      contract: "workflow.operator-command-proposal.v1" as const,
      proposal_id: "proposal-1",
      proposal_digest: "b".repeat(64),
      tenant_id: "client-1",
      principal_id: "human:user-1",
      run_id: "run-1",
      command_type: "pause" as const,
      parameters: {},
      source: {
        active_graph_revision: 2,
        run_status: "running",
        run_state: "active",
        snapshot_digest: "a".repeat(64),
      },
      preflight: {
        digest: "c".repeat(64),
        result: {
          allowed: true,
          risk_level: "low",
          blockers: [],
          warnings: [],
          summary: "Pause is available.",
        },
      },
      idempotency_key: "operator-pause:proposal-1",
      issued_at: "2026-09-30T10:00:00Z",
      expires_at: "2026-09-30T10:05:00Z",
      consequences: ["Autonomous progress stops.", "State is preserved."],
    };
    sendMessage.mockResolvedValueOnce(
      response({
        contract: "operator-conversation-response.v2",
        intent: "pause_run",
        interaction_mode: "proposal",
        command_proposal: proposal,
      }),
    );
    confirmCommand.mockResolvedValueOnce({
      contract: "operator-command-confirmation.v1",
      run_id: "run-1",
      proposal_id: "proposal-1",
      command: {},
      run: { ...run, status: "paused" },
      receipt: {
        contract: "workflow.operator-command-receipt.v1",
        receipt_id: "receipt-1",
        proposal_id: "proposal-1",
        proposal_digest: "b".repeat(64),
        run_id: "run-1",
        command_type: "pause",
        outcome: "paused",
        resulting_run_status: "paused",
        event_ids: { command: "event-1", lifecycle: "event-2" },
        acknowledgement: "control_plane_paused",
        propagation_state: "runtime_propagation_not_certified",
        completed_at: "2026-09-30T10:01:00Z",
        receipt_digest: "d".repeat(64),
        replayed: false,
      },
    });
    const onCommitted = vi.fn();
    render(<OperatorConsoleChat {...baseProps} onCommandCommitted={onCommitted} />);

    await user.type(screen.getByLabelText(/Ask about the selected run/i), "Pause this run");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByRole("button", { name: "Confirm pause" })).toBeInTheDocument();
    expect(confirmCommand).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm pause" }));

    await waitFor(() => expect(confirmCommand).toHaveBeenCalledOnce());
    expect(confirmCommand).toHaveBeenCalledWith("run-1", "proposal-1", "b".repeat(64), "pause");
    expect(await screen.findByLabelText("Pause receipt")).toHaveTextContent(
      /runtime propagation is not independently certified/i,
    );
    expect(onCommitted).toHaveBeenCalledOnce();
  });

  it.each([false, true])("requires exact resume confirmation and fences navigation during history refresh (%s)", async (navigateDuringRefresh) => {
    const user = userEvent.setup();
    const proposal = { ...commandProposal("resume-proposal"), contract: "workflow.operator-command-proposal.v2" as const,
      command_type: "resume" as const, expires_at: "2099-01-01T00:00:00Z", source: { ...commandProposal("resume-proposal").source, run_status: "paused", run_mode: "plan_only" as const },
      predicted_run_status: "planned" as const, consequences: ["Plan-only remains non-executing."] };
    const receipt = { contract: "workflow.operator-command-receipt.v2" as const, receipt_id: "resume-receipt",
      proposal_id: "resume-proposal", proposal_digest: proposal.proposal_digest, run_id: "run-1", command_type: "resume" as const,
      outcome: "planned" as const, resulting_run_status: "planned" as const, event_ids: { command: "resume-event", lifecycle: "resumed-event" },
      acknowledgement: "control_plane_resume_eligible" as const, propagation_state: "runtime_propagation_not_certified" as const,
      completed_at: new Date().toISOString(), receipt_digest: "e".repeat(64) };
    listCommands.mockResolvedValue({ contract: "operator-command-record-list.v1", run_id: "run-1", records: [{ proposal, receipt: null }],
      count: 1, total_count: 1, page: { limit: 50, returned_count: 1, total_count: 1, has_more: false, next_cursor: null },
      completeness: { state: "complete", included_count: 1, total_count: 1, reason: null } });
    confirmCommand.mockResolvedValue({ contract: "operator-command-confirmation.v1", run_id: "run-1", proposal_id: "resume-proposal", command: {}, receipt, run: { ...run, status: "planned" } });
    const onCommitted = vi.fn();
    const view = render(<OperatorConsoleChat {...baseProps} run={{ ...run, status: "paused" }} onCommandCommitted={onCommitted} />);
    const button = await screen.findByRole("button", { name: "Confirm resume" });
    expect(confirmCommand).not.toHaveBeenCalled();
    expect(screen.getByText("Plan-only remains non-executing.")).toBeInTheDocument();
    let finishHistory: () => void = () => undefined;
    if (navigateDuringRefresh) {
      listCommands.mockImplementationOnce(() => new Promise((resolve) => {
        finishHistory = () => resolve({ contract: "operator-command-record-list.v1", run_id: "run-1", records: [{ proposal, receipt }], count: 1, total_count: 1,
          page: { limit: 50, returned_count: 1, total_count: 1, has_more: false, next_cursor: null }, completeness: { state: "complete", included_count: 1, total_count: 1, reason: null } });
      }));
    }
    await user.click(button);
    expect(confirmCommand).toHaveBeenCalledWith("run-1", "resume-proposal", proposal.proposal_digest, "resume");
    expect(await screen.findByLabelText("Resume receipt")).toHaveTextContent("Recorded outcome: planned");
    if (navigateDuringRefresh) {
      view.rerender(<OperatorConsoleChat {...baseProps} run={{ ...run, id: "run-2" }} onCommandCommitted={onCommitted} />);
      finishHistory();
      await waitFor(() => expect(screen.queryByLabelText("Resume receipt")).not.toBeInTheDocument());
      expect(onCommitted).not.toHaveBeenCalled();
    } else {
      await waitFor(() => expect(onCommitted).toHaveBeenCalledOnce());
    }
  });

  it("restores a durable proposal without an in-memory conversation response", async () => {
    const user = userEvent.setup();
    const proposal = {
      contract: "workflow.operator-command-proposal.v1" as const,
      proposal_id: "proposal-durable",
      proposal_digest: "b".repeat(64),
      tenant_id: "client-1",
      principal_id: "human:user-1",
      run_id: "run-1",
      command_type: "pause" as const,
      parameters: {},
      source: {
        active_graph_revision: 2,
        run_status: "running",
        run_state: "active",
        snapshot_digest: "a".repeat(64),
      },
      preflight: {
        digest: "c".repeat(64),
        result: {
          allowed: true,
          risk_level: "low",
          blockers: [],
          warnings: [],
          summary: "Pause is available.",
        },
      },
      idempotency_key: "operator-pause:proposal-durable",
      issued_at: "2026-09-30T10:00:00Z",
      expires_at: "2099-09-30T10:05:00Z",
      consequences: ["Autonomous progress stops.", "State is preserved."],
    };
    listCommands.mockResolvedValueOnce({
      contract: "operator-command-record-list.v1",
      run_id: "run-1",
      records: [{ proposal, receipt: null }],
      count: 1,
      total_count: 1,
      page: {
        limit: 50,
        returned_count: 1,
        total_count: 1,
        has_more: false,
        next_cursor: null,
      },
      completeness: {
        state: "complete",
        included_count: 1,
        total_count: 1,
        reason: null,
      },
    });
    render(<OperatorConsoleChat {...baseProps} />);

    expect((await screen.findAllByText(/proposal-dur/i)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Confirm pause" })).toBeInTheDocument();
    await user.click(screen.getByText(/Durable command history/i));
    expect(screen.getByText(/awaiting confirmation/i)).toBeInTheDocument();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("exposes incomplete history and loads older durable command evidence", async () => {
    const user = userEvent.setup();
    listCommands
      .mockResolvedValueOnce({
        contract: "operator-command-record-list.v1",
        run_id: "run-1",
        records: [{ proposal: commandProposal("proposal-new"), receipt: null }],
        count: 1,
        total_count: 2,
        page: {
          limit: 1,
          returned_count: 1,
          total_count: 2,
          has_more: true,
          next_cursor: "older-page",
        },
        completeness: {
          state: "partial",
          included_count: 1,
          total_count: 2,
          reason: "additional_pages_available",
        },
      })
      .mockResolvedValueOnce({
        contract: "operator-command-record-list.v1",
        run_id: "run-1",
        records: [{ proposal: commandProposal("proposal-old"), receipt: null }],
        count: 1,
        total_count: 2,
        page: {
          limit: 1,
          returned_count: 1,
          total_count: 2,
          has_more: false,
          next_cursor: null,
        },
        completeness: {
          state: "partial",
          included_count: 1,
          total_count: 2,
          reason: "continuation_page",
        },
      });

    render(<OperatorConsoleChat {...baseProps} />);

    expect(await screen.findByText(/Showing the newest 1 of 2 durable commands/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load older commands" }));
    await user.click(await screen.findByText(/Durable command history \(2\)/i));
    expect(screen.getByText(/proposal-old/i)).toBeInTheDocument();
    expect(listCommands).toHaveBeenLastCalledWith("run-1", {
      cursor: "older-page",
      signal: undefined,
    });
    expect(screen.queryByText(/Showing the newest 1 of 2 durable commands/i)).not.toBeInTheDocument();
  });

  it("shows stale-snapshot warnings and structured recommendations", async () => {
    const user = userEvent.setup();
    sendMessage.mockResolvedValueOnce(
      response({
        freshness: {
          state: "stale",
          data_state: "partial",
          snapshot_cursor: "cursor-1",
          latest_cursor: "cursor-2",
          snapshot_digest: "a".repeat(64),
        },
        warnings: [
          {
            code: "snapshot_changed_during_generation",
            message: "The run changed while this answer was generated.",
          },
        ],
        recommendation: {
          kind: "operator_guidance",
          text: "Review the first unresolved blocker.",
          href: "/interventions?run_id=run-1",
        },
      }),
    );
    render(<OperatorConsoleChat {...baseProps} />);

    await user.click(screen.getByRole("button", { name: "Recommend next step" }));

    expect(await screen.findByText(/Evidence view aaaaaaaaaaaa · stale · Data partial/i)).toBeInTheDocument();
    expect(screen.getByText(/run changed while this answer was generated/i)).toBeInTheDocument();
    expect(screen.getByText(/Review the first unresolved blocker/i)).toBeInTheDocument();
  });

  it("renders structured evidence with a server-scoped source link", async () => {
    const user = userEvent.setup();
    sendMessage.mockResolvedValueOnce(
      response({
        evidence: [
          {
            kind: "completion_evidence",
            record: {
              evidence_id: "evidence-1",
              source_type: "validation",
              source_id: "validation-1",
            },
            href: "/evidence?run_id=run-1&experiment_id=exp-1&evidence_id=evidence-1",
          },
        ],
      }),
    );
    render(<OperatorConsoleChat {...baseProps} />);

    await user.type(
      screen.getByLabelText(/Ask about the selected run/i),
      "Show the evidence records",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));
    await user.click(await screen.findByText(/Evidence records \(1\)/i));

    expect(screen.getByText("evidence-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open evidence" })).toHaveAttribute(
      "href",
      "/evidence?run_id=run-1&experiment_id=exp-1&evidence_id=evidence-1",
    );
  });

  it("cancels and discards a late response when the selected run changes", async () => {
    const user = userEvent.setup();
    let resolveRequest: (value: OperatorConversationResponse) => void = () => undefined;
    sendMessage.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const view = render(<OperatorConsoleChat {...baseProps} />);

    await user.click(screen.getByRole("button", { name: "Explain run" }));
    view.rerender(
      <OperatorConsoleChat
        {...baseProps}
        run={{ ...run, id: "run-2" }}
      />,
    );
    resolveRequest(response());

    await waitFor(() => {
      expect(screen.queryByText("The verified run is active.")).not.toBeInTheDocument();
    });
    expect(screen.getByText(/server-verified run context/i)).toBeInTheDocument();
  });

  it("discards a late command-history failure after run navigation", async () => {
    let rejectOldRequest: (reason: Error) => void = () => undefined;
    listCommands
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectOldRequest = reject;
          }),
      )
      .mockResolvedValueOnce({
        contract: "operator-command-record-list.v1",
        run_id: "run-2",
        records: [],
        count: 0,
        total_count: 0,
        page: {
          limit: 50,
          returned_count: 0,
          total_count: 0,
          has_more: false,
          next_cursor: null,
        },
        completeness: {
          state: "complete",
          included_count: 0,
          total_count: 0,
          reason: null,
        },
      });
    const view = render(<OperatorConsoleChat {...baseProps} />);

    view.rerender(<OperatorConsoleChat {...baseProps} run={{ ...run, id: "run-2" }} />);
    await waitFor(() => expect(listCommands).toHaveBeenCalledTimes(2));
    rejectOldRequest(new Error("late run-1 failure"));

    await waitFor(() => {
      expect(screen.queryByText(/late run-1 failure/i)).not.toBeInTheDocument();
    });
    expect(screen.getByText(/No conversational operator commands/i)).toBeInTheDocument();
  });
});
