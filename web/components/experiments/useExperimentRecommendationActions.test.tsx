import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useExperimentRecommendationActions } from "./useExperimentRecommendationActions";
import type { ExperimentMetric, ExperimentRun, ExperimentVariant } from "../../lib/types";
import {
  getNextTestRecommendation,
  listExperimentMetrics,
  listExperimentRuns,
} from "../../lib/api";

vi.mock("../../lib/api", () => ({
  createExperimentVariant: vi.fn(),
  getNextTestRecommendation: vi.fn(),
  listExperimentMetrics: vi.fn(),
  listExperimentRuns: vi.fn(),
  listExperimentVariants: vi.fn(),
}));

const getNextTestRecommendationMock = vi.mocked(getNextTestRecommendation);
const listExperimentRunsMock = vi.mocked(listExperimentRuns);
const listExperimentMetricsMock = vi.mocked(listExperimentMetrics);

function Harness({
  refreshExecutionState = vi.fn().mockResolvedValue(undefined),
  runExperimentWithSelectedMode = vi.fn().mockResolvedValue(undefined),
}: {
  refreshExecutionState?: (experimentId: string) => Promise<void>;
  runExperimentWithSelectedMode?: (experimentId: string, variantId: string) => Promise<unknown>;
}) {
  const [, setVariants] = useState<ExperimentVariant[]>([]);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [metrics, setMetrics] = useState<ExperimentMetric[]>([]);
  const [runningVariantId, setRunningVariantId] = useState<string | null>(null);
  const [, setFormError] = useState<string | null>(null);
  const [, setSubmitting] = useState(false);
  const actions = useExperimentRecommendationActions({
    labMode: "manual",
    selectedExperimentId: "experiment-1",
    userId: "user-1",
    refreshExecutionState,
    runExperimentWithSelectedMode,
    setVariants,
    setRuns,
    setMetrics,
    setRunningVariantId,
    setFormError,
    setSubmitting,
  });

  return (
    <div>
      <button type="button" onClick={actions.handleRecommendNextTest}>
        Recommend
      </button>
      <button type="button" onClick={actions.handleRunRecommended}>
        Run recommended
      </button>
      <span data-testid="variant-id">{actions.nextTest?.variant_id ?? "none"}</span>
      <span data-testid="status">{actions.nextTestStatus ?? "idle"}</span>
      <span data-testid="running-variant">{runningVariantId ?? "none"}</span>
      <span data-testid="runs-count">{runs.length}</span>
      <span data-testid="metrics-count">{metrics.length}</span>
    </div>
  );
}

describe("useExperimentRecommendationActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads a next-test recommendation and runs the recommended variant", async () => {
    const refreshExecutionState = vi.fn().mockResolvedValue(undefined);
    const runExperimentWithSelectedMode = vi.fn().mockResolvedValue(undefined);
    getNextTestRecommendationMock.mockResolvedValue({
      recommendation: {
        experiment_id: "experiment-1",
        action: "run_variant",
        reason: "Run the strongest candidate.",
        variant_id: "variant-1",
      },
    });
    listExperimentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-1",
          experiment_id: "experiment-1",
          variant_id: "variant-1",
          query_id: "query-1",
        },
      ],
    });
    listExperimentMetricsMock.mockResolvedValue({
      metrics: [
        {
          id: "metric-1",
          experiment_id: "experiment-1",
          variant_id: "variant-1",
          metrics: { score: 0.72 },
        },
      ],
    });

    render(
      <Harness
        refreshExecutionState={refreshExecutionState}
        runExperimentWithSelectedMode={runExperimentWithSelectedMode}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Recommend" }));

    expect(getNextTestRecommendationMock).toHaveBeenCalledWith("experiment-1", "user-1");
    expect(await screen.findByTestId("variant-id")).toHaveTextContent("variant-1");

    await userEvent.click(screen.getByRole("button", { name: "Run recommended" }));

    await waitFor(() => {
      expect(runExperimentWithSelectedMode).toHaveBeenCalledWith("experiment-1", "variant-1");
    });
    expect(listExperimentRunsMock).toHaveBeenCalledWith("experiment-1", "user-1");
    expect(listExperimentMetricsMock).toHaveBeenCalledWith("experiment-1", "user-1");
    expect(refreshExecutionState).toHaveBeenCalledWith("experiment-1");
    expect(screen.getByTestId("runs-count")).toHaveTextContent("1");
    expect(screen.getByTestId("metrics-count")).toHaveTextContent("1");
    expect(screen.getByTestId("running-variant")).toHaveTextContent("none");
    expect(screen.getByTestId("status")).toHaveTextContent("Recommended variant run completed.");
  });
});
