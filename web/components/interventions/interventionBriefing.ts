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
    return "No intervention-worthy items are waiting right now. The execution fabric is currently running without operator action.";
  }
  const prefix = runIdParam ? `Run ${runIdParam.slice(0, 8)} has ` : "";
  return `${prefix}${total} intervention item${total === 1 ? "" : "s"}: ${escalationsCount} escalations, ${approvalsCount} approvals, ${commandsCount} recovery item${commandsCount === 1 ? "" : "s"}, ${retriesCount} retry or resume action${retriesCount === 1 ? "" : "s"}, and ${pausesCount} active run pause decision${pausesCount === 1 ? "" : "s"}.`;
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
      label: "Commands",
      value: commandsCount,
      tone: commandsCount > 0 ? "warning" : "default",
    },
    { label: "Retries", value: retriesCount },
    { label: "Pauses", value: pausesCount },
  ];
}
