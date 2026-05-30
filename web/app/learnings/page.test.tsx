import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LearningsPage from "./page";

const pushMock = vi.fn();
const getOverviewSummaryMock = vi.fn();
const getOverviewChangesMock = vi.fn();
const listAgentRunsMock = vi.fn();
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
  getOverviewSummary: (...args: unknown[]) => getOverviewSummaryMock(...args),
  getOverviewChanges: (...args: unknown[]) => getOverviewChangesMock(...args),
  listAgentRuns: (...args: unknown[]) => listAgentRunsMock(...args),
  getAgentRunEvents: (...args: unknown[]) => getAgentRunEventsMock(...args),
}));

describe("LearningsPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    getOverviewSummaryMock.mockReset();
    getOverviewChangesMock.mockReset();
    listAgentRunsMock.mockReset();
    getAgentRunEventsMock.mockReset();

    getOverviewSummaryMock.mockResolvedValue({
      kpis: {
        validation: { accuracy: 0.82, unlock_ready: false },
        protocol_readiness: { score: 0.64 },
        battery_health: { coverage_score: 0.71, redundancy_rate: 0.18 },
        simulation: { avg_lift: 0.24 },
        evidence: { avg_lift: 0.12 },
        experiments: {},
      },
    });

    getOverviewChangesMock.mockResolvedValue({
      latest_experiment: {
        name: "Variant sweep for premium landing page",
        winner_label: "Variant B",
      },
      latest_simulation_lesson: {
        summary: "Urgent buyers still miss shipping confidence signals.",
        confidence: 0.73,
      },
      top_gap_signals: [{ signal: "shipping clarity", count: 4 }],
      next_test: null,
    });

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
        },
      ],
    });

    getAgentRunEventsMock.mockResolvedValue({
      events: [
        {
          id: "evt-1",
          status: "failed",
          note: "Policy blocked publishing without additional review.",
          is_policy_event: true,
          timestamp: "2026-03-18T12:00:00Z",
        },
      ],
    });
  });

  it("renders compact learning summaries and follow-ups", async () => {
    render(<LearningsPage />);

    await waitFor(() => expect(getOverviewSummaryMock).toHaveBeenCalled());

    expect(
      await screen.findAllByText(/Variant sweep for premium landing page/i),
    ).toHaveLength(2);
    expect(screen.getByText(/Validation accuracy/i)).toBeInTheDocument();
    expect(screen.getByText(/82%/i)).toBeInTheDocument();
    expect(screen.getAllByText(/shipping clarity/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Start with close validation gaps/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Decision signals/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Execution signals/i)).toBeInTheDocument();
    expect(screen.getByText(/Review recent execution drift/i)).toBeInTheDocument();
    expect(getAgentRunEventsMock).toHaveBeenCalledTimes(1);
    expect(getAgentRunEventsMock).toHaveBeenCalledWith(
      "run-1",
      { limit: 12, event_type: "all" },
      "user-a",
    );
  });

  it("navigates from a follow-up action", async () => {
    const user = userEvent.setup();
    render(<LearningsPage />);

    await screen.findAllByText(/Close validation gaps/i);
    await user.click(screen.getAllByRole("button", { name: /Open validation/i })[0]);

    expect(pushMock).toHaveBeenCalledWith("/validation");
  });
});
