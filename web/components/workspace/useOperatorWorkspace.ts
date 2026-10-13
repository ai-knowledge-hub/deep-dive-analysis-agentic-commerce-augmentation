"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  workspaceRequest, type WorkspaceHistory, type WorkspaceList, type WorkspaceMessage,
} from "../../lib/workspace";

const EMPTY: WorkspaceList = { conversations: [], has_more: false };
function olderPageRequest(history: WorkspaceHistory | null, id: string | null, loading: boolean) {
  const before = history?.turns_before_id;
  return !id || !before || loading ? null : { id, before };
}
function mergeOlderHistory(current: WorkspaceHistory | null, page: WorkspaceHistory, id: string, before: number) {
  if (current?.session_id !== id || current.turns_before_id !== before) return current;
  const existing = new Set(current.turns.map((turn) => turn.id));
  return { ...current, turns: [...page.turns.filter((turn) => !existing.has(turn.id)), ...current.turns], turns_has_more: page.turns_has_more, turns_before_id: page.turns_before_id };
}
export function useOperatorWorkspace(clientId: string, userId: string | null) {
  const [history, setHistory] = useState<WorkspaceHistory | null>(null);
  const [conversations, setConversations] = useState<WorkspaceList>(EMPTY);
  const [reply, setReply] = useState<WorkspaceMessage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [generation, setGeneration] = useState(0);
  const epoch = useRef(0);
  const busyRef = useRef(false);
  const initialSession = useRef(typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("conversation"));
  const abort = useRef<AbortController | null>(null);
  const session = useRef<string | null>(null);
  const objective = useRef("");

  const list = useCallback(async (signal?: AbortSignal) => {
    const request = epoch.current;
    const result = await workspaceRequest<WorkspaceList>(clientId, { operation: "list" }, signal);
    if (epoch.current === request) setConversations(result);
  }, [clientId]);
  const load = useCallback(async (id: string, signal?: AbortSignal) => {
    const request = epoch.current;
    const result = await workspaceRequest<WorkspaceHistory>(clientId, { operation: "read", session_id: id }, signal);
    if (epoch.current !== request) return;
    setHistory(result);
    session.current = id;
    objective.current = [...result.turns].reverse().find((turn) => turn.speaker === "user")?.content ?? "";
    const latest = [...result.turns].reverse().find((turn) => turn.metadata?.workspace_result);
    setReply(latest?.metadata.workspace_result ?? null);
  }, [clientId]);
  const reset = useCallback(() => {
    epoch.current += 1;
    abort.current?.abort();
    session.current = null;
    objective.current = "";
    initialSession.current = null;
    busyRef.current = false;
    setGeneration((value) => value + 1);
    setHistory(null); setReply(null); setBusy(false); setError(null); setLoadingOlder(false);
    window.history.replaceState(null, "", "/");
  }, []);
  useEffect(() => {
    const id = initialSession.current;
    reset(); initialSession.current = id;
    setConversations(EMPTY);
    if (!clientId || !userId) return;
    const controller = new AbortController();
    abort.current = controller;
    void list(controller.signal).catch((e) => {
      if (!controller.signal.aborted) setError(String(e.message));
    });
    if (id) {
      busyRef.current = true; setBusy(true);
      void load(id, controller.signal).then(() => {
        if (controller.signal.aborted) return;
        initialSession.current = null;
        window.history.replaceState(null, "", `/?conversation=${encodeURIComponent(id)}`);
      }).catch((e) => {
        if (!controller.signal.aborted) setError(String(e.message));
      }).finally(() => {
        if (!controller.signal.aborted) { busyRef.current = false; setBusy(false); }
      });
    }
    return () => { epoch.current += 1; controller.abort(); };
  }, [clientId, userId, list, load, reset]);

  async function select(id: string) {
    epoch.current += 1; abort.current?.abort();
    session.current = null; objective.current = "";
    busyRef.current = true; setBusy(true);
    setGeneration((value) => value + 1);
    setError(null); setHistory(null); setReply(null); setLoadingOlder(false);
    const controller = new AbortController(); abort.current = controller;
    try {
      await load(id, controller.signal);
      if (!controller.signal.aborted) window.history.replaceState(null, "", `/?conversation=${encodeURIComponent(id)}`);
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Conversation unavailable");
    } finally {
      if (!controller.signal.aborted) { busyRef.current = false; setBusy(false); }
    }
  }
  async function perform(payload: Record<string, unknown>) {
    if (busyRef.current || !userId || !clientId) return;
    busyRef.current = true;
    const request = epoch.current;
    const controller = new AbortController(); abort.current = controller;
    setBusy(true); setError(null);
    try {
      const result = await workspaceRequest<WorkspaceMessage>(clientId, payload, controller.signal);
      if (epoch.current !== request) return;
      session.current = result.session_id;
      window.history.replaceState(null, "", `/?conversation=${encodeURIComponent(result.session_id)}`);
      await load(result.session_id, controller.signal);
      await list(controller.signal);
      if (epoch.current === request && payload.operation === "message") setReply(result);
    } catch (e) {
      if (epoch.current === request && !controller.signal.aborted) setError(e instanceof Error ? e.message : "Workspace request failed");
    } finally {
      if (epoch.current === request) { busyRef.current = false; setBusy(false); }
    }
  }
  async function send(message: string, experimentId?: string) {
    objective.current = message;
    await perform({ operation: "message", session_id: session.current, message, experiment_id: experimentId });
  }
  const proposal = history?.run_id ? null : reply?.proposal ?? history?.proposals.at(-1) ?? null;
  async function confirm() {
    if (!proposal) return;
    await perform({ operation: "confirm", session_id: session.current, proposal_id: proposal.proposal_id, proposal_digest: proposal.proposal_digest });
  }
  async function refresh() {
    if (!session.current) return;
    try { await load(session.current); }
    catch (e) { setError(e instanceof Error ? e.message : "Run refresh failed"); }
  }
  async function loadOlderTurns() {
    const pageRequest = olderPageRequest(history, session.current, loadingOlder);
    if (!pageRequest) return;
    const { id, before } = pageRequest;
    const request = epoch.current;
    setLoadingOlder(true);
    try {
      const page = await workspaceRequest<WorkspaceHistory>(clientId, { operation: "read", session_id: id, before_turn_id: before });
      if (epoch.current !== request) return;
      setHistory((current) => mergeOlderHistory(current, page, id, before));
    } catch (e) {
      if (epoch.current === request) setError(e instanceof Error ? e.message : "Older conversation unavailable");
    } finally { if (epoch.current === request) setLoadingOlder(false); }
  }
  return {
    ready: Boolean(clientId && userId), history, conversations, reply, busy, error, generation, proposal, receipt: history?.receipt ?? null,
    reset, select, send, confirm, refresh, loadOlderTurns, loadingOlder,
    choose: (id: string) => send(objective.current, id),
    open: (runId: string) => perform({ operation: "open", run_id: runId }),
  };
}
