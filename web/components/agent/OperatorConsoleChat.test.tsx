import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { sendOperatorConversationMessageStream } from "../../lib/api";
import type { OperatorConversationResponse } from "../../lib/operatorConversationTypes";
import { OperatorConsoleChat } from "./OperatorConsoleChat";

vi.mock("../../lib/api", () => ({
  sendOperatorConversationMessageStream: vi.fn(),
}));

const sendMessage = vi.mocked(sendOperatorConversationMessageStream);

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

describe("OperatorConsoleChat", () => {
  beforeEach(() => {
    sendMessage.mockReset();
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

  it("does not expose execution or approval controls in conversation", () => {
    render(<OperatorConsoleChat {...baseProps} />);

    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pause/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retry/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Conversation cannot change execution state/i)).toBeInTheDocument();
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
});
