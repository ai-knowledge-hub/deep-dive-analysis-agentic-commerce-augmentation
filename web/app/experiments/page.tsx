"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  AdminProduct,
  BrandBelief,
  Experiment,
  ExperimentMetric,
  ExperimentRecommendation,
  ExperimentRun,
  ExperimentVariant,
  NextTestRecommendation,
  ValidationSummary,
  QueryBattery,
  QueryBatteryQuery,
  SessionSummary,
  SimulationGapReport,
  SimulationRunDetailResponse,
} from "../../lib/types";
import {
  createBattery,
  createExperiment,
  createExperimentVariant,
  deleteBatteryQuery,
  deleteConversationSession,
  generateBatteryQueries,
  getBatteryMetrics,
  listConversationSessions,
  listBatteries,
  updateBattery,
  updateBatteryQuery,
  listExperimentMetrics,
  listExperimentRuns,
  listExperimentVariants,
  listExperiments,
  listBatteryQueries,
  runExperiment,
  updateExperimentSchedule,
  backfillExperiment,
  getNextTestRecommendation,
  listExperimentRecommendations,
  getLatestBrandBelief,
  listBrandBeliefs,
  getSimulationRun,
  getExperimentValidationSummary,
  logExperimentValidation,
  getBrandPredictionAccuracy,
  listAdminProducts,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";
import { BrandBeliefs } from "../../components/beliefs/BrandBeliefs";
import { MLPrediction } from "../../components/experiments/MLPrediction";
import { ThompsonSamplingGauge } from "../../components/experiments/ThompsonSamplingGauge";

export default function ExperimentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { productId, productName, brandId, clientId } = useTenant();

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [labMode, setLabMode] = useState<"lab" | "manual">("lab");
  const [beliefsViewMode, setBeliefsViewMode] = useState<
    "list" | "timeline" | "trends"
  >("list");

  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(null);
  const [variants, setVariants] = useState<ExperimentVariant[]>([]);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [metrics, setMetrics] = useState<ExperimentMetric[]>([]);
  const [recommendations, setRecommendations] = useState<
    ExperimentRecommendation[]
  >([]);
  const [simulationDetails, setSimulationDetails] = useState<
    Record<string, SimulationRunDetailResponse["run"]>
  >({});
  const [beliefCount, setBeliefCount] = useState<number>(0);
  const [latestBelief, setLatestBelief] = useState<BrandBelief | null>(null);
  const [queries, setQueries] = useState<QueryBatteryQuery[]>([]);
  const [batteries, setBatteries] = useState<QueryBattery[]>([]);
  const [runningVariantId, setRunningVariantId] = useState<string | null>(null);
  const [batteryForm, setBatteryForm] = useState({
    name: "",
    purpose: "",
    generationMode: "bottom_up",
  });
  const [batteryEdit, setBatteryEdit] = useState({
    name: "",
    purpose: "",
    status: "draft",
  });
  const [batteryMetrics, setBatteryMetrics] = useState<Record<string, unknown> | null>(
    null,
  );
  const [batterySeedQueries, setBatterySeedQueries] = useState("");
  const [batteryUseLlm, setBatteryUseLlm] = useState(false);
  const [batterySeedFeatures, setBatterySeedFeatures] = useState("");
  const [batterySeedUseCases, setBatterySeedUseCases] = useState("");
  const [productDetail, setProductDetail] = useState<AdminProduct | null>(null);
  const [experimentForm, setExperimentForm] = useState({
    name: "",
    batteryId: "",
    hypothesis: "",
    competitorPolicy: "",
  });
  const [variantForm, setVariantForm] = useState({
    label: "",
    type: "copy",
    payload: "",
  });
  const [isSubmitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [batteryStatus, setBatteryStatus] = useState<string | null>(null);
  const [batteryGenerationReport, setBatteryGenerationReport] = useState<{
    accepted_count: number;
    rejected_count: number;
    required_category?: string | null;
    category_confidence?: number | null;
    category_candidates?: { category: string; score: number }[];
    clarification_required?: boolean;
    clarification_prompt?: string | null;
    regeneration_count?: number;
    acceptance_rate?: number;
    rejected?: { query_text: string; reason: string }[];
  } | null>(null);
  const [experimentStatus, setExperimentStatus] = useState<string | null>(null);
  const [queryStatus, setQueryStatus] = useState<string | null>(null);
  const [scheduleForm, setScheduleForm] = useState({
    enabled: false,
    intervalMinutes: "1440",
  });
  const [scheduleStatus, setScheduleStatus] = useState<string | null>(null);
  const [metricsTrendMetric, setMetricsTrendMetric] = useState<
    "win_rate" | "avg_score"
  >("win_rate");
  const [nextTest, setNextTest] = useState<NextTestRecommendation | null>(null);
  const [nextTestStatus, setNextTestStatus] = useState<string | null>(null);
  const [isRecommending, setIsRecommending] = useState(false);
  const [validationSummary, setValidationSummary] = useState<ValidationSummary | null>(
    null,
  );
  const [validationStatus, setValidationStatus] = useState<string | null>(null);
  const [brandAccuracy, setBrandAccuracy] = useState<ValidationSummary | null>(null);
  const [validationForm, setValidationForm] = useState({
    variantId: "",
    platform: "chatgpt",
    queryText: "",
    observedProducts: "",
    observedWinnerVariantId: "",
    observedPosition: "",
    notes: "",
  });
  const [jsonErrors, setJsonErrors] = useState({
    hypothesis: null as string | null,
    competitorPolicy: null as string | null,
    variantPayload: null as string | null,
  });

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
  }, [userId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem("experiments_mode");
    if (saved === "manual" || saved === "lab") {
      setLabMode(saved);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("experiments_mode", labMode);
  }, [labMode]);

  useEffect(() => {
    void listBatteries(userId, productId ?? undefined).then((response) => {
      setBatteries(response.batteries ?? []);
    });
    void listExperiments(userId, productId ?? undefined).then((response) => {
      const items = response.experiments ?? [];
      setExperiments(items);
      if (!selectedExperimentId && items[0]?.id) {
        setSelectedExperimentId(items[0].id);
      }
    });
  }, [productId, selectedExperimentId, userId]);

  useEffect(() => {
    if (!brandId || !productId || !userId) {
      setProductDetail(null);
      return;
    }
    let active = true;
    listAdminProducts(brandId, userId)
      .then((response) => {
        if (!active) return;
        const match = (response.products ?? []).find(
          (product) => product.id === productId,
        );
        setProductDetail(match ?? null);
      })
      .catch(() => {
        if (!active) return;
        setProductDetail(null);
      });
    return () => {
      active = false;
    };
  }, [brandId, productId, userId]);

  useEffect(() => {
    const targetId = searchParams.get("experiment_id");
    if (!targetId) return;
    if (selectedExperimentId === targetId) return;
    const match = experiments.find((item) => item.id === targetId);
    if (match) {
      setSelectedExperimentId(match.id);
    }
  }, [experiments, searchParams, selectedExperimentId]);

  const selectedExperiment = useMemo(
    () => experiments.find((item) => item.id === selectedExperimentId) ?? null,
    [experiments, selectedExperimentId],
  );

  useEffect(() => {
    if (!selectedExperimentId) {
      setVariants([]);
      setRuns([]);
      setMetrics([]);
      setRecommendations([]);
      setValidationSummary(null);
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
  }, [selectedExperimentId, selectedExperiment?.battery_id, userId]);

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

  useEffect(() => {
    if (!variants.length) return;
    if (validationForm.variantId) return;
    setValidationForm((prev) => ({
      ...prev,
      variantId: variants[0]?.id ?? "",
    }));
  }, [validationForm.variantId, variants]);

  useEffect(() => {
    if (!brandId) {
      setBeliefCount(0);
      setLatestBelief(null);
      setBrandAccuracy(null);
      return;
    }
    void listBrandBeliefs(brandId, userId, 25)
      .then((response) => {
        setBeliefCount((response.beliefs ?? []).length);
      })
      .catch(() => setBeliefCount(0));
    void getLatestBrandBelief(brandId, userId)
      .then((response) => {
        setLatestBelief(response.belief ?? null);
      })
      .catch(() => setLatestBelief(null));
    void getBrandPredictionAccuracy(brandId, userId)
      .then((response) => {
        setBrandAccuracy(response.summary ?? null);
      })
      .catch(() => setBrandAccuracy(null));
  }, [brandId, userId]);

  useEffect(() => {
    const batteryId = experimentForm.batteryId || selectedExperiment?.battery_id;
    if (batteryId) {
      void listBatteryQueries(batteryId, userId).then((response) => {
        setQueries(response.queries ?? []);
      });
      void getBatteryMetrics(batteryId, userId).then((response) => {
        setBatteryMetrics(response.metrics ?? null);
      });
    } else {
      setQueries([]);
      setBatteryMetrics(null);
    }
  }, [experimentForm.batteryId, selectedExperiment?.battery_id, userId]);

  const queryMap = useMemo(() => {
    const map = new Map<string, string>();
    queries.forEach((query) => map.set(query.id, query.query_text));
    return map;
  }, [queries]);

  const selectedBattery = useMemo(
    () => batteries.find((battery) => battery.id === experimentForm.batteryId) ?? null,
    [batteries, experimentForm.batteryId],
  );

  const validateJsonField = useCallback((value: string) => {
    if (!value.trim()) return null;
    try {
      JSON.parse(value);
      return null;
    } catch (error) {
      return error instanceof Error ? error.message : "Invalid JSON";
    }
  }, []);

  useEffect(() => {
    setJsonErrors((prev) => ({
      ...prev,
      hypothesis: validateJsonField(experimentForm.hypothesis),
      competitorPolicy: validateJsonField(experimentForm.competitorPolicy),
    }));
  }, [experimentForm.hypothesis, experimentForm.competitorPolicy, validateJsonField]);

  useEffect(() => {
    setJsonErrors((prev) => ({
      ...prev,
      variantPayload: validateJsonField(variantForm.payload),
    }));
  }, [variantForm.payload, validateJsonField]);

  useEffect(() => {
    if (selectedBattery) {
      setBatteryEdit({
        name: selectedBattery.name ?? "",
        purpose: selectedBattery.purpose ?? "",
        status: selectedBattery.status ?? "draft",
      });
    }
  }, [selectedBattery]);

  useEffect(() => {
    if (selectedExperiment) {
      setScheduleForm({
        enabled: Boolean(selectedExperiment.schedule_enabled),
        intervalMinutes: String(
          selectedExperiment.schedule_interval_minutes ?? 1440,
        ),
      });
      setScheduleStatus(null);
    }
  }, [selectedExperiment]);

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await deleteConversationSession(deleteTargetId, userId);
      setSessions((current) => current.filter((item) => item.id !== deleteTargetId));
    } finally {
      setDeleteTargetId(null);
    }
  }, [deleteTargetId, userId]);

  const handleRunVariant = useCallback(
    async (variantId: string) => {
      if (!selectedExperimentId) return;
      if (labMode === "lab") {
        const ok = window.confirm(
          "Run this variant now? We'll execute the query battery and record results.",
        );
        if (!ok) return;
      }
      setRunningVariantId(variantId);
      try {
        await runExperiment(selectedExperimentId, variantId, userId);
        const [runsResponse, metricsResponse] = await Promise.all([
          listExperimentRuns(selectedExperimentId, userId),
          listExperimentMetrics(selectedExperimentId, userId),
        ]);
        setRuns(runsResponse.runs ?? []);
        setMetrics(metricsResponse.metrics ?? []);
      } finally {
        setRunningVariantId(null);
      }
    },
    [labMode, selectedExperimentId, userId],
  );

  const handleScheduleSave = useCallback(async () => {
    if (!selectedExperimentId) return;
    const interval = Number(scheduleForm.intervalMinutes);
    if (scheduleForm.enabled && (Number.isNaN(interval) || interval <= 0)) {
      setScheduleStatus("Interval must be a positive number.");
      return;
    }
    setScheduleStatus(null);
    try {
      await updateExperimentSchedule(selectedExperimentId, {
        enabled: scheduleForm.enabled,
        interval_minutes: scheduleForm.enabled ? interval : undefined,
        user_id: userId ?? undefined,
      });
      const response = await listExperiments(userId, productId ?? undefined);
      setExperiments(response.experiments ?? []);
      setScheduleStatus("Schedule updated.");
    } catch (error) {
      setScheduleStatus("Failed to update schedule.");
    }
  }, [
    productId,
    scheduleForm.enabled,
    scheduleForm.intervalMinutes,
    selectedExperimentId,
    userId,
  ]);

  const handleBackfill = useCallback(async () => {
    if (!selectedExperimentId) return;
    setScheduleStatus(null);
    try {
      await backfillExperiment(selectedExperimentId, userId);
      const experimentsResponse = await listExperiments(
        userId,
        productId ?? undefined,
      );
      setExperiments(experimentsResponse.experiments ?? []);
      const [runsResponse, metricsResponse] = await Promise.all([
        listExperimentRuns(selectedExperimentId, userId),
        listExperimentMetrics(selectedExperimentId, userId),
      ]);
      setRuns(runsResponse.runs ?? []);
      setMetrics(metricsResponse.metrics ?? []);
      setScheduleStatus("Backfill completed.");
    } catch (error) {
      setScheduleStatus("Backfill failed.");
    }
  }, [productId, selectedExperimentId, userId]);

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
  }, [batteryForm, productId, userId]);

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
  }, [batteryEdit, selectedBattery, userId]);

  const parseSeedList = useCallback((value: string) => {
    return value
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }, []);

  const hasBottomUpMetadata = useMemo(() => {
    const metadata = productDetail?.metadata ?? {};
    const features = metadata.features;
    const useCase = metadata.use_case ?? metadata.scenario;
    const hasFeatures =
      (Array.isArray(features) && features.length > 0) ||
      (typeof features === "string" && features.trim() !== "");
    const hasUseCase =
      (Array.isArray(useCase) && useCase.length > 0) ||
      (typeof useCase === "string" && useCase.trim() !== "");
    const hasIntentLabels = Boolean(metadata.intent_labels || metadata.intent_archetypes);
    const hasVertical = Boolean(metadata.vertical || metadata.domain || metadata.category);
    return hasFeatures || hasUseCase || hasIntentLabels || hasVertical;
  }, [productDetail]);

  const handleGenerateQueries = useCallback(
    async (batteryId: string) => {
      if (!batteryId) return;
      setFormError(null);
      setSubmitting(true);
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
        });
        setBatteryGenerationReport(response.report ?? null);
        if (response.report) {
          setBatteryStatus(
            `Accepted ${response.report.accepted_count}, rejected ${response.report.rejected_count}.`,
          );
        }
        const refreshed = await listBatteryQueries(batteryId, userId);
        setQueries(refreshed.queries ?? []);
      } finally {
        setSubmitting(false);
      }
    },
    [
      batterySeedFeatures,
      batterySeedQueries,
      batterySeedUseCases,
      batteryForm.generationMode,
      batteryUseLlm,
      hasBottomUpMetadata,
      parseSeedList,
      userId,
    ],
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
    [userId],
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
    [userId],
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
    [userId],
  );

  const handleCreateExperiment = useCallback(async () => {
    if (!productId || !experimentForm.name.trim()) return;
    if (jsonErrors.hypothesis || jsonErrors.competitorPolicy) return;
    setFormError(null);
    setExperimentStatus(null);
    setSubmitting(true);
    try {
      let hypothesis: Record<string, unknown> = {};
      let competitorPolicy: Record<string, unknown> = {};
      if (experimentForm.hypothesis.trim() !== "") {
        hypothesis = JSON.parse(experimentForm.hypothesis);
      }
      if (experimentForm.competitorPolicy.trim() !== "") {
        competitorPolicy = JSON.parse(experimentForm.competitorPolicy);
      }

      const buildSeedQueries = (): string[] => {
        const seeds: string[] = [];
        const rationale = String((hypothesis as Record<string, unknown>)?.rationale ?? "");
        const payload = (hypothesis as Record<string, unknown>)?.variant_payload;
        const lowered = rationale.toLowerCase();
        const productLabel = productName ?? "product";

        const keywords = lowered
          .replace(/[^a-z0-9\s]/g, " ")
          .split(/\s+/)
          .filter((word) => word.length > 3)
          .slice(0, 4);

        keywords.forEach((keyword) => {
          seeds.push(`best ${productLabel} for ${keyword}`);
          seeds.push(`${productLabel} that improves ${keyword}`);
        });

        if (lowered.includes("price") || lowered.includes("pricing") || typeof payload === "object" && payload && "pricing" in payload) {
          seeds.push(`${productLabel} under budget with strong value`);
          seeds.push(`${productLabel} on sale with best price`);
        }

        if (lowered.includes("delivery") || lowered.includes("shipping") || typeof payload === "object" && payload && "fulfillment" in payload) {
          seeds.push(`${productLabel} with fast delivery options`);
          seeds.push(`${productLabel} available for delivery this week`);
        }

        if (lowered.includes("tone") || lowered.includes("voice") || typeof payload === "object" && payload && "copy" in payload) {
          seeds.push(`${productLabel} with premium positioning`);
          seeds.push(`${productLabel} focused on outcomes and benefits`);
        }

        if (seeds.length === 0 && productLabel) {
          seeds.push(`best ${productLabel} for everyday use`);
        }

        return Array.from(new Set(seeds)).slice(0, 8);
      };

      let batteryId = experimentForm.batteryId;
      if (labMode === "lab" && !batteryId) {
        const confirmCreate = window.confirm(
          "Lab mode will create a battery, generate queries, and run a baseline variant. Continue?",
        );
        if (!confirmCreate) {
          setSubmitting(false);
          return;
        }
        const autoBatteryName = `${productName ?? "Product"} Battery`;
        const seedQueries =
          Object.keys(hypothesis).length > 0 ? buildSeedQueries() : [];
        const featureSeeds = parseSeedList(batterySeedFeatures);
        const useCaseSeeds = parseSeedList(batterySeedUseCases);
        let generationMode =
          seedQueries.length > 0 ? "hybrid" : batteryForm.generationMode;
        if (
          generationMode === "bottom_up" &&
          !hasBottomUpMetadata &&
          seedQueries.length === 0 &&
          featureSeeds.length === 0 &&
          useCaseSeeds.length === 0
        ) {
          const confirmSwitch = window.confirm(
            "Bottom-up needs features/use-cases. Switch to top-down for this generation?",
          );
          if (!confirmSwitch) {
            setFormError("Add features/use-cases or seed queries for bottom-up.");
            setSubmitting(false);
            return;
          }
          generationMode = "top_down";
          setBatteryForm((prev) => ({ ...prev, generationMode: "top_down" }));
          setBatteryStatus("Bottom-up metadata missing. Generated with top-down.");
        }
        const batteryResponse = await createBattery({
          name: autoBatteryName,
          product_id: productId,
          purpose: experimentForm.hypothesis ? "Hypothesis-driven battery" : undefined,
          generation_mode: generationMode,
          user_id: userId,
        });
        batteryId = batteryResponse.battery.id;
        const generationResponse = await generateBatteryQueries(batteryId, {
          source: generationMode,
          seed_queries: seedQueries.length > 0 ? seedQueries : undefined,
          seed_features: featureSeeds.length > 0 ? featureSeeds : undefined,
          seed_use_cases: useCaseSeeds.length > 0 ? useCaseSeeds : undefined,
          user_id: userId,
          use_llm: batteryUseLlm,
        });
        setBatteryGenerationReport(generationResponse.report ?? null);
        const refreshedBatteries = await listBatteries(userId, productId);
        setBatteries(refreshedBatteries.batteries ?? []);
        setExperimentForm((prev) => ({ ...prev, batteryId }));
      }
      const response = await createExperiment({
        name: experimentForm.name.trim(),
        product_id: productId,
        brand_id: brandId ?? undefined,
        battery_id: batteryId || undefined,
        hypothesis,
        competitor_policy: competitorPolicy,
        user_id: userId,
      });
      const refreshed = await listExperiments(userId, productId ?? undefined);
      setExperiments(refreshed.experiments ?? []);
      setSelectedExperimentId(response.experiment.id);
      if (labMode === "lab") {
        const hypothesisPayload =
          (hypothesis as Record<string, unknown>)?.variant_payload ??
          (hypothesis as Record<string, unknown>)?.payload ??
          ((hypothesis as Record<string, unknown>)?.proposed_copy
            ? { description: (hypothesis as Record<string, unknown>).proposed_copy }
            : {});
        const controlVariant = await createExperimentVariant(response.experiment.id, {
          label: "Control (current copy)",
          type: "copy",
          payload: {},
          user_id: userId,
        });
        const hypothesisVariant = await createExperimentVariant(
          response.experiment.id,
          {
            label: "Hypothesis (variant)",
            type: "copy",
            payload:
              hypothesisPayload && typeof hypothesisPayload === "object"
                ? (hypothesisPayload as Record<string, unknown>)
                : {},
            user_id: userId,
          },
        );
        await runExperiment(response.experiment.id, controlVariant.variant.id, userId);
        await runExperiment(
          response.experiment.id,
          hypothesisVariant.variant.id,
          userId,
        );
        const [runsResponse, metricsResponse] = await Promise.all([
          listExperimentRuns(response.experiment.id, userId),
          listExperimentMetrics(response.experiment.id, userId),
        ]);
        setRuns(runsResponse.runs ?? []);
        setMetrics(metricsResponse.metrics ?? []);
        setExperimentStatus("Lab mode: control + hypothesis runs completed.");
      }
      setExperimentForm({
        name: "",
        batteryId: "",
        hypothesis: "",
        competitorPolicy: "",
      });
      if (labMode !== "lab") {
        setExperimentStatus("Experiment created.");
      }
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Invalid JSON payload.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [
    batteryForm.generationMode,
    batterySeedFeatures,
    batterySeedUseCases,
    batteryUseLlm,
    brandId,
    experimentForm,
    jsonErrors,
    labMode,
    hasBottomUpMetadata,
    parseSeedList,
    productId,
    productName,
    userId,
  ]);

  const handleCreateVariant = useCallback(async () => {
    if (!selectedExperimentId || !variantForm.label.trim()) return;
    if (jsonErrors.variantPayload) return;
    setFormError(null);
    setSubmitting(true);
    try {
      const payload =
        variantForm.payload.trim() !== ""
          ? JSON.parse(variantForm.payload)
          : {};
      await createExperimentVariant(selectedExperimentId, {
        label: variantForm.label.trim(),
        type: variantForm.type.trim() || "copy",
        payload,
        user_id: userId,
      });
      const refreshed = await listExperimentVariants(selectedExperimentId, userId);
      setVariants(refreshed.variants ?? []);
      setVariantForm({ label: "", type: "copy", payload: "" });
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Invalid JSON payload.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [jsonErrors.variantPayload, selectedExperimentId, userId, variantForm]);

  const handleUseBelief = useCallback((belief: BrandBelief) => {
    const metric = belief?.metadata?.metric ?? "win_rate";
    const direction = belief?.metadata?.direction ?? "increase";
    const hypothesisPayload = {
      metric,
      direction,
      rationale: belief?.metadata?.summary ?? belief?.recommendation ?? "",
      belief_id: belief?.id,
    };
    setExperimentForm((prev) => ({
      ...prev,
      hypothesis: JSON.stringify(hypothesisPayload, null, 2),
    }));
  }, []);

  const handleRecommendNextTest = useCallback(async () => {
    if (!selectedExperimentId) return;
    setNextTestStatus(null);
    setIsRecommending(true);
    try {
      const response = await getNextTestRecommendation(
        selectedExperimentId,
        userId,
      );
      setNextTest(response.recommendation);
    } catch (error) {
      setNextTestStatus("Unable to recommend next test.");
    } finally {
      setIsRecommending(false);
    }
  }, [selectedExperimentId, userId]);

  const handleLogValidation = useCallback(async () => {
    if (!selectedExperimentId) return;
    setValidationStatus(null);
    setSubmitting(true);
    try {
      const observedProducts = validationForm.observedProducts
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await logExperimentValidation(selectedExperimentId, {
        variant_id: validationForm.variantId || undefined,
        platform: validationForm.platform || undefined,
        query_text: validationForm.queryText || undefined,
        observed_products: observedProducts,
        observed_winner_variant_id: validationForm.observedWinnerVariantId || undefined,
        observed_position: validationForm.observedPosition
          ? Number(validationForm.observedPosition)
          : undefined,
        notes: validationForm.notes || undefined,
        user_id: userId ?? undefined,
      });
      setValidationSummary(response.summary);
      setValidationStatus("Validation logged.");
      setValidationForm((prev) => ({
        ...prev,
        queryText: "",
        observedProducts: "",
        observedWinnerVariantId: "",
        observedPosition: "",
        notes: "",
      }));
    } catch {
      setValidationStatus("Unable to log validation.");
    } finally {
      setSubmitting(false);
    }
  }, [selectedExperimentId, userId, validationForm]);

  const handleRunRecommended = useCallback(async () => {
    if (!selectedExperimentId || !nextTest?.variant_id) return;
    setRunningVariantId(nextTest.variant_id);
    try {
      await runExperiment(selectedExperimentId, nextTest.variant_id, userId);
      const [runsResponse, metricsResponse] = await Promise.all([
        listExperimentRuns(selectedExperimentId, userId),
        listExperimentMetrics(selectedExperimentId, userId),
      ]);
      setRuns(runsResponse.runs ?? []);
      setMetrics(metricsResponse.metrics ?? []);
      setNextTestStatus("Recommended variant run completed.");
    } finally {
      setRunningVariantId(null);
    }
  }, [nextTest?.variant_id, selectedExperimentId, userId]);

  const handleCreateSuggestedVariant = useCallback(async () => {
    if (!selectedExperimentId || !nextTest || nextTest.action !== "create_variant") {
      return;
    }
    if (labMode === "lab") {
      const ok = window.confirm(
        "Create and run the suggested variant now?",
      );
      if (!ok) return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      const response = await createExperimentVariant(selectedExperimentId, {
        label: nextTest.suggested_label ?? "Hypothesis (next)",
        type: nextTest.suggested_type ?? "copy",
        payload:
          nextTest.suggested_payload &&
          typeof nextTest.suggested_payload === "object"
            ? nextTest.suggested_payload
            : {},
        user_id: userId,
      });
      const refreshed = await listExperimentVariants(selectedExperimentId, userId);
      setVariants(refreshed.variants ?? []);
      if (labMode === "lab") {
        await runExperiment(selectedExperimentId, response.variant.id, userId);
        const [runsResponse, metricsResponse] = await Promise.all([
          listExperimentRuns(selectedExperimentId, userId),
          listExperimentMetrics(selectedExperimentId, userId),
        ]);
        setRuns(runsResponse.runs ?? []);
        setMetrics(metricsResponse.metrics ?? []);
        setNextTestStatus(
          `Created and ran variant ${response.variant.label}.`,
        );
      } else {
        setNextTestStatus(`Created variant ${response.variant.label}.`);
      }
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Unable to create variant.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [labMode, nextTest, selectedExperimentId, userId]);

  const handleCreateVariantFromRecommendation = useCallback(
    async (recommendation: NextTestRecommendation) => {
      if (!selectedExperimentId || recommendation.action !== "create_variant") {
        return;
      }
      if (labMode === "lab") {
        const ok = window.confirm("Create and run the suggested variant now?");
        if (!ok) return;
      }
      setFormError(null);
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
        if (labMode === "lab") {
          await runExperiment(selectedExperimentId, response.variant.id, userId);
          const [runsResponse, metricsResponse] = await Promise.all([
            listExperimentRuns(selectedExperimentId, userId),
            listExperimentMetrics(selectedExperimentId, userId),
          ]);
          setRuns(runsResponse.runs ?? []);
          setMetrics(metricsResponse.metrics ?? []);
          setNextTestStatus(
            `Created and ran variant ${response.variant.label}.`,
          );
        } else {
          setNextTestStatus(`Created variant ${response.variant.label}.`);
        }
      } catch (error) {
        setFormError(
          error instanceof Error ? error.message : "Unable to create variant.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [labMode, selectedExperimentId, userId],
  );

  const handleRunRecommendation = useCallback(
    async (variantId: string | null | undefined) => {
      if (!selectedExperimentId || !variantId) return;
      if (labMode === "lab") {
        const ok = window.confirm("Run this recommended test now?");
        if (!ok) return;
      }
      setRunningVariantId(variantId);
      try {
        await runExperiment(selectedExperimentId, variantId, userId);
        const [runsResponse, metricsResponse] = await Promise.all([
          listExperimentRuns(selectedExperimentId, userId),
          listExperimentMetrics(selectedExperimentId, userId),
        ]);
        setRuns(runsResponse.runs ?? []);
        setMetrics(metricsResponse.metrics ?? []);
        setNextTestStatus("Recommended test run completed.");
      } finally {
        setRunningVariantId(null);
      }
    },
    [labMode, selectedExperimentId, userId],
  );

  const latestMetric = metrics[0]?.metrics as Record<string, unknown> | undefined;
  const beliefsRef = useRef<HTMLDivElement | null>(null);
  const metricsByVariant = useMemo(() => {
    const map = new Map<string, ExperimentMetric>();
    metrics.forEach((metric) => {
      if (!metric.variant_id) return;
      const existing = map.get(metric.variant_id);
      if (!existing || (metric.created_at || "") > (existing.created_at || "")) {
        map.set(metric.variant_id, metric);
      }
    });
    return map;
  }, [metrics]);

  const labLoopSteps = useMemo(() => {
    const hypothesisReady = Boolean(
      selectedExperiment?.hypothesis ||
        experimentForm.hypothesis.trim().length > 0,
    );
    const batteryReady = Boolean(
      selectedExperiment?.battery_id || experimentForm.batteryId,
    );
    const runActive = Boolean(runningVariantId);
    const runReady = runs.length > 0 || Boolean(selectedExperiment?.last_run_at);
    const analyzeReady = metrics.length > 0;
    const beliefReady = analyzeReady;
    const nextReady = Boolean(nextTest || recommendations.length > 0);

    return [
      {
        label: "World state",
        status: brandId ? "Ready" : "Select brand",
        tone: brandId ? "ready" : "pending",
      },
      {
        label: "Hypothesis",
        status: hypothesisReady ? "Ready" : "Draft",
        tone: hypothesisReady ? "ready" : "pending",
      },
      {
        label: "Battery",
        status: batteryReady ? "Linked" : "Pending",
        tone: batteryReady ? "ready" : "pending",
      },
      {
        label: "Run",
        status: runActive ? "Running" : runReady ? "Ready" : "Pending",
        tone: runActive ? "active" : runReady ? "ready" : "pending",
      },
      {
        label: "Analyze",
        status: analyzeReady ? "Ready" : "Pending",
        tone: analyzeReady ? "ready" : "pending",
      },
      {
        label: "Belief",
        status: beliefReady ? "Updated" : "Pending",
        tone: beliefReady ? "ready" : "pending",
      },
      {
        label: "Next test",
        status: nextReady ? "Queued" : "Pending",
        tone: nextReady ? "ready" : "pending",
      },
    ];
  }, [
    brandId,
    experimentForm.batteryId,
    experimentForm.hypothesis,
    metrics.length,
    nextTest,
    recommendations.length,
    runningVariantId,
    runs.length,
    selectedExperiment?.battery_id,
    selectedExperiment?.hypothesis,
    selectedExperiment?.last_run_at,
  ]);

  const metricsHistory = useMemo(() => {
    return [...metrics]
      .filter((metric) => metric.variant_id)
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
      .slice(0, 10);
  }, [metrics]);

  const lastRun = useMemo(() => {
    if (!runs.length) return null;
    return [...runs].sort((a, b) =>
      (b.created_at || "").localeCompare(a.created_at || ""),
    )[0];
  }, [runs]);

  const experimentGapSummary = useMemo(() => {
    const targetProductId = selectedExperiment?.product_id ?? productId ?? null;
    if (!targetProductId) return null;
    const missingCounts = new Map<string, number>();
    const winnerCounts = new Map<string, number>();
    const summaries: string[] = [];
    let sampleCount = 0;

    runs.forEach((run) => {
      if (!run.simulation_run_id) return;
      const detail = simulationDetails[run.simulation_run_id];
      if (!detail?.result?.gap_analysis) return;
      const gap =
        detail.result.gap_analysis.find(
          (item) => item.product_id === targetProductId,
        ) ?? detail.result.gap_analysis[0];
      if (!gap) return;
      (gap.missing_signals ?? []).forEach((signal: string) => {
        missingCounts.set(signal, (missingCounts.get(signal) ?? 0) + 1);
      });
      (gap.winner_signals ?? []).forEach((signal: string) => {
        winnerCounts.set(signal, (winnerCounts.get(signal) ?? 0) + 1);
      });
      if (gap.competitor_summary && sampleCount < 3) {
        summaries.push(gap.competitor_summary);
        sampleCount += 1;
      }
    });

    const sortCounts = (map: Map<string, number>) =>
      [...map.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4)
        .map(([signal, count]) => ({ signal, count }));

    return {
      missing: sortCounts(missingCounts),
      winner: sortCounts(winnerCounts),
      summaries,
      total: runs.filter((run) => Boolean(run.simulation_run_id)).length,
    };
  }, [productId, runs, selectedExperiment?.product_id, simulationDetails]);

  const perVariantGaps = useMemo(() => {
    const targetProductId = selectedExperiment?.product_id ?? productId ?? null;
    if (!targetProductId) return new Map<string, SimulationGapReport>();
    const result = new Map<string, SimulationGapReport>();
    metricsByVariant.forEach((metric, variantId) => {
      const runsForVariant = runs.filter(
        (run) => run.variant_id === variantId && run.simulation_run_id,
      );
      for (const run of runsForVariant) {
        const detail = simulationDetails[run.simulation_run_id as string];
        if (!detail?.result?.gap_analysis) continue;
        const gap =
          detail.result.gap_analysis.find(
            (item) => item.product_id === targetProductId,
          ) ?? detail.result.gap_analysis[0];
        if (gap) {
          result.set(variantId, gap as SimulationGapReport);
          break;
        }
      }
    });
    return result;
  }, [metricsByVariant, productId, runs, selectedExperiment?.product_id, simulationDetails]);

  const runGapDetails = useMemo(() => {
    const targetProductId = selectedExperiment?.product_id ?? productId ?? null;
    if (!targetProductId) return new Map<string, SimulationGapReport>();
    const result = new Map<string, SimulationGapReport>();
    runs.forEach((run) => {
      if (!run.simulation_run_id) return;
      const detail = simulationDetails[run.simulation_run_id];
      if (!detail?.result?.gap_analysis) return;
      const gap =
        detail.result.gap_analysis.find(
          (item) => item.product_id === targetProductId,
        ) ?? detail.result.gap_analysis[0];
      if (gap) {
        result.set(run.id, gap as SimulationGapReport);
      }
    });
    return result;
  }, [productId, runs, selectedExperiment?.product_id, simulationDetails]);

  const handleOpenBeliefsTimeline = useCallback(() => {
    setBeliefsViewMode("timeline");
    if (beliefsRef.current) {
      beliefsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [beliefsRef]);

  const handleUseLatestBelief = useCallback(() => {
    if (!latestBelief) return;
    handleUseBelief(latestBelief);
    setBeliefsViewMode("list");
    if (beliefsRef.current) {
      beliefsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [handleUseBelief, latestBelief, beliefsRef]);

  const metricsTrend = useMemo(() => {
    if (!metrics.length) return [];
    return [...metrics]
      .filter((metric) =>
        metricsTrendMetric === "win_rate"
          ? metric.metrics?.win_rate !== undefined
          : metric.metrics?.avg_score !== undefined,
      )
      .sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""))
      .slice(-12)
      .map((metric) =>
        Number(
          metricsTrendMetric === "win_rate"
            ? metric.metrics?.win_rate ?? 0
            : metric.metrics?.avg_score ?? 0,
        ),
      );
  }, [metrics, metricsTrendMetric]);

  const renderSparkline = (values: number[]) => {
    if (values.length === 0) return null;
    const width = 120;
    const height = 36;
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const range = max - min || 1;
    const points = values.map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    });
    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <polyline
          fill="none"
          stroke="rgba(28, 200, 134, 0.7)"
          strokeWidth="2"
          points={points.join(" ")}
        />
      </svg>
    );
  };

  const hypothesisBeliefId = useMemo(() => {
    if (!experimentForm.hypothesis.trim()) return null;
    try {
      const parsed = JSON.parse(experimentForm.hypothesis);
      return typeof parsed?.belief_id === "string" ? parsed.belief_id : null;
    } catch {
      return null;
    }
  }, [experimentForm.hypothesis]);

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/")}
        sessions={sessions}
        activeSessionId={null}
        onSelectSession={(id) => router.push(`/?session=${id}`)}
        onDeleteSession={(id) => setDeleteTargetId(id)}
        onOpenHistory={() => setHistoryOpen(true)}
      />
      <HistoryDrawer
        open={isHistoryOpen}
        closing={isHistoryClosing}
        sessions={sessions}
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(id) => router.push(`/?session=${id}`)}
        onDelete={(id) => setDeleteTargetId(id)}
        confirmDeleteId={deleteTargetId}
        onConfirmDelete={confirmDeleteSession}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Experiments"
            subtitle={
              productName
                ? `Experiment results for ${productName}`
                : "Track query batteries, variants, and outcomes."
            }
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/")}
            actions={
              <div className="summary-card__toggle">
                <button
                  type="button"
                  className={`summary-card__toggle-btn product__tooltip tooltip--below ${
                    labMode === "lab" ? "is-active" : ""
                  }`}
                  onClick={() => setLabMode("lab")}
                  data-tooltip="Lab mode auto-creates batteries, variants, and runs."
                >
                  Lab mode
                </button>
                <button
                  type="button"
                  className={`summary-card__toggle-btn product__tooltip tooltip--below ${
                    labMode === "manual" ? "is-active" : ""
                  }`}
                  onClick={() => setLabMode("manual")}
                  data-tooltip="Manual mode is controlled: you create and run each step."
                >
                  Manual
                </button>
              </div>
            }
          />
          <div className="detail__stack">
            <section className="panel__notice panel__notice--info">
              <strong>Lab signals only:</strong> Experiment results are screening
              signals from simulated judges. Validate winners with live tests
              before rollout.
            </section>
            <section className="panel__card lab-loop">
            <div className="panel__header">
              <h3>Lab Loop</h3>
              <div className="lab-loop__badges">
                <span className="panel__badge">
                  {labMode === "lab" ? "Lab mode" : "Manual mode"}
                </span>
                {selectedExperimentId ? (
                  <span className="panel__badge panel__badge--secondary">
                    Experiment active
                  </span>
                ) : null}
                {selectedExperiment?.battery_id ? (
                  <span className="panel__badge panel__badge--secondary">
                    Battery linked
                  </span>
                ) : null}
                <span className="panel__badge panel__badge--secondary">
                  {variants.length} variants
                </span>
                <span className="panel__badge panel__badge--secondary">
                  {runs.length} runs
                </span>
                <span className="panel__badge panel__badge--secondary">
                  {metrics.length} metrics
                </span>
                <span className="panel__badge panel__badge--secondary">
                  {beliefCount} beliefs
                </span>
              </div>
            </div>
            <p className="lab-loop__hint">
              The lab loop turns hypotheses into evidence and updates brand
              beliefs with every run.
            </p>
            <div className="lab-loop__steps">
              {labLoopSteps.map((step) => (
                <div key={step.label} className="lab-loop__step">
                  <span className={`lab-loop__status lab-loop__status--${step.tone}`}>
                    {step.status}
                  </span>
                  <span className="lab-loop__label">{step.label}</span>
                </div>
              ))}
            </div>
            <div className="lab-loop__summary">
              <div className="lab-loop__summary-card">
                <div className="lab-loop__summary-title">Last run</div>
                <div className="lab-loop__summary-value">
                  {lastRun?.created_at
                    ? new Date(lastRun.created_at).toLocaleString()
                    : "No runs yet"}
                </div>
                <div className="lab-loop__summary-meta">
                  {lastRun?.variant_id
                    ? `Variant: ${lastRun.variant_id}`
                    : "Run a variant to start"}
                </div>
              </div>
              <div className="lab-loop__summary-card">
                <div className="lab-loop__summary-title">Last belief</div>
                <div className="lab-loop__summary-value">
                  {latestBelief?.created_at
                    ? new Date(latestBelief.created_at).toLocaleString()
                    : "No beliefs yet"}
                </div>
                <button
                  type="button"
                  className="lab-loop__summary-meta lab-loop__summary-link"
                  onClick={handleOpenBeliefsTimeline}
                  disabled={!latestBelief}
                >
                  {latestBelief?.metadata?.summary ??
                    latestBelief?.recommendation ??
                    "Beliefs appear after results are analyzed."}
                </button>
                <div className="lab-loop__summary-actions">
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={handleOpenBeliefsTimeline}
                    disabled={!latestBelief}
                  >
                    View timeline
                  </button>
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={handleUseLatestBelief}
                    disabled={!latestBelief}
                  >
                    Use latest belief
                  </button>
                </div>
              </div>
            </div>
          </section>
          {formError ? (
            <div className="panel__notice panel__notice--error">{formError}</div>
          ) : null}
          <section className="panel__card">
            <div className="panel__header">
              <h3>Query Battery Builder</h3>
            </div>
            {productId ? (
              <div className="panel__form">
                {batteryStatus ? (
                  <p className="panel__success">{batteryStatus}</p>
                ) : null}
                <label className="panel__label">
                  Battery name
                  <input
                    className="panel__input"
                    value={batteryForm.name}
                    onChange={(event) =>
                      setBatteryForm((prev) => ({
                        ...prev,
                        name: event.target.value,
                      }))
                    }
                    placeholder="Baseline coverage"
                  />
                </label>
                <label className="panel__label">
                  Purpose
                  <input
                    className="panel__input"
                    value={batteryForm.purpose}
                    onChange={(event) =>
                      setBatteryForm((prev) => ({
                        ...prev,
                        purpose: event.target.value,
                      }))
                    }
                    placeholder="Why this battery exists"
                  />
                </label>
                <label className="panel__label">
                  Generation mode
                  <select
                    className="panel__input"
                    value={batteryForm.generationMode}
                    onChange={(event) =>
                      setBatteryForm((prev) => ({
                        ...prev,
                        generationMode: event.target.value,
                      }))
                    }
                  >
                    <option value="bottom_up">Bottom-up</option>
                    <option value="top_down">Top-down</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </label>
                <label className="panel__toggle">
                  <input
                    type="checkbox"
                    checked={batteryUseLlm}
                    onChange={(event) => setBatteryUseLlm(event.target.checked)}
                  />
                  <span>Use LLM-assisted query generation</span>
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleCreateBattery}
                  disabled={isSubmitting || batteryForm.name.trim() === ""}
                >
                  {isSubmitting ? (
                    <>
                      Creating battery<span className="button__dots" />
                    </>
                  ) : (
                    "Create battery"
                  )}
                </button>
                <label className="panel__label">
                  Seed queries (optional, one per line)
                  <textarea
                    className="panel__textarea"
                    value={batterySeedQueries}
                    onChange={(event) => setBatterySeedQueries(event.target.value)}
                    rows={3}
                  />
                </label>
                <label className="panel__label">
                  Seed features (recommended for bottom-up)
                  <textarea
                    className="panel__textarea"
                    value={batterySeedFeatures}
                    onChange={(event) => setBatterySeedFeatures(event.target.value)}
                    rows={2}
                    placeholder="lightweight cushioning, breathable upper, stable heel support"
                  />
                </label>
                <label className="panel__label">
                  Seed use-cases (recommended for bottom-up)
                  <textarea
                    className="panel__textarea"
                    value={batterySeedUseCases}
                    onChange={(event) => setBatterySeedUseCases(event.target.value)}
                    rows={2}
                    placeholder="daily training, long-distance running, injury prevention"
                  />
                </label>
                {batteryForm.generationMode === "bottom_up" && !hasBottomUpMetadata ? (
                  <div className="panel__notice panel__notice--info">
                    Bottom-up has weak product metadata. Add seed features/use-cases or we
                    will offer fallback to top-down at generation time.
                  </div>
                ) : null}
                <label className="panel__label">
                  Generate for battery
                  <select
                    className="panel__input"
                    value={experimentForm.batteryId}
                    onChange={(event) =>
                      setExperimentForm((prev) => ({
                        ...prev,
                        batteryId: event.target.value,
                      }))
                    }
                  >
                    <option value="">Select battery</option>
                    {batteries.map((battery) => (
                      <option key={battery.id} value={battery.id}>
                        {battery.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={() => handleGenerateQueries(experimentForm.batteryId)}
                  disabled={!experimentForm.batteryId || isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      Generating queries<span className="button__dots" />
                    </>
                  ) : (
                    "Generate queries"
                  )}
                </button>
                {batteryGenerationReport ? (
                  <div className="panel__notice panel__notice--info">
                    Accepted: {batteryGenerationReport.accepted_count} · Rejected:{" "}
                    {batteryGenerationReport.rejected_count}
                    {typeof batteryGenerationReport.acceptance_rate === "number" ? (
                      <>
                        {" "}
                        · Acceptance rate:{" "}
                        {Math.round(batteryGenerationReport.acceptance_rate * 100)}%
                      </>
                    ) : null}
                    {typeof batteryGenerationReport.regeneration_count === "number" ? (
                      <> · Regenerations: {batteryGenerationReport.regeneration_count}</>
                    ) : null}
                    {batteryGenerationReport.required_category ? (
                      <>
                        {" "}
                        · Required category: {batteryGenerationReport.required_category}
                      </>
                    ) : null}
                    {typeof batteryGenerationReport.category_confidence === "number" ? (
                      <>
                        {" "}
                        · Category confidence:{" "}
                        {Math.round(batteryGenerationReport.category_confidence * 100)}%
                      </>
                    ) : null}
                    {batteryGenerationReport.clarification_required &&
                    batteryGenerationReport.clarification_prompt ? (
                      <p className="panel__error">
                        {batteryGenerationReport.clarification_prompt}
                      </p>
                    ) : null}
                    {batteryGenerationReport.rejected &&
                    batteryGenerationReport.rejected.length > 0 ? (
                      <ul className="panel__list">
                        {batteryGenerationReport.rejected.slice(0, 5).map((item) => (
                          <li key={`${item.query_text}-${item.reason}`}>
                            <span className="panel__muted">{item.reason}:</span>{" "}
                            {item.query_text}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="panel__empty">Select a product to create a battery.</p>
            )}
          </section>

          <section className="panel__card">
            <div className="panel__header">
              <h3>Battery Details</h3>
            </div>
            {selectedBattery ? (
              <div className="panel__form">
                <label className="panel__label">
                  Battery name
                  <input
                    className="panel__input"
                    value={batteryEdit.name}
                    onChange={(event) =>
                      setBatteryEdit((prev) => ({
                        ...prev,
                        name: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="panel__label">
                  Purpose
                  <input
                    className="panel__input"
                    value={batteryEdit.purpose}
                    onChange={(event) =>
                      setBatteryEdit((prev) => ({
                        ...prev,
                        purpose: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="panel__label">
                  Status
                  <select
                    className="panel__input"
                    value={batteryEdit.status}
                    onChange={(event) =>
                      setBatteryEdit((prev) => ({
                        ...prev,
                        status: event.target.value,
                      }))
                    }
                  >
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="paused">Paused</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleUpdateBattery}
                  disabled={isSubmitting}
                >
                  Save battery
                </button>
                {queryStatus ? <p className="panel__success">{queryStatus}</p> : null}
                {queries.length === 0 ? (
                  <p className="panel__empty">No queries yet.</p>
                ) : (
                  <ul className="panel__list">
                    {queries.map((query) => (
                      <li key={query.id}>
                        <div className="panel__meta">
                          <span>{query.query_text}</span>
                          <label className="panel__toggle">
                            <input
                              type="checkbox"
                              checked={query.enabled}
                              onChange={(event) =>
                                handleQueryToggle(
                                  selectedBattery.id,
                                  query.id,
                                  event.target.checked,
                                )
                              }
                            />
                            <span>Enabled</span>
                          </label>
                          <button
                            type="button"
                            className="panel__action panel__action--ghost"
                            onClick={() => handleQueryDelete(selectedBattery.id, query.id)}
                          >
                            Delete
                          </button>
                        </div>
                        <div className="panel__meta">
                          <span className="panel__muted">Weight</span>
                          <input
                            className="panel__input panel__input--inline"
                            type="number"
                            step="0.1"
                            min="0"
                            defaultValue={query.weight ?? 1}
                            onBlur={(event) =>
                              handleQueryWeight(
                                selectedBattery.id,
                                query.id,
                                Number(event.target.value),
                              )
                            }
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                {batteryMetrics ? (
                  <div className="panel__metrics">
                    <p className="panel__muted">
                      Total: {batteryMetrics.total_queries ?? 0} · Enabled:{" "}
                      {batteryMetrics.enabled_queries ?? 0} · Unique:{" "}
                      {batteryMetrics.unique_queries ?? 0}
                    </p>
                    <p className="panel__muted">
                      Redundancy:{" "}
                      {batteryMetrics.redundancy_rate !== undefined
                        ? `${Number(batteryMetrics.redundancy_rate) * 100}%`
                        : "—"}
                    </p>
                    <p className="panel__muted">
                      Quality score:{" "}
                      {batteryMetrics.quality_score !== undefined
                        ? `${batteryMetrics.quality_score}/100`
                        : "—"}
                      {batteryMetrics.avg_words
                        ? ` · Avg words: ${batteryMetrics.avg_words}`
                        : ""}
                    </p>
                    {Array.isArray(batteryMetrics.quality_issues) &&
                    batteryMetrics.quality_issues.length > 0 ? (
                      <ul className="panel__list panel__list--compact">
                        {batteryMetrics.quality_issues.map((issue, index) => (
                          <li key={`${issue}-${index}`}>{issue}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="panel__empty">Select a battery to edit.</p>
            )}
          </section>

          <section className="panel__card">
            <div className="panel__header">
              <h3>Create Experiment</h3>
            </div>
            {productId ? (
              <div className="panel__form">
                {experimentStatus ? (
                  <p className="panel__success">{experimentStatus}</p>
                ) : null}
                <label className="panel__label">
                  Experiment name
                  <input
                    className="panel__input"
                    value={experimentForm.name}
                    onChange={(event) =>
                      setExperimentForm((prev) => ({
                        ...prev,
                        name: event.target.value,
                      }))
                    }
                    placeholder="Copy test for stability"
                  />
                </label>
                <label className="panel__label">
                  Battery
                  <select
                    className="panel__input"
                    value={experimentForm.batteryId}
                    onChange={(event) =>
                      setExperimentForm((prev) => ({
                        ...prev,
                        batteryId: event.target.value,
                      }))
                    }
                  >
                    <option value="">Select battery</option>
                    {batteries.map((battery) => (
                      <option key={battery.id} value={battery.id}>
                        {battery.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="panel__label">
                  Hypothesis (JSON)
                  <textarea
                    className="panel__textarea"
                    value={experimentForm.hypothesis}
                    onChange={(event) =>
                      setExperimentForm((prev) => ({
                        ...prev,
                        hypothesis: event.target.value,
                      }))
                    }
                    rows={3}
                    placeholder='{"metric":"win_rate","direction":"increase"}'
                  />
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() =>
                        setExperimentForm((prev) => ({
                          ...prev,
                          hypothesis: '{"metric":"win_rate","direction":"increase","rationale":"Outcome framing improves intent alignment"}',
                        }))
                      }
                    >
                      Use template
                    </button>
                  </div>
                  {hypothesisBeliefId ? (
                    <span className="panel__success">
                      Created from belief: {hypothesisBeliefId}
                    </span>
                  ) : null}
                  {jsonErrors.hypothesis ? (
                    <span className="panel__error">{jsonErrors.hypothesis}</span>
                  ) : null}
                </label>
                <label className="panel__label">
                  Competitor policy (JSON)
                  <textarea
                    className="panel__textarea"
                    value={experimentForm.competitorPolicy}
                    onChange={(event) =>
                      setExperimentForm((prev) => ({
                        ...prev,
                        competitorPolicy: event.target.value,
                      }))
                    }
                    rows={3}
                    placeholder='{"competitor_client_ids":["client-nike"]}'
                  />
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() =>
                        setExperimentForm((prev) => ({
                          ...prev,
                          competitorPolicy: '{"competitor_client_ids":["client-nike","client-adidas"],"strategy":"hold_constant"}',
                        }))
                      }
                    >
                      Use template
                    </button>
                  </div>
                  {jsonErrors.competitorPolicy ? (
                    <span className="panel__error">{jsonErrors.competitorPolicy}</span>
                  ) : null}
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleCreateExperiment}
                  disabled={
                    isSubmitting ||
                    experimentForm.name.trim() === "" ||
                    Boolean(jsonErrors.hypothesis || jsonErrors.competitorPolicy)
                  }
                >
                  {isSubmitting ? (
                    <>
                      Creating experiment<span className="button__dots" />
                    </>
                  ) : (
                    "Create experiment"
                  )}
                </button>
              </div>
            ) : (
              <p className="panel__empty">Select a product to create an experiment.</p>
            )}
          </section>

          <section className="panel__card">
            <div className="panel__header">
              <h3>Experiments</h3>
              <div className="panel__meta">
                {experiments.length > 0 && (
                  <span className="panel__badge">{experiments.length}</span>
                )}
              </div>
            </div>
            {experiments.length === 0 ? (
              <p className="panel__empty">No experiments yet.</p>
            ) : (
              <ul className="panel__list">
                {experiments.map((experiment) => (
                  <li key={experiment.id}>
                    <button
                      type="button"
                      className={`history-panel__item ${
                        experiment.id === selectedExperimentId ? "is-active" : ""
                      }`}
                      onClick={() => setSelectedExperimentId(experiment.id)}
                    >
                      <div className="history-panel__row">
                        <span className="history-panel__title">{experiment.name}</span>
                        {experiment.status ? (
                          <span className="panel__badge panel__badge--secondary">
                            {experiment.status}
                          </span>
                        ) : null}
                      </div>
                      {experiment.hypothesis ? (
                        <span className="history-panel__meta">
                          Hypothesis configured
                        </span>
                      ) : (
                        <span className="history-panel__meta">
                          No hypothesis yet
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="detail__grid">
            <section className="panel__card">
              <div className="panel__header">
                <h3>Variants</h3>
                <div className="panel__meta">
                  {variants.length > 0 && (
                    <span className="panel__badge">{variants.length}</span>
                  )}
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={handleRecommendNextTest}
                    disabled={!selectedExperimentId || isRecommending}
                  >
                    {isRecommending ? "Recommending…" : "Recommend next test"}
                  </button>
                </div>
              </div>
              <div className="panel__form">
                <label className="panel__label">
                  Label
                  <input
                    className="panel__input"
                    value={variantForm.label}
                    onChange={(event) =>
                      setVariantForm((prev) => ({
                        ...prev,
                        label: event.target.value,
                      }))
                    }
                    placeholder="Variant A"
                  />
                </label>
                <label className="panel__label">
                  Type
                  <input
                    className="panel__input"
                    value={variantForm.type}
                    onChange={(event) =>
                      setVariantForm((prev) => ({
                        ...prev,
                        type: event.target.value,
                      }))
                    }
                    placeholder="copy"
                  />
                </label>
                <label className="panel__label">
                  Payload (JSON)
                  <textarea
                    className="panel__textarea"
                    value={variantForm.payload}
                    onChange={(event) =>
                      setVariantForm((prev) => ({
                        ...prev,
                        payload: event.target.value,
                      }))
                    }
                    rows={3}
                    placeholder='{"description":"Updated copy"}'
                  />
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() =>
                        setVariantForm((prev) => ({
                          ...prev,
                          payload: '{"description":"Outcome-led copy that emphasizes user goals and capabilities."}',
                        }))
                      }
                    >
                      Use template
                    </button>
                  </div>
                  {jsonErrors.variantPayload ? (
                    <span className="panel__error">{jsonErrors.variantPayload}</span>
                  ) : null}
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleCreateVariant}
                  disabled={
                    isSubmitting ||
                    !selectedExperimentId ||
                    Boolean(jsonErrors.variantPayload)
                  }
                >
                  {isSubmitting ? (
                    <>
                      Adding variant<span className="button__dots" />
                    </>
                  ) : (
                    "Add variant"
                  )}
                </button>
              </div>
              {variants.length === 0 ? (
                <p className="panel__empty">Add variants to run experiments.</p>
              ) : (
                <ul className="panel__list">
                  {variants.map((variant) => (
                    <li key={variant.id}>
                      <div className="panel__meta">
                        <span>{variant.label}</span>
                        <span className="panel__badge panel__badge--secondary">
                          {variant.type}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="panel__action"
                        onClick={() => handleRunVariant(variant.id)}
                        disabled={runningVariantId === variant.id}
                      >
                        {runningVariantId === variant.id ? "Running…" : "Run battery"}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {nextTest ? (
                <div className="panel__notice">
                  <strong>Next test:</strong> {nextTest.reason}
                  {nextTest.action === "run_variant" && nextTest.variant_id ? (
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="panel__action"
                        onClick={handleRunRecommended}
                        disabled={runningVariantId === nextTest.variant_id}
                      >
                        {runningVariantId === nextTest.variant_id
                          ? "Running…"
                          : "Run recommended"}
                      </button>
                    </div>
                  ) : null}
                  {nextTest.action === "create_variant" ? (
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="panel__action"
                        onClick={handleCreateSuggestedVariant}
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <>
                            Creating variant<span className="button__dots" />
                          </>
                        ) : (
                          "Create suggested variant"
                        )}
                      </button>
                    </div>
                  ) : null}
                  {nextTest.ml_prediction ? (
                    <div className="panel__meta panel__meta--stack">
                      <MLPrediction prediction={nextTest.ml_prediction} />
                    </div>
                  ) : null}
                  {typeof nextTest.exploration_score === "number" &&
                  typeof nextTest.exploitation_score === "number" ? (
                    <div className="panel__meta panel__meta--stack">
                      <ThompsonSamplingGauge
                        explorationScore={nextTest.exploration_score}
                        exploitationScore={nextTest.exploitation_score}
                      />
                    </div>
                  ) : null}
                </div>
              ) : null}
              {nextTestStatus ? (
                <p className="panel__success">{nextTestStatus}</p>
              ) : null}
            </section>

            <section className="panel__card">
              <div className="panel__header">
                <h3>Scheduling</h3>
              </div>
              {selectedExperiment ? (
                <div className="panel__form">
                  {scheduleStatus ? (
                    <p className="panel__success">{scheduleStatus}</p>
                  ) : null}
                  <label className="panel__label">
                    Enable schedule
                    <input
                      type="checkbox"
                      checked={scheduleForm.enabled}
                      onChange={(event) =>
                        setScheduleForm((prev) => ({
                          ...prev,
                          enabled: event.target.checked,
                        }))
                      }
                    />
                  </label>
                  <label className="panel__label">
                    Interval (minutes)
                    <input
                      className="panel__input"
                      type="number"
                      min={15}
                      step={15}
                      value={scheduleForm.intervalMinutes}
                      onChange={(event) =>
                        setScheduleForm((prev) => ({
                          ...prev,
                          intervalMinutes: event.target.value,
                        }))
                      }
                      disabled={!scheduleForm.enabled}
                    />
                  </label>
                  <div className="panel__meta">
                    <span className="panel__muted">
                      Last run:{" "}
                      {selectedExperiment.last_run_at
                        ? new Date(selectedExperiment.last_run_at).toLocaleString()
                        : "—"}
                    </span>
                    <span className="panel__muted">
                      Next run:{" "}
                      {selectedExperiment.next_run_at
                        ? new Date(selectedExperiment.next_run_at).toLocaleString()
                        : "—"}
                    </span>
                  </div>
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action"
                      onClick={handleScheduleSave}
                    >
                      Save schedule
                    </button>
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={handleBackfill}
                    >
                      Backfill now
                    </button>
                  </div>
                </div>
              ) : (
                <p className="panel__empty">Select an experiment to schedule reruns.</p>
              )}
            </section>
            
            <section className="panel__card">
              <div className="panel__header">
                <h3>Latest Metrics</h3>
              </div>
              {latestMetric ? (
                <ul className="panel__list">
                  <li>Total runs: {latestMetric.total_runs ?? "-"}</li>
                  <li>Wins: {latestMetric.wins ?? "-"}</li>
                  <li>Win rate: {latestMetric.win_rate ?? "-"}</li>
                  <li>Win rate (keyword): {latestMetric.win_rate_keyword ?? "-"}</li>
                  <li>Win rate (robust): {latestMetric.win_rate_robust ?? "-"}</li>
                  <li>Avg score: {latestMetric.avg_score ?? "-"}</li>
                  <li>
                    Judge consensus win rate:{" "}
                    {latestMetric.judge_consensus_win_rate ?? "-"}
                  </li>
                </ul>
              ) : (
                <p className="panel__empty">Run a variant to generate metrics.</p>
              )}
            </section>

            <section className="panel__card">
              <div className="panel__header">
                <h3>Validation Progress</h3>
                {validationSummary?.unlock_ready ? (
                  <span className="panel__badge panel__badge--success">
                    Insights unlocked
                  </span>
                ) : (
                  <span className="panel__badge panel__badge--secondary">
                    Lab-only
                  </span>
                )}
              </div>
              <div className="panel__form">
                <div className="panel__meta panel__meta--stack">
                  <span className="panel__muted">
                    Logged validations: {validationSummary?.total_logged ?? 0}
                  </span>
                  <span className="panel__muted">
                    Verified runs: {validationSummary?.verified_runs ?? 0} / 10
                  </span>
                  <span className="panel__muted">
                    Accuracy:{" "}
                    {validationSummary
                      ? `${Math.round(validationSummary.accuracy * 100)}%`
                      : "—"}
                  </span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-bar__fill"
                    style={{
                      width: `${Math.round((validationSummary?.progress ?? 0) * 100)}%`,
                    }}
                  />
                </div>
                {brandAccuracy ? (
                  <div className="panel__meta panel__meta--stack">
                    <span className="panel__muted">
                      Brand accuracy: {Math.round(brandAccuracy.accuracy * 100)}%
                    </span>
                    <span className="panel__muted">
                      Verified (brand): {brandAccuracy.verified_runs}
                    </span>
                  </div>
                ) : null}
                <label className="panel__label">
                  Variant (lab winner)
                  <select
                    className="panel__input"
                    value={validationForm.variantId}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        variantId: event.target.value,
                      }))
                    }
                  >
                    <option value="">Select variant</option>
                    {variants.map((variant) => (
                      <option key={variant.id} value={variant.id}>
                        {variant.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="panel__label">
                  Platform
                  <select
                    className="panel__input"
                    value={validationForm.platform}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        platform: event.target.value,
                      }))
                    }
                  >
                    <option value="chatgpt">ChatGPT</option>
                    <option value="gemini">Gemini</option>
                    <option value="perplexity">Perplexity</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label className="panel__label">
                  Query tested
                  <input
                    className="panel__input"
                    value={validationForm.queryText}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        queryText: event.target.value,
                      }))
                    }
                    placeholder="e.g., running shoes for marathon training"
                  />
                </label>
                <label className="panel__label">
                  Products shown (comma-separated)
                  <input
                    className="panel__input"
                    value={validationForm.observedProducts}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        observedProducts: event.target.value,
                      }))
                    }
                    placeholder="Product A, Product B"
                  />
                </label>
                <label className="panel__label">
                  Observed winner variant (optional)
                  <input
                    className="panel__input"
                    value={validationForm.observedWinnerVariantId}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        observedWinnerVariantId: event.target.value,
                      }))
                    }
                    placeholder="Variant ID (if known)"
                  />
                </label>
                <label className="panel__label">
                  Observed position (optional)
                  <input
                    className="panel__input"
                    value={validationForm.observedPosition}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        observedPosition: event.target.value,
                      }))
                    }
                    placeholder="1"
                  />
                </label>
                <label className="panel__label">
                  Notes
                  <textarea
                    className="panel__textarea"
                    value={validationForm.notes}
                    onChange={(event) =>
                      setValidationForm((prev) => ({
                        ...prev,
                        notes: event.target.value,
                      }))
                    }
                    rows={2}
                    placeholder="Any observations..."
                  />
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleLogValidation}
                  disabled={isSubmitting || !selectedExperimentId}
                >
                  Log verification result
                </button>
                {validationStatus ? (
                  <p className="panel__success">{validationStatus}</p>
                ) : null}
              </div>
            </section>
          </div>

          {brandId ? (
            validationSummary?.unlock_ready ? (
              <div ref={(node) => (beliefsRef.current = node)}>
                <BrandBeliefs
                  brandId={brandId}
                  clientId={clientId ?? undefined}
                  userId={userId ?? undefined}
                  limit={50}
                  onUseBelief={handleUseBelief}
                  viewMode={beliefsViewMode}
                  onViewModeChange={setBeliefsViewMode}
                />
              </div>
            ) : (
              <section className="panel__card">
                <div className="panel__header">
                  <h3>Pattern Insights (Locked)</h3>
                  <span className="panel__badge panel__badge--secondary">
                    Validation required
                  </span>
                </div>
                <p className="panel__muted">
                  Unlock after 10+ verified experiments and ≥75% prediction
                  accuracy. Log live validation results to progress.
                </p>
                <div className="progress-bar">
                  <div
                    className="progress-bar__fill"
                    style={{
                      width: `${Math.round((validationSummary?.progress ?? 0) * 100)}%`,
                    }}
                  />
                </div>
                <p className="panel__muted">
                  Progress: {validationSummary?.verified_runs ?? 0}/10 verified
                </p>
              </section>
            )
          ) : null}

          <section className="panel__card">
            <div className="panel__header">
              <h3>Variant Comparison</h3>
            </div>
            {variants.length === 0 ? (
              <p className="panel__empty">Add variants to compare results.</p>
            ) : (
              <ul className="panel__list">
                {variants.map((variant) => {
                  const metric = metricsByVariant.get(variant.id);
                  const values = (metric?.metrics ?? {}) as Record<string, unknown>;
                  const gap = perVariantGaps.get(variant.id);
                  return (
                    <li key={variant.id}>
                      <div className="panel__meta">
                        <span>{variant.label}</span>
                        <span className="panel__badge panel__badge--secondary">
                          {variant.type}
                        </span>
                        {gap?.severity ? (
                          <span
                            className={`panel__badge panel__badge--severity-${gap.severity}`}
                          >
                            {gap.severity} gap
                          </span>
                        ) : null}
                      </div>
                      <div className="panel__meta">
                        <span className="panel__muted">
                          Win rate: {values.win_rate ?? "—"}
                        </span>
                        <span className="panel__muted">
                          Robust win rate: {values.win_rate_robust ?? "—"}
                        </span>
                        <span className="panel__muted">
                          Avg score: {values.avg_score ?? "—"}
                        </span>
                        <span className="panel__muted">
                          Runs: {values.total_runs ?? "—"}
                        </span>
                      </div>
                      {gap ? (
                        <div className="panel__muted">
                          Missing: {(gap.missing_signals ?? []).slice(0, 3).join(", ") || "—"}
                        </div>
                      ) : null}
                      {metric?.created_at ? (
                        <span className="panel__muted">
                          Last run:{" "}
                          {new Date(metric.created_at).toLocaleDateString()}
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="panel__card">
            <div className="panel__header">
              <h3>Why we lost (experiment deltas)</h3>
              {experimentGapSummary?.total ? (
                <span className="panel__badge panel__badge--secondary">
                  {experimentGapSummary.total} linked runs
                </span>
              ) : null}
            </div>
            {!experimentGapSummary || experimentGapSummary.total === 0 ? (
              <p className="panel__empty">
                Run a variant with linked simulations to see gap signals.
              </p>
            ) : (
              <div className="panel__grid">
                <div className="panel__column">
                  <h4 className="panel__subtitle">Top missing signals</h4>
                  {experimentGapSummary.missing.length === 0 ? (
                    <p className="panel__muted">No missing signals yet.</p>
                  ) : (
                    <ul className="panel__list panel__list--compact">
                      {experimentGapSummary.missing.map((item) => (
                        <li key={`missing-${item.signal}`}>
                          {item.signal} · {item.count}x
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="panel__column">
                  <h4 className="panel__subtitle">Winner signals</h4>
                  {experimentGapSummary.winner.length === 0 ? (
                    <p className="panel__muted">No winner signals yet.</p>
                  ) : (
                    <ul className="panel__list panel__list--compact">
                      {experimentGapSummary.winner.map((item) => (
                        <li key={`winner-${item.signal}`}>
                          {item.signal} · {item.count}x
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {experimentGapSummary.summaries.length > 0 ? (
                  <div className="panel__column">
                    <h4 className="panel__subtitle">Gap summaries</h4>
                    <ul className="panel__list panel__list--compact">
                      {experimentGapSummary.summaries.map((summary, index) => (
                        <li key={`summary-${index}`}>{summary}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}
          </section>

          <section className="panel__card">
            <div className="panel__header">
              <h3>Runs</h3>
              <div className="panel__meta">
                {runs.length > 0 && <span className="panel__badge">{runs.length}</span>}
              </div>
            </div>
            {runs.length === 0 ? (
              <p className="panel__empty">No experiment runs yet.</p>
            ) : (
              <ul className="panel__list">
                {runs.map((run) => (
                  <li key={run.id}>
                    <div className="panel__meta">
                      <span>{queryMap.get(run.query_id) ?? run.query_id}</span>
                      <span className="panel__badge panel__badge--secondary">
                        {run.simulation_run_id ? "linked" : "pending"}
                      </span>
                    </div>
                    <div className="panel__meta panel__meta--stack">
                      <span className="history-panel__meta">
                        Variant: {run.variant_id}
                      </span>
                      {run.simulation_run_id ? (
                        <span className="history-panel__meta">
                          Run ID:{" "}
                          <a
                            className="panel__link"
                            href={`/simulation?run_id=${run.simulation_run_id}`}
                          >
                            {run.simulation_run_id}
                          </a>
                        </span>
                      ) : null}
                      {runGapDetails.get(run.id) ? (
                        <span className="history-panel__meta">
                          Gap:{" "}
                          {runGapDetails
                            .get(run.id)
                            ?.missing_signals?.slice(0, 3)
                            .join(", ") || "—"}
                        </span>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel__card">
            <div className="panel__header">
              <h3>Metrics History</h3>
              <div className="panel__meta">
                {renderSparkline(metricsTrend) ?? (
                  <span className="panel__muted">No trend yet.</span>
                )}
              </div>
            </div>
            <div className="panel__actions">
              <button
                type="button"
                className={`panel__action panel__action--ghost ${
                  metricsTrendMetric === "win_rate" ? "is-active" : ""
                }`}
                onClick={() => setMetricsTrendMetric("win_rate")}
              >
                Win rate
              </button>
              <button
                type="button"
                className={`panel__action panel__action--ghost ${
                  metricsTrendMetric === "avg_score" ? "is-active" : ""
                }`}
                onClick={() => setMetricsTrendMetric("avg_score")}
              >
                Avg score
              </button>
            </div>
            {metricsHistory.length === 0 ? (
              <p className="panel__empty">No metrics history yet.</p>
            ) : (
              <ul className="panel__list">
                {metricsHistory.map((metric) => {
                  const values = (metric.metrics ?? {}) as Record<string, unknown>;
                  const variantLabel =
                    variants.find((variant) => variant.id === metric.variant_id)
                      ?.label ?? metric.variant_id;
                  return (
                    <li key={metric.id}>
                      <div className="panel__meta">
                        <span>{variantLabel}</span>
                        <span className="panel__muted">
                          {metric.created_at
                            ? new Date(metric.created_at).toLocaleDateString()
                            : ""}
                        </span>
                      </div>
                      <span className="panel__muted">
                        Win rate: {values.win_rate ?? "—"} · Avg score:{" "}
                        {values.avg_score ?? "—"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="panel__meta">
              <h4 className="panel__subtitle">Orchestrator Recommendations</h4>
            </div>
            {recommendations.length === 0 ? (
              <p className="panel__empty">No recommendations yet.</p>
            ) : (
              <ul className="panel__list panel__list--compact">
                {recommendations.map((rec) => (
                  <li key={rec.id}>
                    <div className="panel__meta">
                      <span>{rec.recommendation.reason}</span>
                      <span className="panel__badge panel__badge--secondary">
                        {rec.recommendation.action}
                      </span>
                    </div>
                    <span className="panel__muted">
                      {rec.created_at
                        ? new Date(rec.created_at).toLocaleDateString()
                        : ""}
                    </span>
                    {rec.recommendation.action === "run_variant" ? (
                      <div className="panel__actions">
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={() =>
                            handleRunRecommendation(rec.recommendation.variant_id)
                          }
                          disabled={runningVariantId === rec.recommendation.variant_id}
                        >
                          {runningVariantId === rec.recommendation.variant_id
                            ? "Running…"
                            : "Run next test"}
                        </button>
                      </div>
                    ) : rec.recommendation.action === "create_variant" ? (
                      <div className="panel__actions">
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={() =>
                            handleCreateVariantFromRecommendation(
                              rec.recommendation,
                            )
                          }
                          disabled={isSubmitting}
                        >
                          {isSubmitting ? (
                            <>
                              Creating variant<span className="button__dots" />
                            </>
                          ) : (
                            "Create + run variant"
                          )}
                        </button>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="detail__note">
            Runs execute the full query battery against the selected variant and
            aggregate win-rate + score metrics.
          </div>
          </div>
        </div>
      </main>
    </div>
  );
}
