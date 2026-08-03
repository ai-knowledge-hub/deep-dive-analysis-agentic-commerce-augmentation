import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SimulationPage from "./page";

const pushMock = vi.fn();
let searchParamsValue = "run_id=sim-1&experiment_id=exp-1";
const localStorageMock = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};

const listSimulationLessonsMock = vi.fn();
const listSimulationRunsMock = vi.fn();
const getSimulationRunMock = vi.fn();
const listConversationSessionsMock = vi.fn();
const listExperimentsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams(searchParamsValue),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { id: "user-a" } }),
}));

vi.mock("../../components/tenant/TenantProvider", () => ({
  useTenant: () => ({
    clientId: "client-a",
    productId: "prod-1",
    productName: "Product 1",
    brandId: null,
    setProductId: vi.fn(),
    setClientId: vi.fn(),
  }),
}));

vi.mock("../../components/layout/Sidebar", () => ({
  Sidebar: () => null,
}));

vi.mock("../../components/layout/HistoryDrawer", () => ({
  HistoryDrawer: () => null,
}));

vi.mock("../../components/layout/DetailHeader", () => ({
  DetailHeader: ({
    title,
    backLabel,
    onBack,
  }: {
    title: string;
    backLabel?: string;
    onBack?: () => void;
  }) => (
    <header>
      <h1>{title}</h1>
      {backLabel && onBack ? <button onClick={onBack}>{backLabel}</button> : null}
    </header>
  ),
}));

vi.mock("../../components/simulation/SimulationPanel", () => ({
  SimulationPanel: ({ canRun }: { canRun: boolean }) => (
    <div>Simulation Panel {canRun ? "ready" : "not ready"}</div>
  ),
}));

vi.mock("../../components/simulation/SimulationHistory", () => ({
  SimulationHistory: () => <div>Simulation History</div>,
}));

vi.mock("../../components/simulation/SimulationLessons", () => ({
  SimulationLessons: () => <div>Simulation Lessons</div>,
}));

vi.mock("../../lib/api", () => ({
  listSimulationLessons: (...args: unknown[]) => listSimulationLessonsMock(...args),
  listSimulationRuns: (...args: unknown[]) => listSimulationRunsMock(...args),
  getSimulationRun: (...args: unknown[]) => getSimulationRunMock(...args),
  listConversationSessions: (...args: unknown[]) => listConversationSessionsMock(...args),
  listExperiments: (...args: unknown[]) => listExperimentsMock(...args),
  optimizeSimulation: vi.fn(),
  retestSimulation: vi.fn(),
  runSimulation: vi.fn(),
  getConversationSnapshot: vi.fn(),
  requestBrandTone: vi.fn(),
  updateSimulationTone: vi.fn(),
  listProductsByBrand: vi.fn(),
  getBrand: vi.fn(),
  attachSimulationProduct: vi.fn(),
  deleteConversationSession: vi.fn(),
  deleteExperiment: vi.fn(),
  deleteSimulationRun: vi.fn(),
}));

describe("SimulationPage", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: localStorageMock,
      configurable: true,
    });
    pushMock.mockReset();
    searchParamsValue = "run_id=sim-1&experiment_id=exp-1";
    localStorageMock.getItem.mockReset();
    localStorageMock.setItem.mockReset();
    localStorageMock.removeItem.mockReset();
    localStorageMock.clear.mockReset();
    listSimulationLessonsMock.mockReset();
    listSimulationRunsMock.mockReset();
    getSimulationRunMock.mockReset();
    listConversationSessionsMock.mockReset();
    listExperimentsMock.mockReset();
    Element.prototype.scrollIntoView = vi.fn();

    listSimulationLessonsMock.mockResolvedValue({ lessons: [] });
    listSimulationRunsMock.mockResolvedValue({ runs: [] });
    listConversationSessionsMock.mockResolvedValue({ sessions: [] });
    listExperimentsMock.mockResolvedValue({
      experiments: [{ id: "exp-1", name: "Experiment 1" }],
    });
    getSimulationRunMock.mockResolvedValue({
      run: {
        id: "sim-1",
        query: "Find the best product",
        result: {
          winner_id: "prod-1",
          scores: [{ product_id: "prod-1", score: 0.82 }],
        },
        products: [
          {
            id: "prod-1",
            name: "Product 1",
            description: "Desc",
            source: "catalog",
          },
        ],
        retest: null,
      },
    });
  });

  it("preserves run context for back navigation and experiment handoff", async () => {
    const user = userEvent.setup();
    render(<SimulationPage />);

    expect(await screen.findByText(/Run context preserved/i)).toBeInTheDocument();
    expect(screen.getByText(/opened from the selected run/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Past simulation work/i })).toBeInTheDocument();
    expect(screen.getByText(/Past runs and lessons/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/Product 1/i)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^prod-1$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Reference history/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/opened from run/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^sim-1$/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Back to validation/i }));
    expect(pushMock).toHaveBeenCalledWith("/validation?experiment_id=exp-1&run_id=sim-1");

    await user.click(screen.getByRole("button", { name: /Open experiments/i }));
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=sim-1");
    });
  });

  it("guides the operator to the simulation workspace when setup is missing", async () => {
    const user = userEvent.setup();
    searchParamsValue = "";

    render(<SimulationPage />);

    expect(await screen.findByText(/Simulation Panel not ready/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Define scenario and products/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/Simulation workspace/i)).toHaveFocus(),
    );
    expect(screen.getByText(/Add buyer intent before running simulation/i)).toBeInTheDocument();
  });
});
