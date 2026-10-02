import {
  getAgentRun,
  getAgentRunEvents,
  listAgentRuns,
  listAgentRuntimeRegistry,
  listOperatorConversationCommands,
} from "../../lib/api";
import type { OperatorCommandRecord } from "../../lib/operatorConversationTypes";
import { buildDetails } from "./interventionLogic";

const MAX_SCOPED_COMMAND_PAGES = 20;

async function loadCommandProjection(runId: string, exhaustive: boolean) {
  const records = new Map<string, OperatorCommandRecord>();
  let cursor: string | null = null;
  let hasMore = false;
  let totalCount = 0;
  let pageCount = 0;
  do {
    const response = await listOperatorConversationCommands(runId, { cursor });
    response.records.forEach((record) => {
      records.set(record.proposal.proposal_id, record);
    });
    hasMore = response.page.has_more;
    cursor = response.page.next_cursor;
    totalCount = response.total_count;
    pageCount += 1;
  } while (exhaustive && hasMore && cursor && pageCount < MAX_SCOPED_COMMAND_PAGES);
  return {
    records: [...records.values()],
    available: true,
    complete: !hasMore,
    totalCount,
  };
}

export async function loadInterventionDetailRows(
  userId: string,
  requestedRunId: string,
) {
  const [response, registry, requestedRunDetail] = await Promise.all([
    listAgentRuns({ limit: 16 }, userId),
    listAgentRuntimeRegistry(userId).catch(() => null),
    requestedRunId
      ? getAgentRun(requestedRunId, { limit: 50 }, userId)
      : Promise.resolve(null),
  ]);
  const runById = new Map((response.runs ?? []).map((run) => [run.id, run]));
  if (requestedRunDetail?.run) {
    runById.set(requestedRunId, {
      ...runById.get(requestedRunId),
      ...requestedRunDetail.run,
    });
  }
  const harnessProfiles = registry?.harness_profiles ?? [];
  return Promise.all(
    [...runById.values()].map(async (run) => {
      try {
        const [detail, eventData, operatorCommands] = await Promise.all([
          requestedRunDetail?.run?.id === run.id
            ? Promise.resolve(requestedRunDetail)
            : getAgentRun(run.id, { limit: 50 }, userId),
          getAgentRunEvents(run.id, { limit: 50, event_type: "all" }, userId),
          loadCommandProjection(run.id, run.id === requestedRunId).catch(() => ({
            records: [],
            available: false,
            complete: false,
            totalCount: 0,
          })),
        ]);
        return buildDetails(
          { ...run, ...(detail.run ?? {}) },
          detail.actions ?? [],
          eventData.events ?? [],
          harnessProfiles,
          operatorCommands.records,
          operatorCommands.available,
          operatorCommands.complete,
          operatorCommands.totalCount,
        );
      } catch {
        return buildDetails(run, [], [], harnessProfiles, [], false);
      }
    }),
  );
}
