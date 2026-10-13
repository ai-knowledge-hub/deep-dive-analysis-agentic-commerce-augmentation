"use client";
import React, { useMemo, useState } from "react";
import type { AgentRun } from "../../lib/types";
import { restoreWorkspaceMessages } from "../agent/operatorChatHistory";
import { OperatorConsoleChat } from "../agent/OperatorConsoleChat";
import { RunCreationDecision } from "./RunCreationDecision";
import { useOperatorWorkspace } from "./useOperatorWorkspace";

export function OperatorWorkspace({ workspace, runs, userId, onMenu }: {
  workspace: ReturnType<typeof useOperatorWorkspace>; runs: AgentRun[]; userId: string | null; onMenu?: () => void;
}) {
  const [draft, setDraft] = useState("");
  const { history, reply, busy, error } = workspace;
  const messages = useMemo(() => restoreWorkspaceMessages(history), [history]);
  return <main className="workspace-main">
    <header className="workspace-header"><button type="button" className="mobile-toggle" aria-label="Open menu" onClick={onMenu}>☰</button><div><p className="eyebrow">Commerce workspace</p><h1>What would you like to improve?</h1>
      <p>Describe an objective, review its scope and plan, then supervise the work here.</p></div>
      <button type="button" onClick={workspace.reset}>New conversation</button></header>
    <nav className="workspace-links" aria-label="Control plane"><a href="/inbox">Inbox</a><a href="/runs">Runs</a><a href="/interventions">Interventions</a><a href="/learnings">Insights</a><a href="/lab">Advanced Lab</a></nav>
    <label htmlFor="conversation">Continue a conversation</label><select id="conversation" value={history?.session_id ?? ""} onChange={(e) => { if (e.target.value) void workspace.select(e.target.value); }}>
      <option value="">Choose a conversation</option>{workspace.conversations.conversations.map((c) => <option key={c.session_id} value={c.session_id}>{c.preview ?? (c.run_id ? "Run conversation" : "Objective conversation")}</option>)}
    </select>
    {!userId && <p>Sign in to start or continue a conversation.</p>}
    {userId && !workspace.ready && <p>Select a tenant to start or continue a conversation.</p>}
    {error && <p role="alert">{error}</p>}
    {history?.turns_has_more && <button type="button" disabled={workspace.loadingOlder} onClick={() => void workspace.loadOlderTurns()}>{workspace.loadingOlder ? "Loading older messages…" : "Load older messages"}</button>}
    {history?.has_more && <p>Older creation proposals are outside this view. The latest 100 are shown.</p>}
    {workspace.conversations.has_more && <p>More conversations exist than this recent list includes.</p>}
    <RunCreationDecision proposal={workspace.proposal ?? history?.confirmed_proposal ?? null} receipt={workspace.receipt} busy={busy} onConfirm={() => void workspace.confirm()} />
    {history?.run ? <>
      <p>Current run: {history.run.status}. Snapshot: {history.as_of ? new Date(history.as_of).toLocaleString() : "loaded from the server"}. <a href={`/interventions?run_id=${encodeURIComponent(history.run.id)}`}>Review interventions</a></p>
      <button type="button" className="button button--ghost" onClick={() => void workspace.refresh()}>Refresh run progress</button>
      {history.actions_has_more && <p>The action list is partial. Inspect Runs for older actions.</p>}
      <OperatorConsoleChat key={history.session_id} run={history.run} actions={history.actions} events={history.events} userId={userId}
        selectedAction={null} nextRecommendedAction={{ action: null, guardrails: [], hint: "Ask about the next action" }}
        showCreationDecision={false} initialSessionId={history.session_id} initialMessages={messages} onCommandCommitted={workspace.refresh} />
    </> : <>
      {(history?.turns ?? []).map((turn) => <p className="workspace-turn" key={turn.id}><strong>{turn.speaker === "user" ? "You" : "Assistant"}</strong><br />{turn.content}</p>)}
      {reply?.state === "clarification" && <section aria-label="Choose experiment"><h2>Choose an experiment</h2>
        {(reply.candidates ?? []).map((candidate) => <button type="button" key={candidate.id} disabled={busy} onClick={() => void workspace.choose(candidate.id)}>{candidate.name}{candidate.product_name ? ` · ${candidate.product_name}` : ""}</button>)}
        {reply.has_more && <p>More experiments exist. Use the experiment control plane to locate the exact scope.</p>}
        {!reply.candidates?.length && <p>No experiment is available in this tenant. Set up an experiment in the control plane first.</p>}
      </section>}
      <form onSubmit={(event) => { event.preventDefault(); if (draft.trim()) void workspace.send(draft.trim()); }}>
        <label htmlFor="objective">Your objective</label><textarea id="objective" value={draft} maxLength={2000} onChange={(e) => setDraft(e.target.value)} placeholder="Improve the performance of my product experiment" required />
        <button className={`button ${workspace.proposal ? "button--ghost" : "button--primary"}`} type="submit" disabled={busy || !workspace.ready || !draft.trim()}>{busy ? "Preparing…" : workspace.proposal ? "Revise objective" : "Review objective"}</button>
      </form>
      <label htmlFor="existing-run">Or continue a recent run</label><select id="existing-run" value="" disabled={busy} onChange={(event) => { if (event.target.value) void workspace.open(event.target.value); }}>
        <option value="">Choose a run</option>{runs.map((run) => <option key={run.id} value={run.id}>{String(run.objective?.goal ?? run.id)} · {run.status}</option>)}
      </select>
    </>}
  </main>;
}
