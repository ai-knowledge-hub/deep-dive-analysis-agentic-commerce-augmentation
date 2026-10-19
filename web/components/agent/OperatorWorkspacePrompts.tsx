import React from "react";
import type { AgentAction, AgentRun } from "../../lib/types";
import { workspaceActionLabel } from "../../lib/workspaceDisplay";
export function OperatorWorkspacePrompts({ run, actions, busy, send }: {
  run: AgentRun | null; actions: AgentAction[]; busy: boolean; send: (question: string) => void;
}) {
  if (!run || ["completed", "canceled", "failed"].includes(run.status ?? "")) return null;
  const next = [...actions].sort((a, b) => a.sequence - b.sequence).find((action) => action.status === "proposed");
  return <div className="workspace-run-prompts">
    {next && <button type="button" className="button button--ghost" disabled={busy} onClick={() => send(`Approve action ${next.id}`)}>Review action {next.sequence}: {workspaceActionLabel(next.capability_name)}</button>}
    <details><summary>Run controls</summary><div className="panel__actions">
      <button type="button" className="button button--ghost button--sm" disabled={busy} onClick={() => send(run.status === "paused" ? "Resume this run" : "Pause this run")}>{run.status === "paused" ? "Review resume" : "Review pause"}</button>
      <button type="button" className="button button--ghost button--sm" disabled={busy} onClick={() => send("Cancel this run")}>Review cancellation</button>
      {next && <button type="button" className="button button--ghost button--sm" disabled={busy} onClick={() => send(`Reject action ${next.id}`)}>Review rejection of action {next.sequence}</button>}
    </div><p className="workspace-note">Requests prepare a proposal. Confirm the exact decision separately. Started work can finish after pause; cancellation reverses no completed effect.</p></details>
  </div>;
}
