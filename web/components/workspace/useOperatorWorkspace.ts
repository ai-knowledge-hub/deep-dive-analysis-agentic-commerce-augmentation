"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  workspaceRequest, type WorkspaceHistory, type WorkspaceList, type WorkspaceMessage,
} from "../../lib/workspace";

import { refreshWorkspaceHistory, prependWorkspaceHistory } from "./workspaceHistory";

function errorMessage(error: unknown, fallback: string) { return error instanceof Error ? error.message : fallback; }
const EMPTY: WorkspaceList = { conversations: [], has_more: false };
function currentProposal(history: WorkspaceHistory | null, reply: WorkspaceMessage | null) {
  return history?.run_id ? null : reply?.proposal ?? history?.proposals.at(-1) ?? null;
}
function scopedView(inScope: boolean, history: WorkspaceHistory | null, conversations: WorkspaceList, reply: WorkspaceMessage | null, error: string | null, drafts: Record<string, string>, id: string | null) {
  if (!inScope) return { history: null, conversations: EMPTY, reply: null, error: null, proposal: null, receipt: null, draft: "" };
  return { history, conversations, reply, error, proposal: currentProposal(history, reply), receipt: history?.receipt ?? null, draft: drafts[id ?? "new"] ?? "" };
}
function olderPageRequest(history: WorkspaceHistory | null, id: string | null, loading: boolean) {
  const before = history?.turns_before_id;
  return !id || !before || loading ? null : { id, before };
}
export function useOperatorWorkspace(clientId: string, userId: string | null) {
  const [history, setHistory] = useState<WorkspaceHistory | null>(null);
  const [conversations, setConversations] = useState<WorkspaceList>(EMPTY);
  const [reply, setReply] = useState<WorkspaceMessage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const scope = JSON.stringify([clientId, userId]);
  const activeScope = useRef(scope);
  const inScope = activeScope.current === scope;
  const readVersion = useRef(0);
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
  const load = useCallback(async (id: string, signal?: AbortSignal, preserve = false) => {
    const request = epoch.current;
    const version = ++readVersion.current;
    const result = await workspaceRequest<WorkspaceHistory>(clientId, { operation: "read", session_id: id }, signal);
    if (epoch.current !== request || readVersion.current !== version) return;
    setHistory((current) => preserve ? refreshWorkspaceHistory(current, result) : result);
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
    setDrafts((current) => ({ ...current, new: "" }));
    setHistory(null); setReply(null); setBusy(false); setError(null); setLoadingOlder(false);
    window.history.replaceState(null, "", "/");
  }, []);
  useEffect(() => {
    const id = initialSession.current;
    reset(); initialSession.current = id;
    activeScope.current = scope; setDrafts({});
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
  }, [clientId, userId, scope, list, load, reset]);

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
      if (!controller.signal.aborted) setError(errorMessage(e, "Conversation unavailable"));
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
    const sourceDraftKey = session.current ?? "new";
    try {
      const result = await workspaceRequest<WorkspaceMessage>(clientId, payload, controller.signal);
      if (epoch.current !== request) return;
      session.current = result.session_id;
      window.history.replaceState(null, "", `/?conversation=${encodeURIComponent(result.session_id)}`);
      await load(result.session_id, controller.signal, true);
      if (epoch.current !== request) return;
      if (payload.operation === "message") setDrafts((current) => ({ ...current, [sourceDraftKey]: "" }));
      await list(controller.signal);
      if (epoch.current === request && payload.operation === "message") setReply(result);
    } catch (e) {
      if (epoch.current === request && !controller.signal.aborted) setError(errorMessage(e, "Workspace request failed"));
    } finally {
      if (epoch.current === request) { busyRef.current = false; setBusy(false); }
    }
  }
  async function send(message: string, experimentId?: string) {
    objective.current = message;
    await perform({ operation: "message", session_id: session.current, message, experiment_id: experimentId });
  }
  const proposal = currentProposal(history, reply);
  async function confirm() {
    if (!proposal) return;
    await perform({ operation: "confirm", session_id: session.current, proposal_id: proposal.proposal_id, proposal_digest: proposal.proposal_digest });
  }
  async function refresh() {
    if (!session.current) return;
    const request = epoch.current;
    try { await load(session.current, undefined, true); }
    catch (e) { if (epoch.current === request) setError(errorMessage(e, "Run refresh failed")); }
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
      setHistory((current) => prependWorkspaceHistory(current, page, id, before));
    } catch (e) {
      if (epoch.current === request) setError(errorMessage(e, "Older conversation unavailable"));
    } finally { if (epoch.current === request) setLoadingOlder(false); }
  }
  return {
    ...scopedView(inScope, history, conversations, reply, error, drafts, session.current),
    ready: inScope && Boolean(clientId && userId), busy, generation,
    setDraft: (value: string) => { const key = session.current ?? "new"; setDrafts((current) => ({ ...current, [key]: value })); },
    reset, select, send, confirm, refresh, loadOlderTurns, loadingOlder,
    choose: (id: string) => send(objective.current, id),
    open: (runId: string) => perform({ operation: "open", run_id: runId }),
  };
}
