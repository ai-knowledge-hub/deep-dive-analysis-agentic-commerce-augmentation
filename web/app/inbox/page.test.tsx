import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InboxPage from "./page";

const pushMock = vi.fn();
const listAgentRunsMock = vi.fn();
const getAgentRunMock = vi.fn();
const getAgentRunEventsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { id: "user-a" } }),
}));

vi.mock("../../components/layout/Sidebar", () => ({
  Sidebar: () => null,
}));

vi.mock("../../components/layout/DetailHeader", () => ({
  DetailHeader: ({
    title,
    actions,
  }: {
    title: string;
    actions?: ReactNode;
  }) => (
    <header>
      <h1>{title}</h1>
      {actions}
    </header>
  ),
}));

vi.mock("../../lib/api", () => ({
  listAgentRuns: (...args: unknown[]) => listAgentRunsMock(...args),
  getAgentRun: (...args: unknown[]) => getAgentRunMock(...args),
  getAgentRunEvents: (...args: unknown[]) => getAgentRunEventsMock(...args),
}));

describe("InboxPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    listAgentRunsMock.mockReset();
    getAgentRunMock.mockReset();
    getAgentRunEventsMock.mockReset();

    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-1",
          experiment_id: "exp-1",
          status: "failed",
          state: "validation_completed",
        },
        {
          id: "run-2",
          experiment_id: "exp-2",
          status: "planned",
          state: "variants_ready",
          requires_approval: true,
        },
        {
          id: "run-3",
          experiment_id: "exp-3",
          status: "running",
          state: "executing",
        },
      ],
    });

    getAgentRunMock.mockImplementation(async (runId: string) => {
      if (runId === "run-1") {
        return { run: { id: "run-1" }, actions: [] };
      }
      return {
        run: { id: "run-2" },
        actions: [
          {
            id: "act-1",
            sequence: 1,
            status: "proposed",
            capability_name: "run_variant",
            rationale: "Needs review before execution.",
          },
        ],
      };
    });

    getAgentRunEventsMock.mockImplementation(async (runId: string) => {
      if (runId === "run-1") {
        return {
          events: [
            {
              id: "evt-1",
              status: "failed",
              note: "Validation provider failed.",
              timestamp: "2026-03-18T10:00:00Z",
            },
          ],
        };
      }
      if (runId === "run-3") {
        return { events: [] };
      }
      return {
        events: [
          {
            id: "evt-2",
            status: "failed",
            is_policy_event: true,
            note: "Policy blocked promotion.",
            timestamp: "2026-03-18T11:00:00Z",
          },
        ],
      };
    });
  });

  it("renders urgency groups from bounded run detail and event data", async () => {
    render(<InboxPage />);

    await waitFor(() => expect(listAgentRunsMock).toHaveBeenCalled());
    await waitFor(() => expect(getAgentRunMock).toHaveBeenCalledTimes(1));

    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Watching")).toBeInTheDocument();
    expect((await screen.findAllByText(/Experiment exp-1 failed/i)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Validation provider failed/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Policy blocked promotion/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Experiment exp-2 needs approval/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Experiment exp-3 is running/i)).toBeInTheDocument();
  });

  it("surfaces one next action and routes decision work to interventions", async () => {
    const user = userEvent.setup();
    render(<InboxPage />);

    expect(await screen.findByText(/Start with failed work/i)).toBeInTheDocument();
    expect(screen.getByText(/Experiment exp-1 failed: Validation provider failed/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Review intervention/i }));

    expect(pushMock).toHaveBeenCalledWith("/interventions?run_id=run-1");
  });

  it("routes approval-only start actions directly to interventions", async () => {
    const user = userEvent.setup();
    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-2",
          experiment_id: "exp-2",
          status: "planned",
          state: "variants_ready",
          requires_approval: true,
        },
      ],
    });
    getAgentRunEventsMock.mockResolvedValue({ events: [] });

    render(<InboxPage />);

    expect(await screen.findByText(/Review the pending approval/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Review approval/i }));

    expect(pushMock).toHaveBeenCalledWith("/interventions?run_id=run-2");
  });
});
