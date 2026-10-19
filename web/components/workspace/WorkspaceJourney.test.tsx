import React from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OperatorWorkspace } from "./OperatorWorkspace";
import { useOperatorWorkspace } from "./useOperatorWorkspace";
import { workspaceRequest, type WorkspaceHistory } from "../../lib/workspace";
import { listOperatorConversationCommands, sendOperatorConversationMessageStream, confirmOperatorConversationCommand } from "../../lib/api";
import type { OperatorConversationResponse, OperatorCommandProposal } from "../../lib/operatorConversationTypes";
vi.mock("../../lib/workspace", () => ({ workspaceRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ listOperatorConversationCommands: vi.fn(), sendOperatorConversationMessageStream: vi.fn(), confirmOperatorConversationCommand: vi.fn() }));
vi.mock("./WorkspaceAccount", () => ({ WorkspaceAccount: () => <div>Account</div> }));
const request = vi.mocked(workspaceRequest);
const commands = vi.mocked(listOperatorConversationCommands);
const send = vi.mocked(sendOperatorConversationMessageStream);
const confirm = vi.mocked(confirmOperatorConversationCommand);
const action = { id: "action-1", sequence: 1, capability_name: "run_control_baseline", status: "proposed" };
const answer = {
  session_id: "session", run_id: "run", answer: "Recorded comparison remains partial.",
  intent: "explain_run", warnings: [{ code: "partial", message: "Validation outcome is unknown; investigate existing evidence." }],
  snapshot: { digest: "a".repeat(64), fetched_at: "2026-10-14T10:00:00Z" },
  freshness: { state: "stale", data_state: "partial", snapshot_cursor: "original-cursor" },
  verified_facts: [{ id: "fact", text: "Original evidence fact", category: "validation", source: "/validation?job_id=original", provenance: { record_type: "validation_job" } }],
  evidence: [{ kind: "validation", record: { id: "original-job" }, href: "/validation?job_id=original" }],
  recommendation: null, navigation: [],
} as unknown as OperatorConversationResponse;
const latest = { session_id: "session", run_id: "run", run: { id: "run", status: "planned" }, actions: [action], events: [], proposals: [], receipt: null, has_more: false,
  turns: [{ id: 10, speaker: "agent", content: answer.answer, metadata: { operator_response: answer } }], turns_has_more: true, turns_before_id: 10 } as unknown as WorkspaceHistory;
function Journey({ tenant = "tenant", human = "human" }) {
  const workspace = useOperatorWorkspace(tenant, human);
  return <OperatorWorkspace workspace={workspace} runs={[]} userId={human} />;
}
beforeEach(() => {
  window.history.replaceState(null, "", "/?conversation=session");
  window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  request.mockReset(); send.mockReset(); confirm.mockReset(); commands.mockReset();
  request.mockImplementation(async (_client, payload) => payload.operation === "list" ? { conversations: [{ session_id: "session", preview: "First objective" }, { session_id: "second", preview: "Second objective" }], has_more: false } : payload.session_id === "second" ? { ...latest, session_id: "second", run_id: null, run: null, turns: [], turns_has_more: false } : latest);
  commands.mockResolvedValue({ run_id: "run", records: [], page: { has_more: false, next_cursor: null }, total_count: 0 } as never);
});
describe("live workspace combined behavior", () => {
  it("keeps history, provenance and drafts across older loading, refresh, inspector and navigation", async () => {
    const user = userEvent.setup(); render(<Journey />);
    const composer = await screen.findByLabelText("Ask about the selected run");
    await user.type(composer, "My next question");
    request.mockResolvedValueOnce({ ...latest, turns: [{ id: 1, speaker: "user", content: "Earlier objective", metadata: {} }], turns_has_more: false, turns_before_id: null });
    await user.click(screen.getByRole("button", { name: "Load older messages" }));
    request.mockResolvedValueOnce({ ...latest, run: { ...latest.run!, status: "paused" } });
    await user.click(screen.getByRole("button", { name: "Refresh run progress" }));
    expect(await screen.findByText("Run status: paused")).toBeInTheDocument();
    expect(screen.getByText("Earlier objective").compareDocumentPosition(screen.getByText(answer.answer)) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByText(answer.answer)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Load older messages" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Validation outcome is unknown");
    expect(screen.queryByRole("button", { name: /Retry/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open work details" }));
    const details = screen.getByLabelText("Work details");
    expect(within(details).getByLabelText("Verified answer details")).toHaveTextContent("stale · Data partial · Cursor original-cur");
    await user.click(within(details).getByText("Verified facts (1)"));
    expect(within(details).getByRole("link", { name: "Source" })).toHaveAttribute("href", "/validation?job_id=original");
    await user.click(screen.getByRole("button", { name: "Close work details" }));
    await user.click(screen.getByRole("button", { name: /Second objective/ }));
    expect(await screen.findByLabelText("Your objective")).toHaveValue("");
    await user.type(screen.getByLabelText("Your objective"), "Another draft");
    await user.click(screen.getByRole("button", { name: /First objective/ }));
    expect(await screen.findByLabelText("Ask about the selected run")).toHaveValue("My next question");
    await user.click(screen.getByRole("button", { name: /Second objective/ }));
    expect(await screen.findByLabelText("Your objective")).toHaveValue("Another draft");
  });
  it("requests review of one exact action without confirming or executing it", async () => {
    const user = userEvent.setup();
    const proposal = { proposal_id: "review-1", proposal_digest: "b".repeat(64), command_type: "approve", expires_at: "2099-01-01", parameters: { action_id: "action-1", review: { normalized_inputs: { experiment_id: "exp-1" }, capability_name: "run_control_baseline", side_effects: ["Measure the control"], review_checklist: ["Check scope"], inputs_hash: "input-digest" } }, consequences: ["Approval executes nothing"], source: { active_graph_revision: 1 } } as unknown as OperatorCommandProposal;
    send.mockResolvedValue({ ...answer, intent: "approve_action", command_proposal: proposal });
    render(<Journey />);
    await user.click(await screen.findByRole("button", { name: /Review action 1/ }));
    expect(send).toHaveBeenCalledWith("run", "Approve action action-1", "session", expect.any(Object), expect.any(AbortSignal));
    expect(await screen.findByRole("button", { name: "Confirm approve" })).toBeInTheDocument();
    expect(screen.getByText(/experiment_id/)).toHaveTextContent("exp-1");
    expect(confirm).not.toHaveBeenCalled();
    confirm.mockRejectedValueOnce(new Error("Scope changed; request a fresh review"));
    await user.click(screen.getByRole("button", { name: "Confirm approve" }));
    expect(confirm).toHaveBeenCalledWith("run", "review-1", "b".repeat(64), "approve", "action-1");
    expect(await screen.findByText("Scope changed; request a fresh review")).toBeInTheDocument();
  });
  it("discards late confirmations after navigating away from the conversation", async () => {
    const user = userEvent.setup();
    const proposal = { proposal_id: "pause", proposal_digest: "b".repeat(64), command_type: "pause", parameters: {}, expires_at: "2099-01-01", source: { active_graph_revision: 1 }, consequences: [] } as unknown as OperatorCommandProposal;
    commands.mockResolvedValue({ run_id: "run", records: [{ proposal, receipt: null }], page: {}, total_count: 1 } as never);
    let finish!: (value: never) => void;
    confirm.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    render(<Journey />);
    await user.click(await screen.findByRole("button", { name: "Confirm pause" }));
    await user.click(screen.getByRole("button", { name: /Second objective/ }));
    const reads = request.mock.calls.length;
    await act(async () => { finish({ receipt: { proposal_id: "pause" } } as never); });
    expect(request.mock.calls).toHaveLength(reads);
    expect(screen.queryByLabelText("Pause receipt")).not.toBeInTheDocument();
  });
  it("contains mobile overlay focus and restores it on Escape", async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    const user = userEvent.setup(); render(<Journey />);
    const opener = await screen.findByRole("button", { name: "Open navigation" });
    await user.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Work conversations" });
    expect(screen.getByLabelText("Conversation workspace")).toHaveAttribute("inert");
    expect(dialog).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(within(dialog).getByRole("button", { name: "Dark appearance" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(opener).toHaveFocus();
    expect(screen.getByLabelText("Work conversations")).toHaveAttribute("inert");
    await user.click(screen.getByRole("button", { name: "Open work details" }));
    expect(screen.getByRole("dialog", { name: "Work details" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Open work details" })).toHaveFocus();
  });
});
