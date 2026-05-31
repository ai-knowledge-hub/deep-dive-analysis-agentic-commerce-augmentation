"use client";

import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  CopyRevision,
  ExperimentMetric,
  ExperimentRun,
  ExperimentVariant,
  LoopGeneratedVariantCandidate,
} from "../../lib/types";
import {
  createExperimentVariant,
  generateExperimentVariants,
  listExperimentMetrics,
  listExperimentRuns,
  listExperimentVariants,
} from "../../lib/api";

type VariantForm = {
  label: string;
  role: string;
  description: string;
  type: string;
  payload: string;
};

type Args = {
  userId: string | null;
  variantForm: VariantForm;
  jsonErrorVariantPayload: string | null;
  simulationRevisions: CopyRevision[];
  selectedSimulationRevisionId: string;
  loopGeneratedVariants: LoopGeneratedVariantCandidate[];
  selectedLoopCandidateIndex: number;
  coldStartGenerationStrategy: "bottom_up" | "top_down" | "both";
  ensureExperimentContext: () => Promise<string | null>;
  refreshExecutionState: (experimentId: string) => Promise<void>;
  runExperimentWithSelectedMode: (experimentId: string, variantId: string) => Promise<unknown>;
  setVariantForm: Dispatch<SetStateAction<VariantForm>>;
  setVariants: Dispatch<SetStateAction<ExperimentVariant[]>>;
  setRuns: Dispatch<SetStateAction<ExperimentRun[]>>;
  setMetrics: Dispatch<SetStateAction<ExperimentMetric[]>>;
  setFormError: Dispatch<SetStateAction<string | null>>;
  setSubmitting: Dispatch<SetStateAction<boolean>>;
  setSimulationRevisionStatus: Dispatch<SetStateAction<string | null>>;
  setLoopGeneratedVariants: Dispatch<SetStateAction<LoopGeneratedVariantCandidate[]>>;
  setSelectedLoopCandidateIndex: Dispatch<SetStateAction<number>>;
  setLoopGenerationStatus: Dispatch<SetStateAction<string | null>>;
  setIsCreatingVariant: Dispatch<SetStateAction<boolean>>;
  setIsGeneratingLoopVariant: Dispatch<SetStateAction<boolean>>;
  setVariantGenerationRequestType: Dispatch<SetStateAction<"loop" | "cold_start" | null>>;
  setIsCreatingLoopCandidateVariant: Dispatch<SetStateAction<boolean>>;
  setVariantAdvancedOpen: Dispatch<SetStateAction<boolean>>;
};

function buildLoopCandidatePayload(
  candidate: LoopGeneratedVariantCandidate,
  basePayload: Record<string, unknown> = {},
) {
  const candidatePayload =
    candidate.payload && typeof candidate.payload === "object" ? candidate.payload : {};
  return {
    ...basePayload,
    ...candidatePayload,
    source_type: "loop_evidence",
    loop_confidence: candidate.confidence,
  };
}

export function useExperimentVariantActions({
  userId,
  variantForm,
  jsonErrorVariantPayload,
  simulationRevisions,
  selectedSimulationRevisionId,
  loopGeneratedVariants,
  selectedLoopCandidateIndex,
  coldStartGenerationStrategy,
  ensureExperimentContext,
  refreshExecutionState,
  runExperimentWithSelectedMode,
  setVariantForm,
  setVariants,
  setRuns,
  setMetrics,
  setFormError,
  setSubmitting,
  setSimulationRevisionStatus,
  setLoopGeneratedVariants,
  setSelectedLoopCandidateIndex,
  setLoopGenerationStatus,
  setIsCreatingVariant,
  setIsGeneratingLoopVariant,
  setVariantGenerationRequestType,
  setIsCreatingLoopCandidateVariant,
  setVariantAdvancedOpen,
}: Args) {
  const handleCreateVariant = useCallback(async () => {
    if (jsonErrorVariantPayload) return;
    setFormError(null);
    setSubmitting(true);
    setIsCreatingVariant(true);
    try {
      const experimentId = await ensureExperimentContext();
      if (!experimentId) return;
      const basePayload =
        variantForm.payload.trim() !== "" ? JSON.parse(variantForm.payload) : {};
      const payload: Record<string, unknown> =
        basePayload && typeof basePayload === "object"
          ? { ...(basePayload as Record<string, unknown>) }
          : {};
      const description = variantForm.description.trim();
      if (description) {
        payload.description = description;
      }
      payload.role = variantForm.role;
      const normalizedLabel = variantForm.label.trim()
        ? variantForm.label.trim()
        : variantForm.role === "control"
          ? "Control (current copy)"
          : "Test idea variant";
      await createExperimentVariant(experimentId, {
        label: normalizedLabel,
        type: variantForm.type.trim() || "copy",
        payload,
        user_id: userId,
      });
      const refreshed = await listExperimentVariants(experimentId, userId);
      setVariants(refreshed.variants ?? []);
      await refreshExecutionState(experimentId);
      setVariantForm({
        label: "Test idea variant",
        role: "candidate",
        description: "",
        type: "copy",
        payload: "",
      });
      setVariantAdvancedOpen(false);
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Invalid JSON payload.",
      );
    } finally {
      setIsCreatingVariant(false);
      setSubmitting(false);
    }
  }, [
    ensureExperimentContext,
    jsonErrorVariantPayload,
    refreshExecutionState,
    setFormError,
    setIsCreatingVariant,
    setSubmitting,
    setVariantAdvancedOpen,
    setVariantForm,
    setVariants,
    userId,
    variantForm,
  ]);

  const handleUseSimulationRevision = useCallback(() => {
    setSimulationRevisionStatus(null);
    if (!selectedSimulationRevisionId) {
      setSimulationRevisionStatus("Select a simulation revision first.");
      return;
    }
    const revision = simulationRevisions.find(
      (item) => item.id === selectedSimulationRevisionId,
    );
    if (!revision) {
      setSimulationRevisionStatus("Selected simulation revision not found.");
      return;
    }
    const nextDescription = String(revision.candidate_description || "").trim();
    if (!nextDescription) {
      setSimulationRevisionStatus("Selected revision has no candidate description.");
      return;
    }

    setVariantForm((prev) => {
      let parsedPayload: Record<string, unknown> = {};
      if (prev.payload.trim()) {
        try {
          const parsed = JSON.parse(prev.payload);
          if (parsed && typeof parsed === "object") {
            parsedPayload = parsed as Record<string, unknown>;
          }
        } catch {
          return { ...prev, description: nextDescription };
        }
      }
      const nextPayload = {
        ...parsedPayload,
        source_type: "simulation_revision",
        source_revision_id: revision.id,
      };
      return {
        ...prev,
        description: nextDescription,
        payload: JSON.stringify(nextPayload, null, 2),
      };
    });
    setSimulationRevisionStatus(
      `Loaded optimized copy from simulation revision ${selectedSimulationRevisionId.slice(
        0,
        8,
      )}.`,
    );
  }, [
    selectedSimulationRevisionId,
    setSimulationRevisionStatus,
    setVariantForm,
    simulationRevisions,
  ]);

  const handleGenerateLoopVariants = useCallback(async () => {
    setLoopGenerationStatus(null);
    setVariantGenerationRequestType("loop");
    setIsGeneratingLoopVariant(true);
    try {
      const experimentId = await ensureExperimentContext();
      if (!experimentId) return;
      const response = await generateExperimentVariants(experimentId, {
        user_id: userId,
        max_candidates: 3,
        mode: "loop_evidence",
        strategy: "both",
      });
      const candidates = response.candidates ?? [];
      setLoopGeneratedVariants(candidates);
      setSelectedLoopCandidateIndex(0);
      if (candidates.length === 0) {
        setLoopGenerationStatus("No loop-generated candidates available yet.");
      } else {
        setLoopGenerationStatus(
          `Generated ${candidates.length} candidate variant${candidates.length === 1 ? "" : "s"} from experiment, simulation, and validation evidence.`,
        );
      }
    } catch (error) {
      setLoopGenerationStatus(
        error instanceof Error ? error.message : "Unable to generate loop candidates.",
      );
    } finally {
      setIsGeneratingLoopVariant(false);
      setVariantGenerationRequestType(null);
    }
  }, [
    ensureExperimentContext,
    setIsGeneratingLoopVariant,
    setLoopGeneratedVariants,
    setLoopGenerationStatus,
    setSelectedLoopCandidateIndex,
    setVariantGenerationRequestType,
    userId,
  ]);

  const handleGenerateColdStartVariants = useCallback(async () => {
    setLoopGenerationStatus(null);
    setVariantGenerationRequestType("cold_start");
    setIsGeneratingLoopVariant(true);
    try {
      const experimentId = await ensureExperimentContext();
      if (!experimentId) return;
      const response = await generateExperimentVariants(experimentId, {
        user_id: userId,
        max_candidates: 3,
        mode: "cold_start",
        strategy: coldStartGenerationStrategy,
      });
      const candidates = response.candidates ?? [];
      setLoopGeneratedVariants(candidates);
      setSelectedLoopCandidateIndex(0);
      if (candidates.length === 0) {
        setLoopGenerationStatus("No cold-start candidates available yet.");
      } else {
        setLoopGenerationStatus(
          `Generated ${candidates.length} cold-start candidate variant${candidates.length === 1 ? "" : "s"} using ${coldStartGenerationStrategy.replace("_", "-")} strategy.`,
        );
      }
    } catch (error) {
      setLoopGenerationStatus(
        error instanceof Error ? error.message : "Unable to generate cold-start candidates.",
      );
    } finally {
      setIsGeneratingLoopVariant(false);
      setVariantGenerationRequestType(null);
    }
  }, [
    coldStartGenerationStrategy,
    ensureExperimentContext,
    setIsGeneratingLoopVariant,
    setLoopGeneratedVariants,
    setLoopGenerationStatus,
    setSelectedLoopCandidateIndex,
    setVariantGenerationRequestType,
    userId,
  ]);

  const handleUseGeneratedLoopVariant = useCallback(() => {
    const candidate = loopGeneratedVariants[selectedLoopCandidateIndex];
    if (!candidate) {
      setLoopGenerationStatus("Generate and select a loop candidate first.");
      return;
    }
    setVariantForm((prev) => {
      let parsedPayload: Record<string, unknown> = {};
      if (prev.payload.trim()) {
        try {
          const parsed = JSON.parse(prev.payload);
          if (parsed && typeof parsed === "object") {
            parsedPayload = parsed as Record<string, unknown>;
          }
        } catch {
          return {
            ...prev,
            label: candidate.label || prev.label,
            description: candidate.description || prev.description,
          };
        }
      }
      const nextPayload = buildLoopCandidatePayload(candidate, parsedPayload);
      return {
        ...prev,
        role: "candidate",
        label: candidate.label || prev.label,
        description: candidate.description || prev.description,
        payload: JSON.stringify(nextPayload, null, 2),
      };
    });
    setLoopGenerationStatus(
      `Applied loop candidate ${selectedLoopCandidateIndex + 1} to the variant form.`,
    );
  }, [
    loopGeneratedVariants,
    selectedLoopCandidateIndex,
    setLoopGenerationStatus,
    setVariantForm,
  ]);

  const handleCreateVariantFromLoopCandidate = useCallback(async () => {
    const candidate = loopGeneratedVariants[selectedLoopCandidateIndex];
    if (!candidate) {
      setLoopGenerationStatus("Generate and select a loop candidate first.");
      return;
    }

    setFormError(null);
    setLoopGenerationStatus(null);
    setSubmitting(true);
    setIsCreatingLoopCandidateVariant(true);
    try {
      const experimentId = await ensureExperimentContext();
      if (!experimentId) return;
      const payload: Record<string, unknown> = buildLoopCandidatePayload(candidate, {
        role: "candidate",
      });
      const description = String(candidate.description || "").trim();
      if (description) {
        payload.description = description;
      }
      await createExperimentVariant(experimentId, {
        label: candidate.label?.trim() || "Test idea variant",
        type: "copy",
        payload,
        user_id: userId,
      });
      const refreshed = await listExperimentVariants(experimentId, userId);
      setVariants(refreshed.variants ?? []);
      await refreshExecutionState(experimentId);
      setLoopGenerationStatus(
        `Created variant from loop candidate ${selectedLoopCandidateIndex + 1}.`,
      );
    } catch (error) {
      setFormError(
        error instanceof Error
          ? error.message
          : "Unable to create variant from selected loop candidate.",
      );
    } finally {
      setIsCreatingLoopCandidateVariant(false);
      setSubmitting(false);
    }
  }, [
    ensureExperimentContext,
    loopGeneratedVariants,
    refreshExecutionState,
    selectedLoopCandidateIndex,
    setFormError,
    setIsCreatingLoopCandidateVariant,
    setLoopGenerationStatus,
    setSubmitting,
    setVariants,
    userId,
  ]);

  const handleCreateAndRunVariantFromLoopCandidate = useCallback(async () => {
    const candidate = loopGeneratedVariants[selectedLoopCandidateIndex];
    if (!candidate) {
      setLoopGenerationStatus("Generate and select a loop candidate first.");
      return;
    }

    setFormError(null);
    setLoopGenerationStatus(null);
    setSubmitting(true);
    setIsCreatingLoopCandidateVariant(true);
    try {
      const experimentId = await ensureExperimentContext();
      if (!experimentId) return;
      const payload: Record<string, unknown> = buildLoopCandidatePayload(candidate, {
        role: "candidate",
      });
      const description = String(candidate.description || "").trim();
      if (description) {
        payload.description = description;
      }
      const created = await createExperimentVariant(experimentId, {
        label: candidate.label?.trim() || "Test idea variant",
        type: "copy",
        payload,
        user_id: userId,
      });
      await runExperimentWithSelectedMode(experimentId, created.variant.id);
      const [variantsResponse, runsResponse, metricsResponse] = await Promise.all([
        listExperimentVariants(experimentId, userId),
        listExperimentRuns(experimentId, userId),
        listExperimentMetrics(experimentId, userId),
      ]);
      setVariants(variantsResponse.variants ?? []);
      setRuns(runsResponse.runs ?? []);
      setMetrics(metricsResponse.metrics ?? []);
      await refreshExecutionState(experimentId);
      setLoopGenerationStatus(
        `Created and ran candidate ${selectedLoopCandidateIndex + 1}.`,
      );
    } catch (error) {
      setFormError(
        error instanceof Error
          ? error.message
          : "Unable to create and run variant from selected loop candidate.",
      );
    } finally {
      setIsCreatingLoopCandidateVariant(false);
      setSubmitting(false);
    }
  }, [
    ensureExperimentContext,
    loopGeneratedVariants,
    refreshExecutionState,
    runExperimentWithSelectedMode,
    selectedLoopCandidateIndex,
    setFormError,
    setIsCreatingLoopCandidateVariant,
    setLoopGenerationStatus,
    setMetrics,
    setRuns,
    setSubmitting,
    setVariants,
    userId,
  ]);

  return {
    handleCreateVariant,
    handleUseSimulationRevision,
    handleGenerateLoopVariants,
    handleGenerateColdStartVariants,
    handleUseGeneratedLoopVariant,
    handleCreateVariantFromLoopCandidate,
    handleCreateAndRunVariantFromLoopCandidate,
  };
}
