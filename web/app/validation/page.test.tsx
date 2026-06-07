import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ValidationPage from "./page";

const pushMock = vi.fn();
let searchParamsValue = "experiment_id=exp-1&run_id=run-1";

const listExperimentsMock = vi.fn();
const listSimulationRunsMock = vi.fn();
const listBatteriesMock = vi.fn();
const listCopyRevisionsMock = vi.fn();
const getLlmConfigMock = vi.fn();
const listExperimentVariantsMock = vi.fn();
const listExperimentMetricsMock = vi.fn();
const getExperimentValidationSummaryMock = vi.fn();
const getBrandPredictionAccuracyMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams(searchParamsValue),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { id: "user-a" } }),
}));

vi.mock("../../components/tenant/TenantProvider", () => ({
  useTenant: () => ({ clientId: "client-a" }),
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

vi.mock("../../components/validation/ValidationFlowHeader", () => ({
  ValidationFlowHeader: ({
    onOpenExperiments,
  }: {
    onOpenExperiments: () => void;
  }) => (
    <div>
      <button onClick={onOpenExperiments}>Open Experiments</button>
    </div>
  ),
}));

vi.mock("../../lib/api", () => ({
  listExperiments: (...args: unknown[]) => listExperimentsMock(...args),
  listSimulationRuns: (...args: unknown[]) => listSimulationRunsMock(...args),
  listBatteries: (...args: unknown[]) => listBatteriesMock(...args),
  listCopyRevisions: (...args: unknown[]) => listCopyRevisionsMock(...args),
  getLlmConfig: (...args: unknown[]) => getLlmConfigMock(...args),
  listExperimentVariants: (...args: unknown[]) => listExperimentVariantsMock(...args),
  listExperimentMetrics: (...args: unknown[]) => listExperimentMetricsMock(...args),
  getExperimentValidationSummary: (...args: unknown[]) =>
    getExperimentValidationSummaryMock(...args),
  getBrandPredictionAccuracy: (...args: unknown[]) => getBrandPredictionAccuracyMock(...args),
  createValidationJob: vi.fn(),
  runValidationJob: vi.fn(),
  submitValidationExternal: vi.fn(),
  startValidationProviderRun: vi.fn(),
  getSimulationRun: vi.fn(),
  listExperimentRuns: vi.fn(),
  listBatteryQueries: vi.fn(),
  getCopyRevision: vi.fn(),
  publishCopyRevision: vi.fn(),
  logExperimentValidation: vi.fn(),
}));

describe("ValidationPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    searchParamsValue = "experiment_id=exp-1&run_id=run-1";
    listExperimentsMock.mockReset();
    listSimulationRunsMock.mockReset();
    listBatteriesMock.mockReset();
    listCopyRevisionsMock.mockReset();
    getLlmConfigMock.mockReset();
    listExperimentVariantsMock.mockReset();
    listExperimentMetricsMock.mockReset();
    getExperimentValidationSummaryMock.mockReset();
    getBrandPredictionAccuracyMock.mockReset();

    listExperimentsMock.mockResolvedValue({
      experiments: [{ id: "exp-1", name: "Experiment 1", brand_id: null }],
    });
    listSimulationRunsMock.mockResolvedValue({ runs: [] });
    listBatteriesMock.mockResolvedValue({ batteries: [] });
    listCopyRevisionsMock.mockResolvedValue({ revisions: [] });
    getLlmConfigMock.mockResolvedValue({
      active_provider: "openai",
      providers: {
        openai: {
          configured: true,
          validation_configured: true,
          validation_model: "gpt-5.2-2025-12-11",
        },
      },
    });
    listExperimentVariantsMock.mockResolvedValue({ variants: [] });
    listExperimentMetricsMock.mockResolvedValue({ metrics: [] });
    getExperimentValidationSummaryMock.mockResolvedValue({ summary: null });
    getBrandPredictionAccuracyMock.mockResolvedValue({ summary: null });
  });

  it("preserves run context for back navigation and experiment handoff", async () => {
    const user = userEvent.setup();
    render(<ValidationPage />);

    expect(await screen.findByText(/Run context preserved/i)).toBeInTheDocument();
    expect(screen.getByText(/opened from the selected run/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Paste a saved variant if needed/i)).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText(/Paste a saved variant reference if needed/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/opened from run/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^run-1$/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Back to selected run/i }));
    expect(pushMock).toHaveBeenCalledWith("/runs?experiment_id=exp-1&run_id=run-1");

    await user.click(screen.getAllByRole("button", { name: /Open Experiments/i })[0]);
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/experiments?experiment_id=exp-1&run_id=run-1");
    });
  });

  it("uses readable provider labels", async () => {
    const user = userEvent.setup();
    render(<ValidationPage />);

    await screen.findByText(/Synthetic validation signal/i);

    await user.selectOptions(screen.getByLabelText(/^Mode$/i), "provider_openai_mcp");

    expect(await screen.findByText(/External validation status/i)).toBeInTheDocument();
    expect(screen.getByText(/Setup status: Unknown/i)).toBeInTheDocument();
    expect(screen.getByText(/Result status: Waiting for result/i)).toBeInTheDocument();
    expect(screen.getByText(/Handoff reference: Not started/i)).not.toBeVisible();
    await user.click(screen.getByText(/Show provider handoff details/i));
    expect(screen.getByText(/Handoff reference: Not started/i)).toBeVisible();
    expect(screen.getByRole("option", { name: /ChatGPT provider run/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Gemini provider run/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Add result manually/i })).toBeInTheDocument();
    expect(screen.queryByText(/Provider automation status/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider receipt/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider reference/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider run id/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Return status/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider run \(ChatGPT MCP\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider run \(Gemini function\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Manual result entry/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Setup required/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Callback verified/i)).not.toBeInTheDocument();
  });

  it("uses readable copy revision option labels", async () => {
    const user = userEvent.setup();
    listCopyRevisionsMock.mockResolvedValue({
      revisions: [
        {
          id: "copy-revision-abcdef123456",
          client_id: "client-a",
          product_id: "product-1",
          source_type: "simulation_run",
          base_description: "Base copy",
          candidate_description: "Candidate copy",
          status: "ready_for_review",
        },
      ],
    });

    render(<ValidationPage />);

    await screen.findByText(/Synthetic validation signal/i);

    await user.selectOptions(screen.getByLabelText(/Entity type/i), "copy_revision");

    expect(
      await screen.findByRole("option", {
        name: /Simulation run revision · Ready for review/i,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Ref abcdef12/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/simulation_run · ready_for_review/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/copy-revision-abcdef123456/i)).not.toBeInTheDocument();
  });
});
