"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getAgentRunCompletion,
  repairAgentRunCompletion,
} from "../../lib/api";
import type { AgentRunCompletion } from "../../lib/completionTypes";
import type { AgentRun } from "../../lib/types";
import type { CompletionOverview } from "./CompletionAuthorityPanel";

type Options = {
  runs: AgentRun[];
  selectedRunId: string | null;
  userId: string | null;
  onRepairCommitted: () => Promise<unknown>;
};

export type CompletionRefreshOutcome =
  | "refreshed"
  | "unavailable"
  | "superseded"
  | "skipped";

function sameRunSet(activeRunIds: Set<string>, requestedRunIds: string[]): boolean {
  return (
    activeRunIds.size === requestedRunIds.length &&
    requestedRunIds.every((runId) => activeRunIds.has(runId))
  );
}

function buildCompletionOverview(
  runs: AgentRun[],
  completionByRun: Record<string, AgentRunCompletion>,
  unavailable: Set<string>,
): CompletionOverview {
  const summary: CompletionOverview = {
    total: runs.length,
    verified: 0,
    governed: 0,
    legacy: 0,
    current: 0,
    stale: 0,
    repairEligible: 0,
    unavailable: runs.filter((run) => unavailable.has(run.id)).length,
    totalCursorLag: 0,
    incompleteRuns: 0,
    blockerCategories: {
      declaredBlockers: 0,
      missingRequirements: 0,
      missingResults: 0,
      partialResults: 0,
      failedTasks: 0,
      canceledTasks: 0,
      receiptBlockers: 0,
    },
  };
  const activeRunIds = new Set(runs.map((run) => run.id));
  for (const [runId, completion] of Object.entries(completionByRun)) {
    if (!activeRunIds.has(runId) || unavailable.has(runId)) continue;
    summary.verified += 1;
    if (completion.completion_authority_required) summary.governed += 1;
    else summary.legacy += 1;
    if (completion.projection.freshness === "current") summary.current += 1;
    else if (completion.completion_authority_required) summary.stale += 1;
    if (completion.repair.eligible) summary.repairEligible += 1;
    summary.totalCursorLag += Math.max(0, completion.projection.projection_lag ?? 0);
    const decision = completion.authoritative_decision;
    if (completion.projection.freshness !== "current" || decision?.status !== "incomplete") {
      continue;
    }
    summary.incompleteRuns += 1;
    if (decision.blockers.length) summary.blockerCategories.declaredBlockers += 1;
    if (decision.missing_requirements.length) {
      summary.blockerCategories.missingRequirements += 1;
    }
    if (decision.partial_failures.missing_result_task_ids.length) {
      summary.blockerCategories.missingResults += 1;
    }
    if (decision.partial_failures.partial_task_ids.length) {
      summary.blockerCategories.partialResults += 1;
    }
    if (decision.partial_failures.failed_task_ids.length) {
      summary.blockerCategories.failedTasks += 1;
    }
    if (decision.partial_failures.canceled_task_ids.length) {
      summary.blockerCategories.canceledTasks += 1;
    }
    if (decision.receipt_blockers.length) {
      summary.blockerCategories.receiptBlockers += 1;
    }
  }
  return summary;
}

export function useCompletionControlPlane({
  runs,
  selectedRunId,
  userId,
  onRepairCommitted,
}: Options) {
  const [completionByRun, setCompletionByRun] = useState<
    Record<string, AgentRunCompletion>
  >({});
  const [unavailable, setUnavailable] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [repairBusy, setRepairBusy] = useState(false);
  const [repairNotice, setRepairNotice] = useState<{
    type: "info" | "error";
    text: string;
  } | null>(null);
  const readGeneration = useRef(0);
  const repairKey = useRef<string | null>(null);
  const activeRunIds = useRef<Set<string>>(new Set());
  const activeUserId = useRef<string | null>(userId);
  const activeSelectedRunId = useRef<string | null>(selectedRunId);
  activeRunIds.current = new Set(runs.map((run) => run.id));
  activeUserId.current = userId;
  activeSelectedRunId.current = selectedRunId;

  const loadAll = useCallback(async () => {
    const generation = readGeneration.current + 1;
    readGeneration.current = generation;
    if (!userId || runs.length === 0) {
      setCompletionByRun({});
      setUnavailable(new Set());
      setLoading(false);
      return;
    }
    setLoading(true);
    const requestedRunIds = runs.map((run) => run.id);
    const requestedUserId = userId;
    const next: Record<string, AgentRunCompletion> = {};
    const failed = new Set<string>();
    const batchSize = 6;
    for (let index = 0; index < runs.length; index += batchSize) {
      const batch = runs.slice(index, index + batchSize);
      const responses = await Promise.allSettled(
        batch.map((run) => getAgentRunCompletion(run.id, userId)),
      );
      if (
        readGeneration.current !== generation ||
        activeUserId.current !== requestedUserId ||
        !sameRunSet(activeRunIds.current, requestedRunIds)
      ) {
        return;
      }
      responses.forEach((response, responseIndex) => {
        const runId = batch[responseIndex].id;
        if (response.status === "fulfilled") next[runId] = response.value.completion;
        else failed.add(runId);
      });
    }
    if (
      readGeneration.current === generation &&
      activeUserId.current === requestedUserId &&
      sameRunSet(activeRunIds.current, requestedRunIds)
    ) {
      setCompletionByRun(next);
      setUnavailable(failed);
      setLoading(false);
    }
  }, [runs, userId]);

  const refreshSelected = useCallback(async (): Promise<CompletionRefreshOutcome> => {
    if (!selectedRunId || !userId) return "skipped";
    const generation = readGeneration.current + 1;
    readGeneration.current = generation;
    const requestedRunId = selectedRunId;
    const requestedUserId = userId;
    setLoading(true);
    setRepairNotice(null);
    try {
      const response = await getAgentRunCompletion(selectedRunId, userId);
      if (
        readGeneration.current !== generation ||
        activeUserId.current !== requestedUserId ||
        !activeRunIds.current.has(requestedRunId)
      ) {
        return "superseded";
      }
      setCompletionByRun((current) => ({
        ...current,
        [selectedRunId]: response.completion,
      }));
      setUnavailable((current) => {
        const next = new Set(current);
        next.delete(selectedRunId);
        return next;
      });
      return "refreshed";
    } catch {
      if (
        readGeneration.current !== generation ||
        activeUserId.current !== requestedUserId ||
        !activeRunIds.current.has(requestedRunId)
      ) {
        return "superseded";
      }
      setCompletionByRun((current) => {
        const next = { ...current };
        delete next[selectedRunId];
        return next;
      });
      setUnavailable((current) => new Set(current).add(selectedRunId));
      return "unavailable";
    } finally {
      if (readGeneration.current === generation) setLoading(false);
    }
  }, [selectedRunId, userId]);

  const repairSelected = useCallback(async () => {
    if (!selectedRunId || !userId) return;
    const repairRunId = selectedRunId;
    if (!repairKey.current) {
      repairKey.current =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `completion-repair-${selectedRunId}-${Date.now()}`;
    }
    setRepairBusy(true);
    setRepairNotice(null);
    let response: Awaited<ReturnType<typeof repairAgentRunCompletion>>;
    try {
      response = await repairAgentRunCompletion(
        repairRunId,
        { idempotency_key: repairKey.current },
        userId,
      );
    } catch (error) {
      if (activeSelectedRunId.current !== repairRunId) {
        setRepairBusy(false);
        return;
      }
      const refreshOutcome = await refreshSelected();
      if (activeSelectedRunId.current !== repairRunId) {
        setRepairBusy(false);
        return;
      }
      const conflict = error instanceof Error && error.message.includes("409");
      setRepairNotice({
        type: "error",
        text: conflict
          ? refreshOutcome === "refreshed"
            ? "Repair conflicted with newer lifecycle state. Completion was refreshed; review the latest authority before retrying."
            : refreshOutcome === "unavailable"
              ? "Repair conflicted with newer lifecycle state, and the latest completion authority could not be refreshed. Retry the read before repairing again."
              : "Repair conflicted with newer lifecycle state. Another authority read superseded the automatic refresh; review the latest view before retrying."
          : refreshOutcome === "unavailable"
            ? "Repair was not accepted, and completion authority is currently unavailable. Check operator authority, refresh, and retry with the same request."
            : "Repair was not accepted. Check operator authority and retry with the same request.",
      });
      setRepairBusy(false);
      return;
    }
    if (
      activeSelectedRunId.current !== repairRunId ||
      activeUserId.current !== userId ||
      !activeRunIds.current.has(repairRunId)
    ) {
      setRepairBusy(false);
      return;
    }
    readGeneration.current += 1;
    setLoading(false);
    setCompletionByRun((current) => ({
      ...current,
      [repairRunId]: response.completion,
    }));
    setRepairNotice({
      type: "info",
      text:
        response.command.outcome === "replayed"
          ? "The existing repair outcome was replayed safely."
          : "Completion projection repaired from immutable authority.",
    });
    repairKey.current = null;
    try {
      await onRepairCommitted();
    } catch {
      if (activeSelectedRunId.current === repairRunId) {
        setRepairNotice({
          type: "error",
          text: "Completion projection was repaired successfully, but the surrounding run view could not be reloaded. The verified repair result is retained; refresh the run view before continuing.",
        });
      }
    } finally {
      setRepairBusy(false);
    }
  }, [onRepairCommitted, refreshSelected, selectedRunId, userId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    repairKey.current = null;
    setRepairNotice(null);
  }, [selectedRunId]);

  const overview = useMemo(
    () => buildCompletionOverview(runs, completionByRun, unavailable),
    [completionByRun, runs, unavailable],
  );

  return {
    selected: selectedRunId ? completionByRun[selectedRunId] ?? null : null,
    selectedUnavailable: Boolean(selectedRunId && unavailable.has(selectedRunId)),
    loading,
    overview,
    refreshSelected,
    repairBusy,
    repairNotice,
    repairSelected,
  };
}
