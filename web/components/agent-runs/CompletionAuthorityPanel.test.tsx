import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearRegistryWriteToken } from "../../lib/api/core";
import type { AgentRunCompletion } from "../../lib/completionTypes";
import {
  CompletionAuthorityPanel,
  type CompletionOverview,
} from "./CompletionAuthorityPanel";

const overview: CompletionOverview = {
  total: 3,
  verified: 3,
  governed: 2,
  legacy: 1,
  current: 1,
  stale: 1,
  repairEligible: 1,
  unavailable: 0,
  totalCursorLag: 1,
  incompleteRuns: 1,
  blockerCategories: {
    declaredBlockers: 1,
    missingRequirements: 1,
    missingResults: 1,
    partialResults: 0,
    failedTasks: 0,
    canceledTasks: 0,
    receiptBlockers: 0,
  },
};

function completion(
  patch: Partial<AgentRunCompletion> = {},
): AgentRunCompletion {
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
      blockers: [{ code: "missing_result" }],
      missing_requirements: ["requirement-a"],
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
      state: "current",
      freshness: "current",
      display_status: "incomplete",
      authoritative_event_sequence: 2,
      decision_event_sequence: 2,
      projected_event_sequence: 2,
      projection_lag: 0,
      projection_version: 1,
    },
    repair: { eligible: false, reason: "projection_current", last_outcome: null },
    ...patch,
  };
}

function renderPanel(value: AgentRunCompletion | null, props = {}) {
  return render(
    <CompletionAuthorityPanel
      completion={value}
      overview={overview}
      loading={false}
      unavailable={false}
      repairBusy={false}
      repairNotice={null}
      onRefresh={vi.fn()}
      onRepair={vi.fn()}
      {...props}
    />,
  );
}

describe("CompletionAuthorityPanel", () => {
  afterEach(() => clearRegistryWriteToken());

  it("shows verified incomplete truth and the three cursors", () => {
    renderPanel(completion());

    expect(screen.getByText("Incomplete", { selector: ".panel__badge" })).toBeInTheDocument();
    expect(screen.getByText("missing result")).toBeInTheDocument();
    expect(screen.getByText("requirement-a")).toBeInTheDocument();
    expect(screen.getByText(/Missing results \(1\): task-a/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Incomplete runs by blocker category/i)).toHaveTextContent(
      /Missing results 1/i,
    );
    expect(screen.getByText("Authority").nextElementSibling).toHaveTextContent("2");
    expect(screen.getByText("Decision").nextElementSibling).toHaveTextContent("2");
    expect(screen.getByText("Projection").nextElementSibling).toHaveTextContent("2");
  });

  it("never presents a stale complete decision as complete", () => {
    renderPanel(
      completion({
        authoritative_decision: {
          ...completion().authoritative_decision!,
          status: "complete",
        },
        projection: {
          ...completion().projection,
          state: "lagging",
          freshness: "stale",
          display_status: "stale",
          projection_lag: 1,
          projected_event_sequence: 1,
        },
        repair: {
          eligible: true,
          reason: "projection_rebuild_available",
          last_outcome: null,
        },
      }),
    );

    expect(screen.getByText(/lagging · not authoritative/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Complete$/i)).not.toBeInTheDocument();
  });

  it("labels legacy runs as non-authoritative", () => {
    renderPanel(
      completion({
        completion_authority_required: false,
        authority_state: "legacy",
        authoritative_decision: null,
        projection: {
          state: "not_governed",
          freshness: "not_governed",
          display_status: "not_governed",
          authoritative_event_sequence: null,
          decision_event_sequence: null,
          projected_event_sequence: null,
          projection_lag: null,
          projection_version: null,
        },
      }),
    );

    expect(screen.getByText(/Legacy · not governed/i)).toBeInTheDocument();
    expect(screen.getByText(/not authoritative completion evidence/i)).toBeInTheDocument();
  });

  it("requires a credential and explicit confirmation before repair", async () => {
    const user = userEvent.setup();
    const onRepair = vi.fn();
    renderPanel(
      completion({
        projection: {
          ...completion().projection,
          state: "missing",
          freshness: "stale",
          display_status: "stale",
          projected_event_sequence: null,
        },
        repair: {
          eligible: true,
          reason: "projection_rebuild_available",
          last_outcome: null,
        },
      }),
      { onRepair },
    );

    expect(screen.queryByRole("button", { name: /Repair projection/i })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/Operator access key/i), "token-a");
    await user.click(screen.getByRole("button", { name: /Use for this tab/i }));
    await user.click(screen.getByRole("button", { name: /Repair projection/i }));
    expect(onRepair).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /Confirm repair/i }));
    expect(onRepair).toHaveBeenCalledTimes(1);
  });

  it("fails closed when completion authority is unavailable", () => {
    renderPanel(null, { unavailable: true });
    expect(screen.getByRole("alert")).toHaveTextContent(/No completion claim is shown/i);
  });

  it("keeps repair conflict feedback visible when authority is unavailable", () => {
    renderPanel(null, {
      unavailable: true,
      repairNotice: {
        type: "error",
        text: "Repair conflicted, and completion authority could not be refreshed.",
      },
    });

    expect(screen.getByText(/Repair conflicted.*could not be refreshed/i)).toBeVisible();
    expect(screen.getByText(/No completion claim is shown/i)).toBeVisible();
  });
});
