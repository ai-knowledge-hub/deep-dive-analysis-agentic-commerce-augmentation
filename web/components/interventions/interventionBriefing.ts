type BriefingMetric = {
  label: string;
  value: string | number;
  tone?: "default" | "warning";
};

type InterventionCounts = {
  approvalsCount: number;
  commandsCount: number;
  escalationsCount: number;
  pausesCount: number;
  retriesCount: number;
};

export function buildInterventionBriefing({
  userId,
  runIdParam,
  approvalsCount,
  commandsCount,
  escalationsCount,
  pausesCount,
  retriesCount,
}: InterventionCounts & {
  userId: string | null;
  runIdParam: string;
}) {
  if (!userId) {
    return "Sign in to review approvals, retries, pauses, and escalation-worthy runs.";
  }
  const total =
    approvalsCount + retriesCount + pausesCount + escalationsCount + commandsCount;
  if (total === 0) {
    if (runIdParam) {
      return `Run ${runIdParam.slice(0, 8)} does not currently need operator intervention.`;
    }
    return "No decisions are waiting right now. Return to Runs when you want to supervise execution.";
  }
  const prefix = runIdParam ? `Run ${runIdParam.slice(0, 8)} has ` : "";
  return `${prefix}${total} decision${total === 1 ? "" : "s"} waiting. Start with the recommended card, then use the queue sections only when you need more context.`;
}

export function buildInterventionMetrics({
  approvalsCount,
  commandsCount,
  escalationsCount,
  pausesCount,
  retriesCount,
}: InterventionCounts): BriefingMetric[] {
  return [
    {
      label: "Escalations",
      value: escalationsCount,
      tone: escalationsCount > 0 ? "warning" : "default",
    },
    { label: "Approvals", value: approvalsCount },
    {
      label: "Recovery",
      value: commandsCount,
      tone: commandsCount > 0 ? "warning" : "default",
    },
    { label: "Resume", value: retriesCount },
    { label: "Pauses", value: pausesCount },
  ];
}
