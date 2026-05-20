"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  ExperimentExecutionState,
  ExperimentHypothesis,
  ExperimentMetric,
  ExperimentRecommendation,
  ExperimentRun,
  ExperimentVariant,
  SimulationRunDetailResponse,
  ValidationSummary,
} from "../../lib/types";
import {
  getExperimentExecutionState,
  getExperimentValidationSummary,
  getSimulationRun,
  listExperimentHypotheses,
  listExperimentMetrics,
  listExperimentRecommendations,
  listExperimentRuns,
  listExperimentVariants,
} from "../../lib/api";

type Args = {
  selectedExperimentId: string | null;
  selectedExperimentBatteryId?: string | null;
  userId: string | null;
  onClearSelection?: () => void;
};

export function useExperimentSelectionData({
  selectedExperimentId,
  selectedExperimentBatteryId,
  userId,
  onClearSelection,
}: Args) {
  const [variants, setVariants] = useState<ExperimentVariant[]>([]);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [metrics, setMetrics] = useState<ExperimentMetric[]>([]);
  const [executionState, setExecutionState] =
    useState<ExperimentExecutionState | null>(null);
  const [hypotheses, setHypotheses] = useState<ExperimentHypothesis[]>([]);
  const [recommendations, setRecommendations] = useState<
    ExperimentRecommendation[]
  >([]);
  const [validationSummary, setValidationSummary] =
    useState<ValidationSummary | null>(null);
  const [simulationDetails, setSimulationDetails] = useState<
    Record<string, SimulationRunDetailResponse["run"]>
  >({});

  const refreshExecutionState = useCallback(
    async (experimentId: string) => {
      try {
        const response = await getExperimentExecutionState(experimentId, userId);
        setExecutionState(response.state ?? null);
      } catch {
        setExecutionState(null);
      }
    },
    [userId],
  );

  useEffect(() => {
    if (!selectedExperimentId) {
      setVariants([]);
      setRuns([]);
      setMetrics([]);
      setExecutionState(null);
      setHypotheses([]);
      setRecommendations([]);
      setValidationSummary(null);
      onClearSelection?.();
      return;
    }
    void listExperimentVariants(selectedExperimentId, userId).then((response) => {
      setVariants(response.variants ?? []);
    });
    void listExperimentRuns(selectedExperimentId, userId).then((response) => {
      setRuns(response.runs ?? []);
    });
    void listExperimentMetrics(selectedExperimentId, userId).then((response) => {
      setMetrics(response.metrics ?? []);
    });
    void refreshExecutionState(selectedExperimentId);
    void listExperimentHypotheses(selectedExperimentId, userId)
      .then((response) => {
        setHypotheses(response.hypotheses ?? []);
      })
      .catch(() => setHypotheses([]));
    void listExperimentRecommendations(selectedExperimentId, userId).then(
      (response) => {
        setRecommendations(response.recommendations ?? []);
      },
    );
    void getExperimentValidationSummary(selectedExperimentId, userId)
      .then((response) => {
        setValidationSummary(response.summary ?? null);
      })
      .catch(() => setValidationSummary(null));
  }, [
    onClearSelection,
    refreshExecutionState,
    selectedExperimentBatteryId,
    selectedExperimentId,
    userId,
  ]);

  useEffect(() => {
    if (!runs.length) return;
    const runIds = runs
      .map((run) => run.simulation_run_id)
      .filter((runId): runId is string => Boolean(runId));
    const pending = runIds.filter((id) => !simulationDetails[id]);
    if (!pending.length) return;
    let cancelled = false;
    Promise.all(
      pending.slice(0, 12).map(async (runId) => {
        try {
          const response = await getSimulationRun(runId, userId);
          return [runId, response.run] as const;
        } catch {
          return null;
        }
      }),
    ).then((entries) => {
      if (cancelled) return;
      const updates: Record<string, SimulationRunDetailResponse["run"]> = {};
      entries.forEach((entry) => {
        if (entry) {
          updates[entry[0]] = entry[1];
        }
      });
      if (Object.keys(updates).length) {
        setSimulationDetails((prev) => ({ ...prev, ...updates }));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [runs, simulationDetails, userId]);

  return {
    variants,
    setVariants,
    runs,
    setRuns,
    metrics,
    setMetrics,
    executionState,
    hypotheses,
    setHypotheses,
    recommendations,
    setRecommendations,
    validationSummary,
    setValidationSummary,
    simulationDetails,
    refreshExecutionState,
  };
}
