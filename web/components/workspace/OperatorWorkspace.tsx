"use client";
import React, { useMemo } from "react";
import type { AgentRun } from "../../lib/types";
import { restoreWorkspaceMessages } from "../agent/operatorChatHistory";
import { OperatorConsoleChat } from "../agent/OperatorConsoleChat";
import { RunCreationDecision } from "./RunCreationDecision";
import { useOperatorWorkspace } from "./useOperatorWorkspace";
import { WorkspaceShell } from "./WorkspaceShell";
import { WorkspaceDetails } from "./WorkspaceDetails";

export function OperatorWorkspace({ workspace, runs, userId }: {
  workspace: ReturnType<typeof useOperatorWorkspace>; runs: AgentRun[]; userId: string | null;
}) {
  const { history, reply, busy, error } = workspace;
  const messages = useMemo(() => restoreWorkspaceMessages(history), [history]);
  const empty = !history && !busy;
  return <WorkspaceShell conversations={workspace.conversations} activeId={history?.session_id}
    title={history?.confirmed_proposal?.preflight.parameters.objective.goal || "Commerce workspace"}
    subtitle={history?.run ? `Supervised run · ${history.run.status}` : "One existing product experiment"}
    onNew={workspace.reset} onSelect={(id) => void workspace.select(id)} details={<WorkspaceDetails history={history} proposal={workspace.proposal} />}>
    {(evidenceTarget) => <div className={`workspace-conversation-body ${empty ? "is-empty" : ""}`}>
      {empty && <div className="workspace-welcome"><p className="workspace-eyebrow">Scout · your commerce assistant</p><h1>What would you like to improve?</h1><p>Start with an existing product experiment.<br />Review the plan, then supervise one decision at a time.</p></div>}
      {!userId && <p>Sign in to start or continue a conversation.</p>}
      {userId && !workspace.ready && <p>Select a tenant to start or continue a conversation.</p>}
      {error && <p role="alert">{error}</p>}
      {busy && <p role="status">Loading conversation…</p>}
      {history?.turns_has_more && <button className="workspace-text-button" type="button" disabled={workspace.loadingOlder} onClick={() => void workspace.loadOlderTurns()}>{workspace.loadingOlder ? "Loading older messages…" : "Load older messages"}</button>}
      {history?.has_more && <p className="workspace-note">Older creation proposals are outside this view. The latest 100 are shown.</p>}
      {history?.run ? <>
        <div className="workspace-run-progress"><span>Run status: {history.run.status}</span><button type="button" disabled={busy} onClick={() => void workspace.refresh()}>Refresh run progress</button>
          <small>Snapshot: {history.as_of ? new Date(history.as_of).toLocaleString() : "loaded from the server"}. Completion requires verified evidence.</small></div>
        <details className="workspace-creation-record"><summary>Run creation decision</summary><RunCreationDecision proposal={history.confirmed_proposal ?? null} receipt={workspace.receipt} busy={busy} onConfirm={() => void workspace.confirm()} /></details>
        {history.actions_has_more && <p>The action list is partial. Inspect Runs for older actions.</p>}
        <OperatorConsoleChat key={`${workspace.generation}:${history.session_id}`} run={history.run} actions={history.actions} events={history.events} userId={userId}
          selectedAction={null} nextRecommendedAction={{ action: null, guardrails: [], hint: "Ask about the next action" }} presentation="workspace" detailsTarget={evidenceTarget}
          draftValue={workspace.draft} onDraftChange={workspace.setDraft} showCreationDecision={false} initialSessionId={history.session_id} initialMessages={messages} onCommandCommitted={workspace.refresh} />
      </> : <>
        {(history?.turns ?? []).map((turn) => <div className={`workspace-message workspace-message--${turn.speaker}`} key={turn.id}><small>{turn.speaker === "user" ? "You" : "Scout"}</small><p>{turn.content}</p></div>)}
        {reply?.state === "clarification" && <section className="workspace-review" aria-label="Choose experiment"><h2>Choose an experiment</h2>
          {(reply.candidates ?? []).map((candidate) => <button type="button" key={candidate.id} disabled={busy} onClick={() => void workspace.choose(candidate.id)}>{candidate.name}{candidate.product_name ? ` · ${candidate.product_name}` : ""}</button>)}
          {reply.has_more && <p>More experiments exist. Use the experiment control plane to locate the exact scope.</p>}
          {!reply.candidates?.length && <p>No experiment is available in this tenant. <a href="/experiments">Set up an experiment</a> first.</p>}
        </section>}
        <RunCreationDecision proposal={workspace.proposal} receipt={workspace.receipt} busy={busy} onConfirm={() => void workspace.confirm()} />
        <form className="workspace-composer" onSubmit={(event) => { event.preventDefault(); if (workspace.draft.trim()) void workspace.send(workspace.draft.trim()); }}>
          <label className="workspace-sr-only" htmlFor="objective">Your objective</label><textarea id="objective" value={workspace.draft} maxLength={2000} onChange={(e) => workspace.setDraft(e.target.value)} placeholder="Compare a candidate with the control…" rows={3} required disabled={busy} />
          <div><span>One existing experiment</span><button className="workspace-submit" type="submit" disabled={busy || !workspace.ready || !workspace.draft.trim()}>{busy ? "Preparing…" : workspace.proposal ? "Revise objective" : "Review objective"}</button></div>
        </form>
        <details className="workspace-recent-runs"><summary>Continue a recent run</summary><label htmlFor="existing-run">Choose a run</label><select id="existing-run" value="" disabled={busy || !workspace.ready} onChange={(event) => { if (event.target.value) void workspace.open(event.target.value); }}>
          <option value="">Choose a run</option>{runs.map((run) => <option key={run.id} value={run.id}>{String(run.objective?.goal ?? run.id)} · {run.status}</option>)}
        </select></details>
      </>}
    </div>}
  </WorkspaceShell>;
}
