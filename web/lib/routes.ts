type RouteContext = {
  experimentId?: string | null;
  runId?: string | null;
};

function buildHref(path: string, context: RouteContext): string {
  const params = new URLSearchParams();
  if (context.experimentId) {
    params.set("experiment_id", context.experimentId);
  }
  if (context.runId) {
    params.set("run_id", context.runId);
  }
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export function buildRunsHref(context: RouteContext = {}): string {
  return buildHref("/runs", context);
}

export function buildInterventionsHref(context: RouteContext = {}): string {
  return buildHref("/interventions", context);
}

export function buildExperimentHref(
  experimentId?: string | null,
  context: Pick<RouteContext, "runId"> = {},
): string {
  return buildHref("/experiments", { experimentId, runId: context.runId });
}

export function buildValidationHref(context: RouteContext = {}): string {
  return buildHref("/validation", context);
}

export function buildSimulationHref(
  runId?: string | null,
  context: Pick<RouteContext, "experimentId"> = {},
): string {
  return buildHref("/simulation", { experimentId: context.experimentId, runId });
}
