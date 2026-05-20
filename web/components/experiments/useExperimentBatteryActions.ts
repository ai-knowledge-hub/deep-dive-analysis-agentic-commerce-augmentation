"use client";

import { useCallback, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  AudienceSegment,
  QueryBattery,
  QueryBatteryCandidate,
  QueryBatteryQuery,
} from "../../lib/types";
import {
  addBatteryQuery,
  createBattery,
  deleteBatteryQuery,
  generateBatteryQueries,
  listBatteries,
  listBatteryQueries,
  updateBattery,
  updateBatteryAudienceSegment,
  updateBatteryQuery,
} from "../../lib/api";
import type { BatteryGenerationReport } from "./BatteryGenerationReportNotice";

type BatteryForm = {
  name: string;
  purpose: string;
  generationMode: string;
};

type BatteryEdit = {
  name: string;
  purpose: string;
  status: string;
};

type ExperimentForm = {
  name: string;
  batteryId: string;
  hypothesis: string;
  competitorPolicy: string;
};

type Args = {
  userId: string | null;
  productId?: string | null;
  batteryForm: BatteryForm;
  batteryEdit: BatteryEdit;
  selectedBattery: QueryBattery | null;
  batterySeedQueries: string;
  batterySeedFeatures: string;
  batterySeedUseCases: string;
  batteryUseLlm: boolean;
  hasBottomUpMetadata: boolean;
  setBatteries: Dispatch<SetStateAction<QueryBattery[]>>;
  setBatteryForm: Dispatch<SetStateAction<BatteryForm>>;
  setExperimentForm: Dispatch<SetStateAction<ExperimentForm>>;
  setQueries: Dispatch<SetStateAction<QueryBatteryQuery[]>>;
  setAudienceSegments: Dispatch<SetStateAction<AudienceSegment[]>>;
  setAudienceSegmentsStatus: Dispatch<SetStateAction<string | null>>;
  setFormError: Dispatch<SetStateAction<string | null>>;
  setSubmitting: Dispatch<SetStateAction<boolean>>;
};

function parseSeedList(value: string) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function useExperimentBatteryActions({
  userId,
  productId,
  batteryForm,
  batteryEdit,
  selectedBattery,
  batterySeedQueries,
  batterySeedFeatures,
  batterySeedUseCases,
  batteryUseLlm,
  hasBottomUpMetadata,
  setBatteries,
  setBatteryForm,
  setExperimentForm,
  setQueries,
  setAudienceSegments,
  setAudienceSegmentsStatus,
  setFormError,
  setSubmitting,
}: Args) {
  const [generatedCandidates, setGeneratedCandidates] = useState<
    (QueryBatteryCandidate & { selected: boolean })[]
  >([]);
  const [isGeneratingQueries, setIsGeneratingQueries] = useState(false);
  const [batteryStatus, setBatteryStatus] = useState<string | null>(null);
  const [batteryGenerationReport, setBatteryGenerationReport] =
    useState<BatteryGenerationReport | null>(null);
  const [queryStatus, setQueryStatus] = useState<string | null>(null);

  const handleCreateBattery = useCallback(async () => {
    if (!productId || !batteryForm.name.trim()) return;
    setFormError(null);
    setBatteryStatus(null);
    setSubmitting(true);
    try {
      const response = await createBattery({
        name: batteryForm.name.trim(),
        product_id: productId,
        purpose: batteryForm.purpose || undefined,
        generation_mode: batteryForm.generationMode,
        user_id: userId,
      });
      const updated = await listBatteries(userId, productId);
      setBatteries(updated.batteries ?? []);
      setExperimentForm((prev) => ({
        ...prev,
        batteryId: response.battery.id,
      }));
      setBatteryForm({ name: "", purpose: "", generationMode: "bottom_up" });
      setBatteryStatus("Battery created.");
    } finally {
      setSubmitting(false);
    }
  }, [
    batteryForm,
    productId,
    setBatteries,
    setBatteryForm,
    setExperimentForm,
    setFormError,
    setSubmitting,
    userId,
  ]);

  const handleUpdateBattery = useCallback(async () => {
    if (!selectedBattery) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const response = await updateBattery(selectedBattery.id, {
        name: batteryEdit.name,
        purpose: batteryEdit.purpose,
        status: batteryEdit.status,
        user_id: userId,
      });
      setBatteries((current) =>
        current.map((battery) =>
          battery.id === selectedBattery.id ? response.battery : battery,
        ),
      );
      setBatteryStatus("Battery updated.");
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Unable to update battery.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [batteryEdit, selectedBattery, setBatteries, setFormError, setSubmitting, userId]);

  const handleGenerateQueries = useCallback(
    async (batteryId: string) => {
      if (!batteryId) return;
      setFormError(null);
      setSubmitting(true);
      setIsGeneratingQueries(true);
      try {
        const seedList = parseSeedList(batterySeedQueries);
        const featureSeeds = parseSeedList(batterySeedFeatures);
        const useCaseSeeds = parseSeedList(batterySeedUseCases);
        let source = batteryForm.generationMode;
        if (
          source === "bottom_up" &&
          !hasBottomUpMetadata &&
          seedList.length === 0 &&
          featureSeeds.length === 0 &&
          useCaseSeeds.length === 0
        ) {
          const confirmSwitch = window.confirm(
            "Bottom-up needs features/use-cases. Switch to top-down for this generation?",
          );
          if (!confirmSwitch) {
            setFormError("Add features/use-cases or seed queries for bottom-up.");
            setSubmitting(false);
            setIsGeneratingQueries(false);
            return;
          }
          source = "top_down";
          setBatteryForm((prev) => ({ ...prev, generationMode: "top_down" }));
          setBatteryStatus("Bottom-up metadata missing. Generated with top-down.");
        }
        const response = await generateBatteryQueries(batteryId, {
          source,
          seed_queries: seedList.length ? seedList : undefined,
          seed_features: featureSeeds.length ? featureSeeds : undefined,
          seed_use_cases: useCaseSeeds.length ? useCaseSeeds : undefined,
          user_id: userId,
          use_llm: batteryUseLlm,
          persist: false,
        });
        setBatteryGenerationReport(response.report ?? null);
        const candidates = (response.candidates ?? []).map((candidate) => ({
          ...candidate,
          selected: true,
          weight: typeof candidate.weight === "number" ? candidate.weight : 1,
        }));
        setGeneratedCandidates(candidates);
        if (response.report) {
          setBatteryStatus(
            `Accepted ${response.report.accepted_count}, rejected ${response.report.rejected_count}.`,
          );
        }
      } finally {
        setIsGeneratingQueries(false);
        setSubmitting(false);
      }
    },
    [
      batteryForm.generationMode,
      batterySeedFeatures,
      batterySeedQueries,
      batterySeedUseCases,
      batteryUseLlm,
      hasBottomUpMetadata,
      setBatteryForm,
      setFormError,
      setSubmitting,
      userId,
    ],
  );

  const handleSaveGeneratedCandidates = useCallback(
    async (batteryId: string) => {
      if (!batteryId || generatedCandidates.length === 0) return;
      setSubmitting(true);
      try {
        const selected = generatedCandidates.filter((item) => item.selected);
        for (const item of selected) {
          await addBatteryQuery(batteryId, {
            query_text: item.query_text,
            query_type: item.query_type ?? undefined,
            intent_archetype: item.intent_archetype ?? undefined,
            constraints: item.constraints ?? undefined,
            weight: typeof item.weight === "number" ? item.weight : 1,
            enabled: true,
            user_id: userId,
          });
        }
        setBatteryStatus(`Saved ${selected.length} queries to battery.`);
        const refreshed = await listBatteryQueries(batteryId, userId);
        setQueries(refreshed.queries ?? []);
        setGeneratedCandidates([]);
      } finally {
        setSubmitting(false);
      }
    },
    [generatedCandidates, setQueries, setSubmitting, userId],
  );

  const handleQueryToggle = useCallback(
    async (batteryId: string, queryId: string, enabled: boolean) => {
      setQueryStatus(null);
      try {
        const response = await updateBatteryQuery(batteryId, queryId, {
          enabled,
          user_id: userId,
        });
        setQueries((current) =>
          current.map((query) =>
            query.id === queryId ? response.query : query,
          ),
        );
        setQueryStatus("Query updated.");
      } catch (error) {
        setQueryStatus(
          error instanceof Error ? error.message : "Unable to update query.",
        );
      }
    },
    [setQueries, userId],
  );

  const handleSegmentToggle = useCallback(
    async (segmentId: string, active: boolean) => {
      if (!selectedBattery) return;
      setAudienceSegmentsStatus(null);
      try {
        const response = await updateBatteryAudienceSegment(
          selectedBattery.id,
          segmentId,
          {
            active,
            user_id: userId,
          },
        );
        setAudienceSegments((current) =>
          current.map((segment) =>
            segment.id === segmentId ? response.segment : segment,
          ),
        );
        setAudienceSegmentsStatus(
          active
            ? "Segment enabled for query generation."
            : "Segment disabled for query generation.",
        );
      } catch (error) {
        setAudienceSegmentsStatus(
          error instanceof Error ? error.message : "Unable to update segment.",
        );
      }
    },
    [selectedBattery, setAudienceSegments, setAudienceSegmentsStatus, userId],
  );

  const handleQueryWeight = useCallback(
    async (batteryId: string, queryId: string, weight: number) => {
      setQueryStatus(null);
      try {
        const response = await updateBatteryQuery(batteryId, queryId, {
          weight,
          user_id: userId,
        });
        setQueries((current) =>
          current.map((query) =>
            query.id === queryId ? response.query : query,
          ),
        );
        setQueryStatus("Query updated.");
      } catch (error) {
        setQueryStatus(
          error instanceof Error ? error.message : "Unable to update query.",
        );
      }
    },
    [setQueries, userId],
  );

  const handleQueryDelete = useCallback(
    async (batteryId: string, queryId: string) => {
      setQueryStatus(null);
      try {
        await deleteBatteryQuery(batteryId, queryId, userId);
        setQueries((current) => current.filter((query) => query.id !== queryId));
        setQueryStatus("Query deleted.");
      } catch (error) {
        setQueryStatus(
          error instanceof Error ? error.message : "Unable to delete query.",
        );
      }
    },
    [setQueries, userId],
  );

  return {
    generatedCandidates,
    setGeneratedCandidates,
    isGeneratingQueries,
    batteryStatus,
    batteryGenerationReport,
    queryStatus,
    handleCreateBattery,
    handleUpdateBattery,
    handleGenerateQueries,
    handleSaveGeneratedCandidates,
    handleQueryToggle,
    handleSegmentToggle,
    handleQueryWeight,
    handleQueryDelete,
  };
}
