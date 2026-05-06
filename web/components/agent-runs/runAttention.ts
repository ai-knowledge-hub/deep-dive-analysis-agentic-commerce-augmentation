import type { AgentRun } from "../../lib/types";

export function runAttentionRank(run: AgentRun): number {
  const status = String(run.status ?? "").toLowerCase();
  if (status === "failed") return 0;
  if (run.requires_approval) return 1;
  if (["running", "active", "executing", "paused"].includes(status)) return 2;
  return 3;
}

export function runAttentionLabel(run: AgentRun): string | null {
  const status = String(run.status ?? "").toLowerCase();
  if (status === "failed") return "Critical";
  if (run.requires_approval) return "Approval";
  if (["running", "active", "executing", "paused"].includes(status)) return "Watching";
  return null;
}

export function sortRunsForOperatorAttention(runs: AgentRun[]): AgentRun[] {
  return [...runs].sort((a, b) => {
    const rankDelta = runAttentionRank(a) - runAttentionRank(b);
    if (rankDelta !== 0) return rankDelta;
    return String(a.id).localeCompare(String(b.id));
  });
}
