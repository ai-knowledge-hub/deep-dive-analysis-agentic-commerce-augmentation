"use client";

import { useCallback, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  ExperimentMetric,
  ExperimentRun,
  ExperimentVariant,
  NextTestRecommendation,
} from "../../lib/types";
import {
  createExperimentVariant,
  getNextTestRecommendation,
  listExperimentMetrics,
  listExperimentRuns,
  listExperimentVariants,
} from "../../lib/api";

type Args = {
  labMode: "lab" | "manual";
  selectedExperimentId: string | null;
  userId: string | null;
  refreshExecutionState: (experimentId: string) => Promise<void>;
  runExperimentWithSelectedMode: (experimentId: string, variantId: string) => Promise<unknown>;
  setVariants: Dispatch<SetStateAction<ExperimentVariant[]>>;
  setRuns: Dispatch<SetStateAction<ExperimentRun[]>>;
  setMetrics: Dispatch<SetStateAction<ExperimentMetric[]>>;
  setRunningVariantId: Dispatch<SetStateAction<string | null>>;
  setFormError: Dispatch<SetStateAction<string | null>>;
  setSubmitting: Dispatch<SetStateAction<boolean>>;
};

export function useExperimentRecommendationActions({
  labMode,
  selectedExperimentId,
  userId,
  refreshExecutionState,
  runExperimentWithSelectedMode,
  setVariants,
  setRuns,
  setMetrics,
  setRunningVariantId,
  setFormError,
  setSubmitting,
}: Args) {
  const [nextTest, setNextTest] = useState<NextTestRecommendation | null>(null);
  const [nextTestStatus, setNextTestStatus] = useState<string | null>(null);
  const [isRecommending, setIsRecommending] = useState(false);
  const [isCreatingSuggestedVariant, setIsCreatingSuggestedVariant] = useState(false);

  const handleRecommendNextTest = useCallback(async () => {
    if (!selectedExperimentId) return;
    setNextTestStatus(null);
    setIsRecommending(true);
    try {
      const response = await getNextTestRecommendation(selectedExperimentId, userId);
      setNextTest(response.recommendation);
    } catch {
      setNextTestStatus("Unable to recommend next test.");
    } finally {
      setIsRecommending(false);
    }
  }, [selectedExperimentId, userId]);

  const handleRunRecommendation = useCallback(
    async (variantId: string | null | undefined) => {
      if (!selectedExperimentId || !variantId) return;
      setRunningVariantId(variantId);
      try {
        await runExperimentWithSelectedMode(selectedExperimentId, variantId);
        const [runsResponse, metricsResponse] = await Promise.all([
          listExperimentRuns(selectedExperimentId, userId),
          listExperimentMetrics(selectedExperimentId, userId),
        ]);
        setRuns(runsResponse.runs ?? []);
        setMetrics(metricsResponse.metrics ?? []);
        await refreshExecutionState(selectedExperimentId);
        setNextTestStatus("Recommended test run completed.");
      } finally {
        setRunningVariantId(null);
      }
    },
    [
      refreshExecutionState,
      runExperimentWithSelectedMode,
      selectedExperimentId,
      setMetrics,
      setRunningVariantId,
      setRuns,
      userId,
    ],
  );

  const handleRunRecommended = useCallback(async () => {
    await handleRunRecommendation(nextTest?.variant_id);
    if (nextTest?.variant_id) {
      setNextTestStatus("Recommended variant run completed.");
    }
  }, [handleRunRecommendation, nextTest?.variant_id]);

  const createSuggestedVariant = useCallback(
    async (recommendation: NextTestRecommendation) => {
      if (!selectedExperimentId || recommendation.action !== "create_variant") {
        return;
      }
      setFormError(null);
      setIsCreatingSuggestedVariant(true);
      setSubmitting(true);
      try {
        const response = await createExperimentVariant(selectedExperimentId, {
          label: recommendation.suggested_label ?? "Hypothesis (next)",
          type: recommendation.suggested_type ?? "copy",
          payload:
            recommendation.suggested_payload &&
            typeof recommendation.suggested_payload === "object"
              ? recommendation.suggested_payload
              : {},
          user_id: userId,
        });
        const refreshed = await listExperimentVariants(selectedExperimentId, userId);
        setVariants(refreshed.variants ?? []);
        await refreshExecutionState(selectedExperimentId);
        if (labMode === "lab") {
          await runExperimentWithSelectedMode(
            selectedExperimentId,
            response.variant.id,
          );
          const [runsResponse, metricsResponse] = await Promise.all([
            listExperimentRuns(selectedExperimentId, userId),
            listExperimentMetrics(selectedExperimentId, userId),
          ]);
          setRuns(runsResponse.runs ?? []);
          setMetrics(metricsResponse.metrics ?? []);
          await refreshExecutionState(selectedExperimentId);
          setNextTestStatus(`Created and ran variant ${response.variant.label}.`);
        } else {
          setNextTestStatus(`Created variant ${response.variant.label}.`);
        }
      } catch (error) {
        setFormError(
          error instanceof Error ? error.message : "Unable to create variant.",
        );
      } finally {
        setSubmitting(false);
        setIsCreatingSuggestedVariant(false);
      }
    },
    [
      labMode,
      refreshExecutionState,
      runExperimentWithSelectedMode,
      selectedExperimentId,
      setFormError,
      setMetrics,
      setRuns,
      setSubmitting,
      setVariants,
      userId,
    ],
  );

  const handleCreateSuggestedVariant = useCallback(async () => {
    if (!nextTest) return;
    await createSuggestedVariant(nextTest);
  }, [createSuggestedVariant, nextTest]);

  return {
    nextTest,
    nextTestStatus,
    isRecommending,
    isCreatingSuggestedVariant,
    handleRecommendNextTest,
    handleRunRecommended,
    handleCreateSuggestedVariant,
    handleCreateVariantFromRecommendation: createSuggestedVariant,
    handleRunRecommendation,
  };
}
