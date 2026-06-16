import type { AgentRun } from "../../lib/types";
import { formatOperatorIdentifier } from "../../lib/operatorDisplayLanguage";
import { formatDateCompact } from "./registryAudit";

function formatRunObjective(objective?: Record<string, unknown>): string | null {
  if (!objective) return null;
  const candidate =
    objective.label ??
    objective.name ??
    objective.title ??
    objective.objective ??
    objective.goal ??
    objective.query;

  if (typeof candidate !== "string" || !candidate.trim()) return null;
  return formatOperatorIdentifier(candidate);
}

export function formatAgentRunLabel(run: AgentRun): string {
  const kind = run.experiment_id ? "Experiment run" : "Standalone run";
  const objective = formatRunObjective(run.objective);
  if (objective) return `${kind} · ${objective}`;
  if (run.created_at) return `${kind} · started ${formatDateCompact(run.created_at)}`;
  return kind;
}
