import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./page";
const api = vi.hoisted(() => ({ listAgentRuns: vi.fn(), clientId: "tenant-1", userId: "human" as string | null }));
vi.mock("../lib/auth", () => ({ useAppUser: () => ({ user: api.userId ? { id: api.userId } : null }) }));
vi.mock("../components/tenant/TenantProvider", () => ({ useTenant: () => ({ clientId: api.clientId }) }));
vi.mock("../components/layout/Sidebar", () => ({ Sidebar: ({ onNewConversation }: { onNewConversation: () => void }) => <button onClick={onNewConversation}>New chat</button> }));
vi.mock("../lib/api", () => ({ listAgentRuns: api.listAgentRuns }));
vi.mock("../components/agent/OperatorConsoleChat", () => ({ OperatorConsoleChat: ({ initialSessionId, initialMessages }: { initialSessionId: string; initialMessages: Array<{ content: string }> }) => <section aria-label="Run supervision">{initialSessionId}{initialMessages.map((m,i) => <p key={i}>{m.content}</p>)}</section> }));
const proposal = { proposal_id: "proposal", proposal_digest: "a".repeat(64), session_id: "session", expires_at: "2099-01-01T00:00:00Z",
  preflight: { scope: { product: "Product A", experiment: "Experiment A" }, execution_posture: "Every action needs its own approval", parameters: { experiment_id: "experiment-1", objective: { goal: "Improve product performance" }, budgets: { max_actions: 12, max_variant_runs: 1, max_cost_usd: 5 } }, plan: [{ capability_name: "run_control_baseline", rationale: "Measure baseline" }] } };
let created = false;
const originalFetch = global.fetch;
function history() { return { session_id: "session", run_id: created ? "run-1" : null, run: created ? { id: "run-1", status: "planned" } : null,
  actions: [], events: [], proposals: [proposal], turns: [{ id: 1, speaker: "user", content: "Improve product performance", metadata: {} }],
  receipt: created ? { receipt_id: "receipt", receipt_digest: "b".repeat(64), run_id: "run-1" } : null }; }
beforeEach(() => {
  created = false; api.userId = "human"; api.clientId = "tenant-1"; window.history.replaceState(null, "", "/");
  api.listAgentRuns.mockResolvedValue({ runs: [] });
  global.fetch = vi.fn().mockImplementation(async (_url, init) => {
    const body = JSON.parse(String(init.body));
    if (body.operation === "list") return new Response(JSON.stringify({ conversations: [], has_more: false }));
    if (body.operation === "read") return new Response(JSON.stringify(history()));
    if (body.operation === "confirm") { created = true; return new Response(JSON.stringify({ session_id: "session", run_id: "run-1" })); }
    return new Response(JSON.stringify({ state: "proposed", session_id: "session", run_id: null, proposal }));
  });
});
afterEach(() => { global.fetch = originalFetch; });
describe("primary conversation workspace", () => {
  it("requires separate creation confirmation and then continues the same conversation", async () => {
    const user = userEvent.setup(); render(<HomePage />);
    expect(screen.getByRole("heading", { name: "What would you like to improve?" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your objective"), "Improve product performance");
    await user.click(screen.getByRole("button", { name: "Review objective" }));
    expect(await screen.findByRole("button", { name: "Confirm and create run" })).toBeInTheDocument();
    expect(created).toBe(false);
    await user.click(screen.getByRole("button", { name: "Confirm and create run" }));
    expect(await screen.findByRole("heading", { name: "Run created" })).toBeInTheDocument();
    expect(screen.getByLabelText("Run supervision")).toHaveTextContent("session");
    expect(screen.getByLabelText("Run supervision")).toHaveTextContent("Improve product performance");
    expect(screen.getByText(/does not mean the objective is complete/)).toBeInTheDocument();
  });
  it("restores a durable bound conversation from its URL", async () => {
    created = true; window.history.replaceState(null, "", "/?conversation=session"); render(<HomePage />);
    expect(await screen.findByLabelText("Run supervision")).toHaveTextContent("session");
  });
  it("does not accept a delayed creation proposal after starting a new conversation", async () => {
    const user = userEvent.setup(); let resolveMessage: (value: Response) => void = () => undefined;
    const existing = global.fetch;
    global.fetch = vi.fn().mockImplementation((url, init) => {
      if (JSON.parse(String(init.body)).operation === "message") return new Promise<Response>((resolve) => { resolveMessage = resolve; });
      return existing(url, init);
    });
    render(<HomePage />);
    await user.type(screen.getByLabelText("Your objective"), "Improve product performance"); await user.click(screen.getByRole("button", { name: "Review objective" }));
    await user.click(screen.getByRole("button", { name: "New chat" }));
    resolveMessage(new Response(JSON.stringify({ state: "proposed", session_id: "old", proposal })));
    await waitFor(() => expect(screen.getByLabelText("Your objective")).toHaveValue(""));
    expect(screen.queryByRole("button", { name: "Confirm and create run" })).not.toBeInTheDocument();
  });
  it("restores the URL conversation in StrictMode", async () => {
    created = true; window.history.replaceState(null, "", "/?conversation=session");
    render(<React.StrictMode><HomePage /></React.StrictMode>);
    expect(await screen.findByLabelText("Run supervision")).toHaveTextContent("session");
  });
  it.each(["tenant", "human"])("clears prior private conversation when %s changes", async (identity) => {
    created = true; window.history.replaceState(null, "", "/?conversation=session");
    const view = render(<HomePage />);
    expect(await screen.findByLabelText("Run supervision")).toBeInTheDocument();
    if (identity === "tenant") api.clientId = "tenant-2";
    else api.userId = "another-human";
    view.rerender(<HomePage />);
    await waitFor(() => expect(screen.queryByLabelText("Run supervision")).not.toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Run created" })).not.toBeInTheDocument();
  });
  it("requires sign-in before submitting an objective", async () => {
    api.userId = null; const user = userEvent.setup(); render(<HomePage />);
    await user.type(screen.getByLabelText("Your objective"), "Improve performance");
    expect(screen.getByRole("button", { name: "Review objective" })).toBeDisabled();
  });

});
