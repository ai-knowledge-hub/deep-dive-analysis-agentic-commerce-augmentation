import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useOperatorWorkspace } from "./useOperatorWorkspace";
import { workspaceRequest, type WorkspaceHistory } from "../../lib/workspace";
vi.mock("../../lib/workspace", () => ({ workspaceRequest: vi.fn() }));
const request = vi.mocked(workspaceRequest);
const evidence = { snapshot: { digest: "original-digest" }, evidence: [{ href: "/evidence/original" }], freshness: { state: "stale" } };
const latest = { session_id: "session", run_id: "run", run: { id: "run" }, actions: [], events: [], proposals: [], receipt: null, has_more: false,
  turns: [{ id: 5, speaker: "user", content: "Recent question", metadata: {} }, { id: 504, speaker: "agent", content: "Latest verified answer", metadata: { operator_response: evidence } }], turns_has_more: true, turns_before_id: 5 } as unknown as WorkspaceHistory;
beforeEach(() => {
  window.history.replaceState(null, "", "/?conversation=session");
  request.mockReset();
  request.mockImplementation(async (_client, payload) => payload.operation === "list" ? { conversations: [], has_more: false } : latest);
});
afterEach(() => vi.restoreAllMocks());
describe("workspace conversation pagination", () => {
  it("prepends older pages without replacing current progress or recent structured evidence", async () => {
    const { result } = renderHook(() => useOperatorWorkspace("tenant", "human"));
    await waitFor(() => expect(result.current.history?.turns.at(-1)?.id).toBe(504));
    request.mockResolvedValueOnce({ ...latest, run: { id: "run", status: "old" }, turns: [{ id: 1, speaker: "user", content: "Old question", metadata: {} }, latest.turns[0]], turns_has_more: false, turns_before_id: null });
    await act(() => result.current.loadOlderTurns());
    expect(request).toHaveBeenLastCalledWith("tenant", { operation: "read", session_id: "session", before_turn_id: 5 });
    expect(result.current.history?.turns.map((turn) => turn.id)).toEqual([1, 5, 504]);
    expect(result.current.history?.turns.at(-1)?.metadata.operator_response).toEqual(evidence);
    expect(result.current.history?.run).toEqual(latest.run);
    expect(result.current.history?.turns_has_more).toBe(false);
    expect(result.current.history?.turns_before_id).toBeNull();
  });
  it("discards delayed older evidence after tenant switching", async () => {
    const { result, rerender } = renderHook(({ tenant }) => useOperatorWorkspace(tenant, "human"), { initialProps: { tenant: "tenant" } });
    await waitFor(() => expect(result.current.history?.session_id).toBe("session"));
    let deliver!: (value: unknown) => void;
    request.mockImplementationOnce(() => new Promise((resolve) => { deliver = resolve; }));
    let pending!: Promise<void>;
    act(() => { pending = result.current.loadOlderTurns(); });
    request.mockImplementation(async (_client, payload) => payload.operation === "list" ? { conversations: [], has_more: false } : { ...latest, session_id: "another-session", turns: [] });
    rerender({ tenant: "other-tenant" });
    await act(async () => { deliver({ ...latest, turns: [{ id: 1, content: "private older evidence" }] }); await pending; });
    expect(result.current.history).toBeNull();
    expect(result.current.loadingOlder).toBe(false);
  });
  it("discards an older page superseded by a progress refresh", async () => {
    const { result } = renderHook(() => useOperatorWorkspace("tenant", "human"));
    await waitFor(() => expect(result.current.history?.turns_before_id).toBe(5));
    let deliver!: (value: unknown) => void;
    request.mockImplementationOnce(() => new Promise((resolve) => { deliver = resolve; }));
    let pending!: Promise<void>;
    act(() => { pending = result.current.loadOlderTurns(); });
    request.mockResolvedValueOnce({ ...latest, turns_before_id: 6 });
    await act(() => result.current.refresh());
    await act(async () => { deliver({ ...latest, turns: [{ id: 1, content: "superseded page" }], turns_before_id: null }); await pending; });
    expect(result.current.history?.turns_before_id).toBe(6);
    expect(result.current.history?.turns.map((turn) => turn.id)).toEqual([5, 504]);
  });
});
