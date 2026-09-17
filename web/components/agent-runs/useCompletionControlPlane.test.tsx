import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentRunCompletion } from "../../lib/completionTypes";
import { useCompletionControlPlane } from "./useCompletionControlPlane";

const getCompletion = vi.fn();
const repairCompletion = vi.fn();
const runs = [{ id: "run-a", client_id: "tenant-a" }];
const categoryRuns = [
  ...runs,
  { id: "run-b", client_id: "tenant-a" },
];

vi.mock("../../lib/api", () => ({
  getAgentRunCompletion: (...args: unknown[]) => getCompletion(...args),
  repairAgentRunCompletion: (...args: unknown[]) => repairCompletion(...args),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

function completion(state: "current" | "lagging" = "lagging"): AgentRunCompletion {
  return {
    tenant_id: "tenant-a",
    workflow_id: "run-a",
    completion_authority_required: true,
    authority_state: "current",
    authoritative_decision: {
      decision_id: "decision-a",
      decision_digest: "a".repeat(64),
      scope: { tenant_id: "tenant-a", workflow_id: "run-a", graph_revision: 1 },
      criteria_id: "criteria-a",
      criteria_digest: "b".repeat(64),
      status: "incomplete",
      evaluated_at: "2026-09-16T09:40:00Z",
      authoritative_event_sequence: 2,
      accepted_result_ids: [],
      evidence_ids: [],
      blockers: ["missing_result"],
      missing_requirements: [],
      partial_failures: {
        missing_result_task_ids: ["task-a"],
        partial_task_ids: [],
        failed_task_ids: [],
        canceled_task_ids: [],
      },
      receipt_blockers: [],
    },
    accepted_results: [],
    evidence: [],
    projection: {
      state,
      freshness: state === "current" ? "current" : "stale",
      display_status: state === "current" ? "incomplete" : "stale",
      authoritative_event_sequence: 2,
      decision_event_sequence: 2,
      projected_event_sequence: state === "current" ? 2 : 1,
      projection_lag: state === "current" ? 0 : 1,
      projection_version: 1,
    },
    repair: {
      eligible: state !== "current",
      reason: state === "current" ? "projection_current" : "projection_rebuild_available",
      last_outcome: null,
    },
  };
}

describe("useCompletionControlPlane", () => {
  beforeEach(() => {
    getCompletion.mockReset();
    repairCompletion.mockReset();
    getCompletion.mockResolvedValue({ completion: completion() });
  });

  it("reports only verified reads and preserves one repair key across a conflict retry", async () => {
    const onRepairCommitted = vi.fn().mockResolvedValue(undefined);
    repairCompletion
      .mockRejectedValueOnce(new Error("API error 409"))
      .mockResolvedValueOnce({
        command: {
          outcome: "replayed",
          command_id: "command-a",
          decision_id: "decision-a",
          decision_digest: "a".repeat(64),
          projection_version: 2,
        },
        completion: completion("current"),
      });
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted,
      }),
    );

    await waitFor(() => expect(result.current.selected).not.toBeNull());
    expect(result.current.overview).toMatchObject({
      verified: 1,
      governed: 1,
      stale: 1,
      repairEligible: 1,
      totalCursorLag: 1,
    });

    await act(async () => result.current.repairSelected());
    expect(result.current.repairNotice?.text).toMatch(/conflicted with newer lifecycle state/i);
    await act(async () => result.current.repairSelected());

    const firstKey = repairCompletion.mock.calls[0][1].idempotency_key;
    const secondKey = repairCompletion.mock.calls[1][1].idempotency_key;
    expect(firstKey).toBeTruthy();
    expect(secondKey).toBe(firstKey);
    expect(result.current.repairNotice?.text).toMatch(/replayed safely/i);
    expect(onRepairCommitted).toHaveBeenCalledTimes(1);
  });

  it("keeps conflict feedback visible and truthful when its automatic refresh fails", async () => {
    repairCompletion.mockRejectedValueOnce(new Error("API error 409"));
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted: vi.fn(),
      }),
    );
    await waitFor(() => expect(result.current.selected).not.toBeNull());
    getCompletion.mockRejectedValueOnce(new Error("API error 503"));

    await act(async () => result.current.repairSelected());

    expect(result.current.selectedUnavailable).toBe(true);
    expect(result.current.repairNotice?.text).toMatch(
      /conflicted.*could not be refreshed/i,
    );
    expect(result.current.repairNotice?.text).not.toMatch(/completion was refreshed/i);
  });

  it("preserves a successful repair when the surrounding run reload fails", async () => {
    const onRepairCommitted = vi.fn().mockRejectedValue(new Error("reload failed"));
    repairCompletion.mockResolvedValueOnce({
      command: {
        outcome: "applied",
        command_id: "command-a",
        decision_id: "decision-a",
        decision_digest: "a".repeat(64),
        projection_version: 2,
      },
      completion: completion("current"),
    });
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted,
      }),
    );
    await waitFor(() => expect(result.current.selected).not.toBeNull());

    await act(async () => result.current.repairSelected());

    expect(result.current.selected?.projection.freshness).toBe("current");
    expect(result.current.repairNotice?.text).toMatch(
      /repaired successfully.*run view could not be reloaded/i,
    );
    expect(result.current.repairNotice?.text).not.toMatch(/not accepted|retry/i);
    expect(onRepairCommitted).toHaveBeenCalledTimes(1);
    expect(repairCompletion).toHaveBeenCalledTimes(1);
  });

  it("marks failed authority reads unavailable without creating a completion claim", async () => {
    getCompletion.mockRejectedValue(new Error("API error 409"));
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted: vi.fn(),
      }),
    );

    await waitFor(() => expect(result.current.selectedUnavailable).toBe(true));
    expect(result.current.selected).toBeNull();
    expect(result.current.overview.verified).toBe(0);
    expect(result.current.overview.unavailable).toBe(1);
  });

  it("evicts a previously verified claim when a selected refresh fails", async () => {
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted: vi.fn(),
      }),
    );
    await waitFor(() => expect(result.current.overview.verified).toBe(1));

    getCompletion.mockRejectedValueOnce(new Error("API error 503"));
    await act(async () => result.current.refreshSelected());

    expect(result.current.selected).toBeNull();
    expect(result.current.selectedUnavailable).toBe(true);
    expect(result.current.overview.verified).toBe(0);
    expect(result.current.overview.unavailable).toBe(1);
  });

  it("counts incomplete runs once per blocker category instead of raw entries", async () => {
    getCompletion.mockImplementation((runId: string) => {
      const value = completion("current");
      value.workflow_id = runId;
      value.authoritative_decision = {
        ...value.authoritative_decision!,
        scope: { ...value.authoritative_decision!.scope, workflow_id: runId },
        blockers: ["missing_result", "missing_result_again"],
        missing_requirements: ["requirement-a", "requirement-b"],
        partial_failures: {
          missing_result_task_ids: ["task-a", "task-b"],
          partial_task_ids: runId === "run-a" ? ["task-c"] : [],
          failed_task_ids: [],
          canceled_task_ids: [],
        },
        receipt_blockers: ["evidence-a", "evidence-b"],
      };
      return Promise.resolve({ completion: value });
    });
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs: categoryRuns,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted: vi.fn(),
      }),
    );

    await waitFor(() => expect(result.current.overview.verified).toBe(2));

    expect(result.current.overview.incompleteRuns).toBe(2);
    expect(result.current.overview.blockerCategories).toEqual({
      declaredBlockers: 2,
      missingRequirements: 2,
      missingResults: 2,
      partialResults: 1,
      failedTasks: 0,
      canceledTasks: 0,
      receiptBlockers: 2,
    });
  });

  it("prevents an older bulk read from overwriting a newer selected refresh", async () => {
    const olderBulk = deferred<{ completion: AgentRunCompletion }>();
    const obsoleteComplete = completion("current");
    obsoleteComplete.authoritative_decision = {
      ...obsoleteComplete.authoritative_decision!,
      status: "complete",
    };
    const newerStale = completion("lagging");
    getCompletion
      .mockReturnValueOnce(olderBulk.promise)
      .mockResolvedValueOnce({ completion: newerStale });
    const { result } = renderHook(() =>
      useCompletionControlPlane({
        runs,
        selectedRunId: "run-a",
        userId: "operator-a",
        onRepairCommitted: vi.fn(),
      }),
    );
    await waitFor(() => expect(getCompletion).toHaveBeenCalledTimes(1));

    await act(async () => result.current.refreshSelected());
    expect(result.current.selected?.projection.state).toBe("lagging");

    await act(async () => olderBulk.resolve({ completion: obsoleteComplete }));
    expect(result.current.selected?.projection.state).toBe("lagging");
    expect(result.current.selected?.authoritative_decision?.status).toBe("incomplete");
  });

  it("invalidates an in-flight bulk read before clearing an empty active run set", async () => {
    const olderBulk = deferred<{ completion: AgentRunCompletion }>();
    getCompletion.mockReturnValueOnce(olderBulk.promise);
    const onRepairCommitted = vi.fn();
    const { result, rerender } = renderHook(
      ({ activeRuns }: { activeRuns: typeof runs }) =>
        useCompletionControlPlane({
          runs: activeRuns,
          selectedRunId: "run-a",
          userId: "operator-a",
          onRepairCommitted,
        }),
      { initialProps: { activeRuns: runs } },
    );
    await waitFor(() => expect(getCompletion).toHaveBeenCalledTimes(1));

    rerender({ activeRuns: [] });
    expect(result.current.overview.total).toBe(0);
    await act(async () => olderBulk.resolve({ completion: completion("current") }));

    expect(result.current.selected).toBeNull();
    expect(result.current.overview.verified).toBe(0);
  });

  it("ignores a repair response after the operator selects another run", async () => {
    const pendingRepair = deferred<{
      command: {
        outcome: "applied";
        command_id: string;
        decision_id: string;
        decision_digest: string;
        projection_version: number;
      };
      completion: AgentRunCompletion;
    }>();
    repairCompletion.mockReturnValueOnce(pendingRepair.promise);
    const runBCompletion = completion("current");
    runBCompletion.workflow_id = "run-b";
    const { result, rerender } = renderHook(
      ({ selectedRunId }: { selectedRunId: string }) =>
        useCompletionControlPlane({
          runs: categoryRuns,
          selectedRunId,
          userId: "operator-a",
          onRepairCommitted: vi.fn(),
        }),
      { initialProps: { selectedRunId: "run-a" } },
    );
    await waitFor(() => expect(result.current.selected).not.toBeNull());

    let repairPromise!: Promise<void>;
    act(() => {
      repairPromise = result.current.repairSelected();
    });
    rerender({ selectedRunId: "run-b" });
    getCompletion.mockResolvedValueOnce({ completion: runBCompletion });
    await act(async () => result.current.refreshSelected());
    await act(async () =>
      pendingRepair.resolve({
        command: {
          outcome: "applied",
          command_id: "command-a",
          decision_id: "decision-a",
          decision_digest: "a".repeat(64),
          projection_version: 2,
        },
        completion: completion("current"),
      }),
    );
    await act(async () => repairPromise);

    expect(result.current.selected?.workflow_id).toBe("run-b");
    expect(result.current.repairNotice).toBeNull();
  });
});
