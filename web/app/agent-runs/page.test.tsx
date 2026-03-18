import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentRunsPage from "./page";

const pushMock = vi.fn();
const replaceMock = vi.fn();

const listAgentRunsMock = vi.fn();
const listExperimentsMock = vi.fn();
const getAgentRunMock = vi.fn();
const getAgentRunEventsMock = vi.fn();
const createAgentRunMock = vi.fn();
const decideAgentActionMock = vi.fn();
const controlAgentRunMock = vi.fn();
let searchParamsValue = "experiment_id=exp-1";

const localStorageMock = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(searchParamsValue),
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
  listExperiments: (...args: unknown[]) => listExperimentsMock(...args),
  getAgentRun: (...args: unknown[]) => getAgentRunMock(...args),
  getAgentRunEvents: (...args: unknown[]) => getAgentRunEventsMock(...args),
  createAgentRun: (...args: unknown[]) => createAgentRunMock(...args),
  decideAgentAction: (...args: unknown[]) => decideAgentActionMock(...args),
  controlAgentRun: (...args: unknown[]) => controlAgentRunMock(...args),
}));

describe("AgentRunsPage timeline presets", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: localStorageMock,
      configurable: true,
    });
    localStorageMock.getItem.mockReset();
    localStorageMock.setItem.mockReset();
    localStorageMock.removeItem.mockReset();
    localStorageMock.clear.mockReset();
    pushMock.mockReset();
    replaceMock.mockReset();
    listAgentRunsMock.mockReset();
    listExperimentsMock.mockReset();
    getAgentRunMock.mockReset();
    getAgentRunEventsMock.mockReset();
    createAgentRunMock.mockReset();
    decideAgentActionMock.mockReset();
    controlAgentRunMock.mockReset();
    searchParamsValue = "experiment_id=exp-1";
    window.localStorage.clear();

    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-1",
          experiment_id: "exp-1",
          status: "planned",
          state: "battery_ready",
          budgets: {},
          requires_approval: true,
          run_mode: "plan_only",
        },
      ],
    });
    listExperimentsMock.mockResolvedValue({ experiments: [] });
    getAgentRunMock.mockResolvedValue({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "planned",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "plan_only",
      },
      actions: [],
    });
    getAgentRunEventsMock.mockResolvedValue({
      events: [],
      page: {
        before_cursor: null,
        after_cursor: null,
        has_more_before: false,
        has_more_after: false,
      },
    });
    createAgentRunMock.mockResolvedValue({ run: { id: "run-2" } });
    decideAgentActionMock.mockResolvedValue({});
    controlAgentRunMock.mockResolvedValue({});
  });

  it("applies Policy failures preset to event query payload", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Policy failures \(24h\)/i });

    getAgentRunEventsMock.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /Policy failures \(24h\)/i }));

    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    const lastCall = getAgentRunEventsMock.mock.calls.at(-1);
    expect(lastCall).toBeTruthy();
    const payload = lastCall?.[1] as Record<string, unknown>;
    expect(payload.event_type).toBe("policy");
    expect(payload.status).toBe("failed");
    expect(typeof payload.since).toBe("string");
  });

  it("shows custom view badge when filters diverge from presets", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Policy failures \(24h\)/i });

    await userEvent.click(screen.getByRole("button", { name: /Policy failures \(24h\)/i }));
    const filters = screen.getAllByRole("combobox");
    await userEvent.selectOptions(filters[0], "executed");

    await waitFor(() => {
      expect(screen.getByText("Custom view")).toBeInTheDocument();
    });
  });

  it("syncs timeline preset state into URL query params", async () => {
    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await screen.findByRole("button", { name: /Policy failures \(24h\)/i });

    replaceMock.mockClear();
    await userEvent.click(screen.getByRole("button", { name: /Policy failures \(24h\)/i }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    const calls = replaceMock.mock.calls.map((call) => String(call?.[0] ?? ""));
    expect(
      calls.some(
        (value) =>
          value.includes("timeline_preset=policy_failures_24h") &&
          value.includes("timeline_event_type=policy"),
      ),
    ).toBe(true);
  });

  it("requests centered recovery when deep-linked event is outside current window", async () => {
    searchParamsValue = "experiment_id=exp-1&event_id=evt-404";
    getAgentRunEventsMock
      .mockResolvedValueOnce({
        events: [],
        page: {
          before_cursor: null,
          after_cursor: null,
          has_more_before: false,
          has_more_after: false,
        },
      })
      .mockResolvedValue({
        events: [],
        page: {
          before_cursor: null,
          after_cursor: null,
          has_more_before: false,
          has_more_after: false,
        },
      });

    render(<AgentRunsPage />);
    await waitFor(() => expect(getAgentRunEventsMock).toHaveBeenCalled());
    await waitFor(() => {
      const calls = getAgentRunEventsMock.mock.calls;
      expect(
        calls.some((call) => {
          const payload = call?.[1] as Record<string, unknown> | undefined;
          return payload?.event_id === "evt-404" && payload?.around === 240;
        }),
      ).toBe(true);
    });
  });

  it("shows guardrail reason and disables approve for proposed action when run is failed", async () => {
    getAgentRunMock.mockResolvedValueOnce({
      run: {
        id: "run-1",
        experiment_id: "exp-1",
        status: "failed",
        state: "battery_ready",
        budgets: {},
        requires_approval: true,
        run_mode: "plan_only",
      },
      actions: [
        {
          id: "act-1",
          sequence: 1,
          status: "proposed",
          capability_name: "run_variant",
          capability_version: "v1",
          rationale: "run candidate",
          confidence: 0.7,
          inputs: {},
          outputs: {},
        },
      ],
    });

    render(<AgentRunsPage />);
    await waitFor(() => expect(screen.getByText("Next recommended action")).toBeInTheDocument());
    expect(
      screen.getAllByText(/Run is failed\. Start a new run or move to a healthy run state\./i)
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });
});
