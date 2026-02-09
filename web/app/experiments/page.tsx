"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  AdminProduct,
  BrandBelief,
  CopyRevision,
  Experiment,
  ExperimentMetric,
  ExperimentRecommendation,
  ExperimentRun,
  LoopGeneratedVariantCandidate,
  ExperimentVariant,
  NextTestRecommendation,
  ValidationSummary,
  QueryBattery,
  QueryBatteryQuery,
  QueryBatteryCandidate,
  AudienceSegment,
  QueryBatteryMetrics,
  SessionSummary,
  SimulationGapReport,
  SimulationRunDetailResponse,
  SimulationRunSummary,
} from "../../lib/types";
import {
  createBattery,
  createExperiment,
  createExperimentVariant,
  generateExperimentVariants,
  deleteBatteryQuery,
  deleteConversationSession,
  deleteExperiment,
  deleteExperimentRun,
  deleteSimulationRun,
  generateBatteryQueries,
  addBatteryQuery,
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
  listBatteryAudienceSegments,
  updateBatteryAudienceSegment,
  runExperiment,
  updateExperiment,
  updateExperimentSchedule,
  backfillExperiment,
  getNextTestRecommendation,
  listExperimentRecommendations,
  getLatestBrandBelief,
  listBrandBeliefs,
  getSimulationRun,
  getExperimentValidationSummary,
  listAdminProducts,
  listSimulationRuns,
  listCopyRevisions,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";
import { BrandBeliefs } from "../../components/beliefs/BrandBeliefs";
import { MLPrediction } from "../../components/experiments/MLPrediction";
import { ThompsonSamplingGauge } from "../../components/experiments/ThompsonSamplingGauge";
import { buildTenantStorageKey } from "../../lib/storage";

export default function ExperimentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { productId, productName, brandId, clientId } = useTenant();
  const storageClientId =
    clientId ??
    (typeof window !== "undefined"
      ? window.localStorage.getItem("client_id")
      : null) ??
    undefined;
  const experimentsDraftStorageKey = useMemo(
    () => buildTenantStorageKey("experiments_draft", userId, storageClientId),
    [storageClientId, userId],
  );

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
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
  const [experimentSnapshots, setExperimentSnapshots] = useState<
    Record<
      string,
      { winnerLabel?: string; winRate?: number | null; measuredAt?: string | null }
    >
  >({});
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
  const [batteryMetrics, setBatteryMetrics] = useState<QueryBatteryMetrics | null>(null);
  const [audienceSegments, setAudienceSegments] = useState<AudienceSegment[]>([]);
  const [audienceSegmentsStatus, setAudienceSegmentsStatus] = useState<string | null>(null);
  const [audienceSegmentsOpen, setAudienceSegmentsOpen] = useState(false);
  const [batterySeedQueries, setBatterySeedQueries] = useState("");
  const [batteryUseLlm, setBatteryUseLlm] = useState(false);
  const [batterySeedFeatures, setBatterySeedFeatures] = useState("");
  const [batterySeedUseCases, setBatterySeedUseCases] = useState("");
  const [advancedOverridesOpen, setAdvancedOverridesOpen] = useState(false);
  const [batteryDetailsOpen, setBatteryDetailsOpen] = useState(true);
  const [setupFlowCollapsed, setSetupFlowCollapsed] = useState(true);
  const [historyCollapsed, setHistoryCollapsed] = useState(true);
  const [setupSecondaryActionsOpen, setSetupSecondaryActionsOpen] = useState(false);
  const [variantSecondaryActionsOpen, setVariantSecondaryActionsOpen] = useState(false);
  const [recommendationsOpen, setRecommendationsOpen] = useState(false);
  const [labShowManualControls, setLabShowManualControls] = useState(false);
  const [labAutoRunEnabled, setLabAutoRunEnabled] = useState(true);
  const [generatedCandidates, setGeneratedCandidates] = useState<
    (QueryBatteryCandidate & { selected: boolean })[]
  >([]);
  const [productDetail, setProductDetail] = useState<AdminProduct | null>(null);
  const [experimentForm, setExperimentForm] = useState({
    name: "",
    batteryId: "",
    hypothesis: "",
    competitorPolicy: "",
  });
  const [variantForm, setVariantForm] = useState({
    label: "Hypothesis (variant)",
    role: "candidate",
    description: "",
    type: "copy",
    payload: "",
  });
  const [simulationRevisions, setSimulationRevisions] = useState<CopyRevision[]>([]);
  const [selectedSimulationRevisionId, setSelectedSimulationRevisionId] = useState("");
  const [simulationRevisionStatus, setSimulationRevisionStatus] = useState<string | null>(
    null,
  );
  const [loopGeneratedVariants, setLoopGeneratedVariants] = useState<
    LoopGeneratedVariantCandidate[]
  >([]);
  const [selectedLoopCandidateIndex, setSelectedLoopCandidateIndex] = useState(0);
  const [loopGenerationStatus, setLoopGenerationStatus] = useState<string | null>(null);
  const [isGeneratingLoopVariant, setIsGeneratingLoopVariant] = useState(false);
  const [variantGenerationRequestType, setVariantGenerationRequestType] = useState<
    "loop" | "cold_start" | null
  >(null);
  const [variantSourceMode, setVariantSourceMode] = useState<
    "manual" | "simulation" | "loop_evidence" | "cold_start"
  >("manual");
  const [variantSourceManualOverride, setVariantSourceManualOverride] = useState(false);
  const [coldStartGenerationStrategy, setColdStartGenerationStrategy] = useState<
    "bottom_up" | "top_down" | "both"
  >("both");
  const [expandedVariantId, setExpandedVariantId] = useState<string | null>(null);
  const [variantAdvancedOpen, setVariantAdvancedOpen] = useState(false);
  const [isSubmitting, setSubmitting] = useState(false);
  const [savingExperimentId, setSavingExperimentId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [batteryStatus, setBatteryStatus] = useState<string | null>(null);
  const [batteryGenerationReport, setBatteryGenerationReport] = useState<{
    accepted_count: number;
    rejected_count: number;
    generated_count?: number;
    generated_preview?: { query_text: string; query_type?: string | null }[];
    required_category?: string | null;
    category_confidence?: number | null;
    category_candidates?: { category: string; score: number }[];
    clarification_required?: boolean;
    clarification_prompt?: string | null;
    regeneration_count?: number;
    acceptance_rate?: number;
    rejected?: { query_text: string; reason: string }[];
    audience_segments_generated?: number;
    audience_segment_labels?: string[];
    audience_segments_source?: "behavioral" | "canonical_fallback";
    audience_segments_fallback_reason?: string | null;
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
  const [metricsHistoryExpanded, setMetricsHistoryExpanded] = useState(false);
  const [nextTest, setNextTest] = useState<NextTestRecommendation | null>(null);
  const [nextTestStatus, setNextTestStatus] = useState<string | null>(null);
  const [isRecommending, setIsRecommending] = useState(false);
  const [validationSummary, setValidationSummary] = useState<ValidationSummary | null>(
    null,
  );
  const [jsonErrors, setJsonErrors] = useState({
    hypothesis: null as string | null,
    competitorPolicy: null as string | null,
    variantPayload: null as string | null,
  });
  const [restoreDraft, setRestoreDraft] = useState<{
    labMode?: "lab" | "manual";
    selectedExperimentId?: string | null;
    experimentForm?: typeof experimentForm;
    variantForm?: typeof variantForm;
    variantAdvancedOpen?: boolean;
    batteryForm?: typeof batteryForm;
    batteryEdit?: typeof batteryEdit;
    batterySeedQueries?: string;
    batterySeedFeatures?: string;
    batterySeedUseCases?: string;
    batteryUseLlm?: boolean;
    advancedOverridesOpen?: boolean;
  } | null>(null);
  const [showRestorePrompt, setShowRestorePrompt] = useState(false);
  const autosaveEnabled = useRef(false);
  const variantsSectionRef = useRef<HTMLElement | null>(null);
  const runsSectionRef = useRef<HTMLDivElement | null>(null);
  const metricsSectionRef = useRef<HTMLElement | null>(null);

  const showManualControls = labMode === "manual" || labShowManualControls;

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
  }, [userId, clientId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved =
      window.localStorage.getItem(experimentsDraftStorageKey) ??
      window.localStorage.getItem("experiments_draft");
    if (!saved) {
      autosaveEnabled.current = true;
      return;
    }
    try {
      const parsed = JSON.parse(saved);
      setRestoreDraft(parsed);
      setShowRestorePrompt(true);
    } catch {
      window.localStorage.removeItem(experimentsDraftStorageKey);
      window.localStorage.removeItem("experiments_draft");
      autosaveEnabled.current = true;
    }
  }, [experimentsDraftStorageKey]);

  const handleRestoreDraft = useCallback(() => {
    if (!restoreDraft) return;
    setLabMode(restoreDraft.labMode ?? "lab");
    setSelectedExperimentId(restoreDraft.selectedExperimentId ?? null);
    setExperimentForm((prev) => ({
      ...prev,
      ...(restoreDraft.experimentForm ?? {}),
    }));
    setVariantForm((prev) => ({
      ...prev,
      ...(restoreDraft.variantForm ?? {}),
    }));
    setVariantAdvancedOpen(Boolean(restoreDraft.variantAdvancedOpen));
    setBatteryForm((prev) => ({
      ...prev,
      ...(restoreDraft.batteryForm ?? {}),
    }));
    setBatteryEdit((prev) => ({
      ...prev,
      ...(restoreDraft.batteryEdit ?? {}),
    }));
    setBatterySeedQueries(restoreDraft.batterySeedQueries ?? "");
    setBatterySeedFeatures(restoreDraft.batterySeedFeatures ?? "");
    setBatterySeedUseCases(restoreDraft.batterySeedUseCases ?? "");
    setBatteryUseLlm(Boolean(restoreDraft.batteryUseLlm));
    setAdvancedOverridesOpen(Boolean(restoreDraft.advancedOverridesOpen));
    setShowRestorePrompt(false);
    autosaveEnabled.current = true;
  }, [restoreDraft]);

  const handleDismissDraft = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(experimentsDraftStorageKey);
      window.localStorage.removeItem("experiments_draft");
    }
    setRestoreDraft(null);
    setShowRestorePrompt(false);
    autosaveEnabled.current = true;
  }, [experimentsDraftStorageKey]);

  useEffect(() => {
    void listBatteries(userId, productId ?? undefined).then((response) => {
      setBatteries(response.batteries ?? []);
    });
    void listExperiments(userId, productId ?? undefined).then((response) => {
      const items = response.experiments ?? [];
      setExperiments(items);
    });
  }, [productId, selectedExperimentId, userId]);

  useEffect(() => {
    if (!userId || experiments.length === 0) {
      setExperimentSnapshots({});
      return;
    }
    let active = true;
    void (async () => {
      const entries = await Promise.all(
        experiments.map(async (experiment) => {
          try {
            const [metricsResponse, variantsResponse] = await Promise.all([
              listExperimentMetrics(experiment.id, userId),
              listExperimentVariants(experiment.id, userId),
            ]);
            const metricsList = metricsResponse.metrics ?? [];
            const variantsList = variantsResponse.variants ?? [];
            const variantLabelById = new Map(
              variantsList.map((variant) => [variant.id, variant.label]),
            );
            let bestVariantId: string | null = null;
            let bestWinRate = -1;
            let measuredAt: string | null = null;
            metricsList.forEach((metric) => {
              const rawWinRate = Number((metric.metrics ?? {}).win_rate);
              if (!Number.isFinite(rawWinRate)) return;
              if (rawWinRate > bestWinRate) {
                bestWinRate = rawWinRate;
                bestVariantId = metric.variant_id ?? null;
                measuredAt = metric.created_at ?? null;
              } else if (
                rawWinRate === bestWinRate &&
                (metric.created_at ?? "") > (measuredAt ?? "")
              ) {
                bestVariantId = metric.variant_id ?? null;
                measuredAt = metric.created_at ?? null;
              }
            });
            return [
              experiment.id,
              {
                winnerLabel: bestVariantId
                  ? variantLabelById.get(bestVariantId) ?? bestVariantId
                  : undefined,
                winRate: bestWinRate >= 0 ? bestWinRate : null,
                measuredAt,
              },
            ] as const;
          } catch {
            return [experiment.id, {}] as const;
          }
        }),
      );
      if (!active) return;
      setExperimentSnapshots(Object.fromEntries(entries));
    })();
    return () => {
      active = false;
    };
  }, [experiments, userId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!autosaveEnabled.current) return;
    const payload = {
      labMode,
      selectedExperimentId,
      experimentForm,
      variantForm,
      variantAdvancedOpen,
      batteryForm,
      batteryEdit,
      batterySeedQueries,
      batterySeedFeatures,
      batterySeedUseCases,
      batteryUseLlm,
      advancedOverridesOpen,
    };
    window.localStorage.setItem(experimentsDraftStorageKey, JSON.stringify(payload));
  }, [
    experimentsDraftStorageKey,
    labMode,
    selectedExperimentId,
    experimentForm,
    variantForm,
    variantAdvancedOpen,
    batteryForm,
    batteryEdit,
    batterySeedQueries,
    batterySeedFeatures,
    batterySeedUseCases,
    batteryUseLlm,
    advancedOverridesOpen,
  ]);

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
      setLoopGeneratedVariants([]);
      setSelectedLoopCandidateIndex(0);
      setLoopGenerationStatus(null);
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
    if (!brandId) {
      setBeliefCount(0);
      setLatestBelief(null);
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
  }, [brandId, userId]);

  useEffect(() => {
    if (!productId) {
      setSimulationRevisions([]);
      setSelectedSimulationRevisionId("");
      return;
    }
    let cancelled = false;
    void listCopyRevisions({
      product_id: productId,
      source_type: "simulation",
      user_id: userId,
      limit: 50,
    })
      .then((response) => {
        if (cancelled) return;
        const revisions = response.revisions ?? [];
        setSimulationRevisions(revisions);
        setSelectedSimulationRevisionId((current) => {
          if (current && revisions.some((item) => item.id === current)) return current;
          return revisions[0]?.id ?? "";
        });
      })
      .catch(() => {
        if (cancelled) return;
        setSimulationRevisions([]);
        setSelectedSimulationRevisionId("");
      });
    return () => {
      cancelled = true;
    };
  }, [productId, userId]);

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
    let cancelled = false;
    if (!selectedBattery) {
      setAudienceSegments([]);
      setAudienceSegmentsStatus(null);
      return;
    }
    void listBatteryAudienceSegments(selectedBattery.id, userId)
      .then((response) => {
        if (cancelled) return;
        setAudienceSegments(response.segments ?? []);
      })
      .catch(() => {
        if (cancelled) return;
        setAudienceSegments([]);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedBattery, userId]);

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

  useEffect(() => {
    if (!selectedExperiment) return;
    const hypothesisText = selectedExperiment.hypothesis
      ? JSON.stringify(selectedExperiment.hypothesis, null, 2)
      : "";
    const competitorPolicyText = selectedExperiment.competitor_policy
      ? JSON.stringify(selectedExperiment.competitor_policy, null, 2)
      : "";
    setExperimentForm((prev) => ({
      ...prev,
      name: selectedExperiment.name ?? prev.name,
      batteryId: selectedExperiment.battery_id ?? prev.batteryId,
      hypothesis: hypothesisText || prev.hypothesis,
      competitorPolicy: competitorPolicyText || prev.competitorPolicy,
    }));
  }, [selectedExperiment]);

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

  const handleDeleteSimulationRun = useCallback(
    async (runId: string) => {
      if (!userId) return;
      try {
        await deleteSimulationRun(runId, userId, clientId ?? undefined);
        setSimulationRuns((current) => current.filter((run) => run.id !== runId));
      } catch {
        // ignore delete errors
      }
    },
    [clientId, userId],
  );

  const handleDeleteExperiment = useCallback(
    async (experimentId: string) => {
      if (!userId) return;
      try {
        await deleteExperiment(experimentId, userId, clientId ?? undefined);
        setExperiments((current) =>
          current.filter((experiment) => experiment.id !== experimentId),
        );
        setSelectedExperimentId((current) =>
          current === experimentId ? null : current,
        );
      } catch {
        // ignore delete errors
      }
    },
    [clientId, userId],
  );

  const handleDeleteExperimentRun = useCallback(
    async (runId: string) => {
      if (!userId || !selectedExperimentId) return;
      try {
        await deleteExperimentRun(selectedExperimentId, runId, userId);
        setRuns((current) => current.filter((run) => run.id !== runId));
      } catch {
        // ignore delete errors
      }
    },
    [selectedExperimentId, userId],
  );

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await deleteConversationSession(deleteTargetId, userId);
      setSessions((current) => current.filter((item) => item.id !== deleteTargetId));
    } finally {
      setDeleteTargetId(null);
    }
  }, [deleteTargetId, userId]);

  const handleBulkDeleteSessions = useCallback(
    async (sessionIds: string[]) => {
      if (!sessionIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${sessionIds.length} chat session${sessionIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        sessionIds.map((id) =>
          deleteConversationSession(id, userId).catch(() => null),
        ),
      );
      setSessions((current) => current.filter((item) => !sessionIds.includes(item.id)));
      setDeleteTargetId(null);
    },
    [userId],
  );

  const handleBulkDeleteSimulations = useCallback(
    async (runIds: string[]) => {
      if (!runIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${runIds.length} simulation run${runIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        runIds.map((id) =>
          deleteSimulationRun(id, userId, clientId ?? undefined).catch(() => null),
        ),
      );
      setSimulationRuns((current) => current.filter((run) => !runIds.includes(run.id)));
    },
    [clientId, userId],
  );

  const handleBulkDeleteExperiments = useCallback(
    async (experimentIds: string[]) => {
      if (!experimentIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${experimentIds.length} experiment${experimentIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        experimentIds.map((id) =>
          deleteExperiment(id, userId, clientId ?? undefined).catch(() => null),
        ),
      );
      setExperiments((current) =>
        current.filter((experiment) => !experimentIds.includes(experiment.id)),
      );
      setSelectedExperimentId((current) =>
        current && experimentIds.includes(current) ? null : current,
      );
    },
    [clientId, userId],
  );

  const handleRunVariant = useCallback(
    async (variantId: string) => {
      if (!selectedExperimentId) return;
      if (labMode === "lab" && labAutoRunEnabled) {
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
    const canonicalSpec =
      (metadata.canonical_intent_spec as Record<string, unknown> | undefined) ?? {};
    const features = metadata.features;
    const useCase = metadata.use_case ?? metadata.scenario;
    const hasFeatures =
      (Array.isArray(features) && features.length > 0) ||
      (typeof features === "string" && features.trim() !== "");
    const hasUseCase =
      (Array.isArray(useCase) && useCase.length > 0) ||
      (typeof useCase === "string" && useCase.trim() !== "");
    const canonicalFeatures = canonicalSpec.feature_concepts;
    const canonicalUseCases = canonicalSpec.use_cases;
    const hasCanonicalFeatures =
      (Array.isArray(canonicalFeatures) && canonicalFeatures.length > 0) ||
      (typeof canonicalFeatures === "string" && canonicalFeatures.trim() !== "");
    const hasCanonicalUseCases =
      (Array.isArray(canonicalUseCases) && canonicalUseCases.length > 0) ||
      (typeof canonicalUseCases === "string" && canonicalUseCases.trim() !== "");
    const hasIntentLabels = Boolean(metadata.intent_labels || metadata.intent_archetypes);
    const hasVertical = Boolean(
      metadata.vertical ||
        metadata.domain ||
        metadata.category ||
        canonicalSpec.category,
    );
    return (
      hasFeatures ||
      hasUseCase ||
      hasCanonicalFeatures ||
      hasCanonicalUseCases ||
      hasIntentLabels ||
      hasVertical
    );
  }, [productDetail]);

  useEffect(() => {
    if (batteryForm.generationMode === "bottom_up" && !hasBottomUpMetadata) {
      setAdvancedOverridesOpen(true);
    }
  }, [batteryForm.generationMode, hasBottomUpMetadata]);

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
    [generatedCandidates, userId],
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
    [selectedBattery, userId],
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
      if (labMode === "lab" && labAutoRunEnabled) {
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
      } else if (labMode === "lab") {
        setExperimentStatus(
          "Lab mode: experiment created. Auto-run is off, so run variants when ready.",
        );
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
    labAutoRunEnabled,
    hasBottomUpMetadata,
    parseSeedList,
    productId,
    productName,
    userId,
  ]);

  const handleCreateVariant = useCallback(async () => {
    if (!selectedExperimentId) return;
    if (jsonErrors.variantPayload) return;
    setFormError(null);
    setSubmitting(true);
    try {
      const basePayload =
        variantForm.payload.trim() !== ""
          ? JSON.parse(variantForm.payload)
          : {};
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
          : "Hypothesis (variant)";
      await createExperimentVariant(selectedExperimentId, {
        label: normalizedLabel,
        type: variantForm.type.trim() || "copy",
        payload,
        user_id: userId,
      });
      const refreshed = await listExperimentVariants(selectedExperimentId, userId);
      setVariants(refreshed.variants ?? []);
      setVariantForm({
        label: "Hypothesis (variant)",
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
      setSubmitting(false);
    }
  }, [jsonErrors.variantPayload, selectedExperimentId, userId, variantForm]);

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
          // Keep existing payload string untouched if invalid JSON; validation already surfaces this.
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
  }, [selectedSimulationRevisionId, simulationRevisions]);

  const handleGenerateLoopVariants = useCallback(async () => {
    if (!selectedExperimentId) {
      setLoopGenerationStatus("Select an experiment first.");
      return;
    }
    setLoopGenerationStatus(null);
    setVariantGenerationRequestType("loop");
    setIsGeneratingLoopVariant(true);
    try {
      const response = await generateExperimentVariants(selectedExperimentId, {
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
  }, [selectedExperimentId, userId]);

  const handleGenerateColdStartVariants = useCallback(async () => {
    if (!selectedExperimentId) {
      setLoopGenerationStatus("Select an experiment first.");
      return;
    }
    setLoopGenerationStatus(null);
    setVariantGenerationRequestType("cold_start");
    setIsGeneratingLoopVariant(true);
    try {
      const response = await generateExperimentVariants(selectedExperimentId, {
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
  }, [coldStartGenerationStrategy, selectedExperimentId, userId]);

  const buildLoopCandidatePayload = useCallback(
    (
      candidate: LoopGeneratedVariantCandidate,
      basePayload: Record<string, unknown> = {},
    ) => {
      const candidatePayload =
        candidate.payload && typeof candidate.payload === "object"
          ? candidate.payload
          : {};
      return {
        ...basePayload,
        ...candidatePayload,
        source_type: "loop_evidence",
        loop_confidence: candidate.confidence,
      };
    },
    [],
  );

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
    buildLoopCandidatePayload,
    loopGeneratedVariants,
    selectedLoopCandidateIndex,
  ]);

  const handleCreateVariantFromLoopCandidate = useCallback(async () => {
    if (!selectedExperimentId) {
      setLoopGenerationStatus("Select an experiment first.");
      return;
    }
    const candidate = loopGeneratedVariants[selectedLoopCandidateIndex];
    if (!candidate) {
      setLoopGenerationStatus("Generate and select a loop candidate first.");
      return;
    }

    setFormError(null);
    setLoopGenerationStatus(null);
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = buildLoopCandidatePayload(candidate, {
        role: "candidate",
      });
      const description = String(candidate.description || "").trim();
      if (description) {
        payload.description = description;
      }
      await createExperimentVariant(selectedExperimentId, {
        label: candidate.label?.trim() || "Hypothesis (variant)",
        type: "copy",
        payload,
        user_id: userId,
      });
      const refreshed = await listExperimentVariants(selectedExperimentId, userId);
      setVariants(refreshed.variants ?? []);
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
      setSubmitting(false);
    }
  }, [
    buildLoopCandidatePayload,
    loopGeneratedVariants,
    selectedExperimentId,
    selectedLoopCandidateIndex,
    userId,
  ]);

  const handleCreateAndRunVariantFromLoopCandidate = useCallback(async () => {
    if (!selectedExperimentId) {
      setLoopGenerationStatus("Select an experiment first.");
      return;
    }
    const candidate = loopGeneratedVariants[selectedLoopCandidateIndex];
    if (!candidate) {
      setLoopGenerationStatus("Generate and select a loop candidate first.");
      return;
    }

    setFormError(null);
    setLoopGenerationStatus(null);
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = buildLoopCandidatePayload(candidate, {
        role: "candidate",
      });
      const description = String(candidate.description || "").trim();
      if (description) {
        payload.description = description;
      }
      const created = await createExperimentVariant(selectedExperimentId, {
        label: candidate.label?.trim() || "Hypothesis (variant)",
        type: "copy",
        payload,
        user_id: userId,
      });
      await runExperiment(selectedExperimentId, created.variant.id, userId);
      const [variantsResponse, runsResponse, metricsResponse] = await Promise.all([
        listExperimentVariants(selectedExperimentId, userId),
        listExperimentRuns(selectedExperimentId, userId),
        listExperimentMetrics(selectedExperimentId, userId),
      ]);
      setVariants(variantsResponse.variants ?? []);
      setRuns(runsResponse.runs ?? []);
      setMetrics(metricsResponse.metrics ?? []);
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
      setSubmitting(false);
    }
  }, [
    buildLoopCandidatePayload,
    loopGeneratedVariants,
    selectedExperimentId,
    selectedLoopCandidateIndex,
    userId,
  ]);

  const handleSaveExperimentDraft = useCallback(
    async (experimentId: string) => {
      setFormError(null);
      setSavingExperimentId(experimentId);
      try {
        await updateExperiment(experimentId, {
          status: "active",
          user_id: userId,
        });
        const refreshed = await listExperiments(userId, productId ?? undefined);
        setExperiments(refreshed.experiments ?? []);
        setExperimentStatus("Experiment saved as active.");
      } catch (error) {
        setFormError(
          error instanceof Error ? error.message : "Unable to save experiment draft.",
        );
      } finally {
        setSavingExperimentId(null);
      }
    },
    [productId, userId],
  );

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

  const latestMetricEntry = metrics[0] ?? null;
  const latestMetric =
    (latestMetricEntry?.metrics as Record<string, unknown> | undefined) ?? null;
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
  const beliefsRef = useRef<HTMLDivElement | null>(null);

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

  const hasValidationSignals =
    (validationSummary?.total_logged ?? 0) > 0 ||
    (validationSummary?.verified_runs ?? 0) > 0;

  const outcomeSnapshot = useMemo(() => {
    const latestRunEntry = runs
      .slice()
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
    const latestMetricEntry = metrics
      .slice()
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
    const metricValues = (latestMetricEntry?.metrics ?? {}) as Record<string, unknown>;
    const runVariantLabel = latestRunEntry?.variant_id
      ? variants.find((variant) => variant.id === latestRunEntry.variant_id)?.label ??
        latestRunEntry.variant_id
      : "No runs yet";
    const runQueryLabel = latestRunEntry?.query_id
      ? queryMap.get(latestRunEntry.query_id) ?? latestRunEntry.query_id
      : "—";
    const winRate =
      typeof metricValues.win_rate === "number"
        ? `${Math.round(metricValues.win_rate * 100)}%`
        : "—";
    const avgScore =
      typeof metricValues.avg_score === "number"
        ? metricValues.avg_score.toFixed(3)
        : "—";
    const validationState = hasValidationSignals
      ? `Started · ${validationSummary?.verified_runs ?? 0} verified`
      : "Pending";
    return {
      runVariantLabel,
      runQueryLabel,
      runCreatedAt: latestRunEntry?.created_at ?? null,
      winRate,
      avgScore,
      validationState,
    };
  }, [hasValidationSignals, metrics, queryMap, runs, validationSummary?.verified_runs, variants]);

  const experimentFlowSteps = useMemo(() => {
    const batteryBuilt = Boolean(selectedExperiment?.battery_id || experimentForm.batteryId);
    const queriesReady = queries.length > 0;
    const experimentCreated = Boolean(selectedExperimentId);
    const variantsReady = variants.length > 0;
    const hasRuns = runs.length > 0 || Boolean(selectedExperiment?.last_run_at);
    const outcomesReviewed = metrics.length > 0;
    const validated = hasValidationSignals;
    const nextVariantsReady =
      loopGeneratedVariants.length > 0 ||
      Boolean(nextTest) ||
      recommendations.length > 0;
    return [
      { id: 1, label: "Build query battery", done: batteryBuilt },
      { id: 2, label: "Generate and review queries", done: queriesReady },
      { id: 3, label: "Create experiment", done: experimentCreated },
      { id: 4, label: "Create variants", done: variantsReady },
      { id: 5, label: "Run experiment", done: hasRuns },
      { id: 6, label: "Review outcomes and metrics", done: outcomesReviewed },
      { id: 7, label: "Validate synthetic and observed", done: validated },
      { id: 8, label: "Generate next variants", done: nextVariantsReady },
    ];
  }, [
    experimentForm.batteryId,
    hasValidationSignals,
    loopGeneratedVariants.length,
    metrics.length,
    nextTest,
    queries.length,
    recommendations.length,
    runs.length,
    selectedExperiment?.battery_id,
    selectedExperiment?.last_run_at,
    selectedExperimentId,
    variants.length,
  ]);

  const labFlowSteps = useMemo(() => {
    const batteryBuilt = Boolean(selectedExperiment?.battery_id || experimentForm.batteryId);
    const queriesReady = queries.length > 0;
    const experimentCreated = Boolean(selectedExperimentId);
    const variantsReady = variants.length >= 2;
    const hasRuns = runs.length > 0 || Boolean(selectedExperiment?.last_run_at);
    const outcomesReviewed = metrics.length > 0;
    const validated = hasValidationSignals;
    const nextVariantsReady =
      loopGeneratedVariants.length > 0 ||
      Boolean(nextTest) ||
      recommendations.length > 0;
    return [
      { id: 1, label: "Build query battery", done: batteryBuilt },
      { id: 2, label: "Generate and review queries", done: queriesReady },
      { id: 3, label: "Create experiment", done: experimentCreated },
      { id: 4, label: "Create baseline + hypothesis variants", done: variantsReady },
      { id: 5, label: "Run baseline + hypothesis", done: hasRuns },
      { id: 6, label: "Review outcomes and metrics", done: outcomesReviewed },
      { id: 7, label: "Validation checkpoint", done: validated },
      { id: 8, label: "Generate next variants", done: nextVariantsReady },
    ];
  }, [
    experimentForm.batteryId,
    hasValidationSignals,
    loopGeneratedVariants.length,
    metrics.length,
    nextTest,
    queries.length,
    recommendations.length,
    runs.length,
    selectedExperiment?.battery_id,
    selectedExperiment?.last_run_at,
    selectedExperimentId,
    variants.length,
  ]);

  const activeFlowSteps = labMode === "lab" ? labFlowSteps : experimentFlowSteps;

  const currentFlowStep = useMemo(
    () => activeFlowSteps.find((step) => !step.done)?.id ?? 8,
    [activeFlowSteps],
  );

  const queryGenerationDisabledReason = !experimentForm.batteryId
    ? "Select a battery first."
    : isSubmitting
      ? "Please wait for the current action to finish."
      : null;
  const createExperimentDisabledReason = isSubmitting
    ? "Please wait for the current action to finish."
    : experimentForm.name.trim() === ""
      ? "Enter an experiment name."
      : jsonErrors.hypothesis
        ? "Fix invalid Hypothesis JSON."
        : jsonErrors.competitorPolicy
          ? "Fix invalid Competitor policy JSON."
          : null;
  const addVariantDisabledReason = isSubmitting
    ? "Please wait for the current action to finish."
    : !selectedExperimentId
      ? "Create or select an experiment first."
      : jsonErrors.variantPayload
        ? "Fix invalid payload JSON."
        : null;
  const canRunVariantTests = Boolean(
    selectedExperimentId && (selectedExperiment?.battery_id || experimentForm.batteryId),
  ) && queries.length > 0;
  const runVariantDisabledReason = !selectedExperimentId
    ? "Create or select an experiment first."
    : !(selectedExperiment?.battery_id || experimentForm.batteryId)
      ? "Link a battery to this experiment first."
      : queries.length === 0
        ? "Generate and save at least one enabled query first."
        : null;
  const loopEvidenceAdvisory =
    runs.length === 0 && variantSourceMode === "loop_evidence"
      ? "Loop evidence works best after at least one run. Use cold-start to bootstrap."
      : !hasValidationSignals && variantSourceMode === "loop_evidence"
        ? "Add validation signals to improve loop-evidence reliability."
        : null;

  const recommendedVariantSource = useMemo<
    "manual" | "simulation" | "loop_evidence" | "cold_start"
  >(() => {
    if (runs.length === 0) return "cold_start";
    if (!hasValidationSignals) {
      return simulationRevisions.length > 0 ? "simulation" : "cold_start";
    }
    return "loop_evidence";
  }, [hasValidationSignals, runs.length, simulationRevisions.length]);

  const recommendedVariantSourceReason = useMemo(() => {
    if (runs.length === 0) {
      return "No run history yet, so cold-start is the fastest bootstrap path.";
    }
    if (!hasValidationSignals && simulationRevisions.length > 0) {
      return "Runs exist but validation is still pending; simulation prefill gives a stable interim source.";
    }
    if (!hasValidationSignals) {
      return "Runs exist but validation is still pending; use cold-start until stronger loop evidence is available.";
    }
    return "Validation signals are available; loop evidence is now the highest-confidence source.";
  }, [hasValidationSignals, runs.length, simulationRevisions.length]);

  useEffect(() => {
    setVariantSourceManualOverride(false);
  }, [selectedExperimentId]);

  useEffect(() => {
    if (currentFlowStep !== 4) return;
    if (variantSourceManualOverride) return;
    if (variantSourceMode === recommendedVariantSource) return;
    setVariantSourceMode(recommendedVariantSource);
  }, [
    currentFlowStep,
    recommendedVariantSource,
    variantSourceManualOverride,
    variantSourceMode,
  ]);

  const nextFlowAction = useMemo(() => {
    if (!selectedExperimentId && setupFlowCollapsed) {
      return {
        label: "Expand setup and start Step 1",
        helper: "Start by creating a battery and generating queries.",
        action: "expand_setup" as const,
      };
    }
    if (!selectedExperimentId) {
      return {
        label: "Create experiment (Step 3)",
        helper: "Complete battery/query setup, then create the experiment.",
        action: "scroll_setup" as const,
      };
    }
    if (variants.length === 0) {
      return {
        label: "Create first variant (Step 4)",
        helper: "Use manual, simulation, loop, or cold-start source.",
        action: "scroll_variants" as const,
      };
    }
    if (runs.length === 0) {
      return {
        label: "Run first variant test (Step 5)",
        helper: "Run a variant across the linked battery queries.",
        action: "run_first_variant" as const,
      };
    }
    if (!hasValidationSignals) {
      return {
        label: "Validate in Validation module (Step 7)",
        helper: "Add synthetic and/or observed validation before final decisions.",
        action: "open_validation" as const,
      };
    }
    return {
      label: "Generate next variants (Step 8)",
      helper: "Use loop evidence to iterate on the next candidate copy.",
      action: "generate_next_variant" as const,
    };
  }, [hasValidationSignals, runs.length, selectedExperimentId, setupFlowCollapsed, variants]);

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

  const handleRunNextFlowAction = useCallback(() => {
    switch (nextFlowAction.action) {
      case "expand_setup":
        setSetupFlowCollapsed(false);
        return;
      case "scroll_setup":
        setSetupFlowCollapsed(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      case "scroll_variants":
        variantsSectionRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        return;
      case "run_first_variant":
        if (variants[0]?.id) {
          void handleRunVariant(variants[0].id);
          return;
        }
        variantsSectionRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        return;
      case "open_validation":
        if (selectedExperimentId) {
          router.push(`/validation?experiment_id=${selectedExperimentId}`);
          return;
        }
        router.push("/validation");
        return;
      case "generate_next_variant":
        variantsSectionRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        void handleGenerateLoopVariants();
        return;
      default:
        return;
    }
  }, [
    handleGenerateLoopVariants,
    handleRunVariant,
    nextFlowAction.action,
    router,
    selectedExperimentId,
    variants,
  ]);

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
  const recentMetrics = useMemo(() => metricsHistory.slice(0, 5), [metricsHistory]);

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

  const formatTimestamp = useCallback((value?: string | null) => {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
  }, []);

  const renderMetricValue = useCallback((value: unknown, fallback = "—") => {
    if (value === null || value === undefined) return fallback;
    if (typeof value === "number") return Number.isFinite(value) ? String(value) : fallback;
    if (typeof value === "string") return value;
    if (typeof value === "boolean") return value ? "true" : "false";
    return fallback;
  }, []);

  const latestBeliefSummary = useMemo(() => {
    const summary = latestBelief?.metadata?.summary;
    if (typeof summary === "string" && summary.trim()) return summary;
    if (typeof latestBelief?.recommendation === "string" && latestBelief.recommendation.trim()) {
      return latestBelief.recommendation;
    }
    return "Beliefs appear after results are analyzed.";
  }, [latestBelief]);

  const resolveVariantDescription = useCallback(
    (variant: ExperimentVariant): string | null => {
      const payload = variant.payload ?? {};
      const direct = payload.description;
      if (typeof direct === "string" && direct.trim()) {
        return direct.trim();
      }
      const isControl =
        payload.role === "control" ||
        variant.label.toLowerCase().includes("control");
      if (isControl) {
        const fallback = productDetail?.description ?? productName ?? "";
        return fallback.trim() ? fallback.trim() : null;
      }
      return null;
    },
    [productDetail?.description, productName],
  );

  return (
    <div className="app experiments-page">
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
        isOpen={isHistoryOpen}
        isClosing={isHistoryClosing}
        sessions={sessions}
        simulations={simulationRuns}
        experiments={experiments}
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(session) => router.push(`/?session=${session.id}`)}
        onSelectSimulation={(run) => {
          router.push(`/simulation?run_id=${run.id}`);
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(`/experiments?experiment_id=${experiment.id}`);
          handleCloseHistory();
        }}
        onRequestDelete={(id) => setDeleteTargetId(id)}
        onRequestDeleteSimulation={handleDeleteSimulationRun}
        onRequestDeleteExperiment={handleDeleteExperiment}
        onRequestDeleteSessionsBulk={handleBulkDeleteSessions}
        onRequestDeleteSimulationsBulk={handleBulkDeleteSimulations}
        onRequestDeleteExperimentsBulk={handleBulkDeleteExperiments}
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
                  onClick={() => {
                    setLabMode("lab");
                    setLabShowManualControls(false);
                  }}
                  data-tooltip="Lab mode follows the automation-first path with optional auto-run."
                >
                  Lab mode
                </button>
                <button
                  type="button"
                  className={`summary-card__toggle-btn product__tooltip tooltip--below ${
                    labMode === "manual" ? "is-active" : ""
                  }`}
                  onClick={() => {
                    setLabMode("manual");
                    setLabShowManualControls(true);
                  }}
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
              signals from simulated judges. Use them to prioritize what to test
              next.
            </section>
            {showRestorePrompt ? (
              <section className="panel__notice panel__notice--info">
                <strong>Restore last session?</strong> Your last experiment draft
                is available.
                <div className="panel__actions">
                  <button
                    type="button"
                    className="panel__action"
                    onClick={handleRestoreDraft}
                  >
                    Restore
                  </button>
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={handleDismissDraft}
                  >
                    Dismiss
                  </button>
                </div>
              </section>
            ) : null}
            <section className="panel__card panel__card--primary lab-loop">
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
              </div>
            </div>
            <p className="lab-loop__meta">
              {variants.length} variants · {runs.length} runs · {metrics.length} metrics ·{" "}
              {beliefCount} beliefs
            </p>
            <p className="lab-loop__hint">
              The lab loop turns hypotheses into evidence and updates brand
              beliefs with every run.
            </p>
            {labMode === "lab" ? (
              <section className="panel__notice panel__notice--info lab-contract">
                <strong>Lab mode contract:</strong> Automation handles the default path
                (battery, queries, baseline/hypothesis variants, and optional auto-run).
                <div className="panel__actions">
                  <label className="panel__toggle">
                    <input
                      type="checkbox"
                      checked={labAutoRunEnabled}
                      onChange={(event) => setLabAutoRunEnabled(event.target.checked)}
                    />
                    <span>Auto-run baseline + hypothesis after experiment creation</span>
                  </label>
                  {!showManualControls ? (
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => setLabShowManualControls(true)}
                    >
                      Show manual controls
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => setLabShowManualControls(false)}
                    >
                      Hide manual controls
                    </button>
                  )}
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={() => {
                      setLabMode("manual");
                      setLabShowManualControls(true);
                      setExperimentStatus(
                        "Switched to Manual mode for explicit control over each step.",
                      );
                    }}
                  >
                    Switch to Manual for this experiment
                  </button>
                </div>
              </section>
            ) : null}
            <div className="flow-rail">
              <div className="flow-rail__header">
                <h4>{labMode === "lab" ? "Lab Flow" : "Experiment Flow"}</h4>
                <span className="panel__muted">Current step: {currentFlowStep} / 8</span>
              </div>
              <div className="flow-rail__steps">
                {activeFlowSteps.map((step) => (
                  <div
                    key={step.id}
                    className={`flow-rail__step ${
                      step.done ? "is-done" : step.id === currentFlowStep ? "is-current" : ""
                    }`}
                  >
                    <span className="flow-rail__index">{step.id}</span>
                    <span className="flow-rail__label">{step.label}</span>
                    <span className="flow-rail__status">
                      {step.done ? "Done" : step.id === currentFlowStep ? "Current" : "Pending"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
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
                  {latestBeliefSummary}
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
            <section className="panel__notice panel__notice--info flow-next-action">
              <strong>Next recommended action:</strong> {nextFlowAction.label}
              <p className="panel__muted">{nextFlowAction.helper}</p>
              <div className="panel__actions panel__actions--priority">
                <button
                  type="button"
                  className="panel__action panel__action--prominent"
                  onClick={handleRunNextFlowAction}
                >
                  {nextFlowAction.label}
                </button>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() =>
                    router.push(
                      selectedExperimentId
                        ? `/validation?experiment_id=${selectedExperimentId}`
                        : "/validation",
                    )
                  }
                >
                  Open Validation
                </button>
              </div>
            </section>
            {labMode === "lab" && runs.length > 0 && !hasValidationSignals ? (
              <section className="panel__notice panel__notice--warning lab-checkpoint">
                <strong>Validation checkpoint (Step 7):</strong> Runs exist, but no
                validation evidence is logged yet.
                <p className="panel__muted">
                  Complete synthetic and/or observed validation before trusting automated
                  iteration decisions.
                </p>
                <div className="panel__actions panel__actions--priority">
                  <button
                    type="button"
                    className="panel__action panel__action--prominent"
                    onClick={() =>
                      router.push(
                        selectedExperimentId
                          ? `/validation?experiment_id=${selectedExperimentId}`
                          : "/validation",
                      )
                    }
                  >
                    Go to Validation (Step 7)
                  </button>
                </div>
              </section>
            ) : null}
          </section>
          {formError ? (
            <div className="panel__notice panel__notice--error">{formError}</div>
          ) : null}
          <section className="panel__card panel__card--primary">
            <div className="panel__header">
              <h3>
                {labMode === "lab"
                  ? "Lab Setup Flow"
                  : "Experiment Setup Flow"}
              </h3>
              <div className="panel__meta">
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => setSetupFlowCollapsed((open) => !open)}
                >
                  {setupFlowCollapsed ? "Expand setup" : "Collapse setup"}
                </button>
              </div>
            </div>
            <p className="panel__subheading">Setup phase · Steps 1 to 3</p>
            <p className="panel__muted">
              {labMode === "lab"
                ? "Automation-first: create experiment and let Lab mode handle the default setup path."
                : "Build battery, generate queries, then create experiment."}
            </p>
            {setupFlowCollapsed ? (
              <p className="panel__empty">
                Setup is collapsed. Expand to edit battery and experiment inputs.
              </p>
            ) : productId ? (
              <div className="panel__form">
                {labMode === "lab" && !showManualControls ? (
                  <section className="panel__notice panel__notice--info">
                    <strong>Lab automation path:</strong> Steps 1 and 2 are handled during
                    experiment creation when no battery is selected.
                    <div className="panel__actions panel__actions--priority">
                      <button
                        type="button"
                        className="panel__action panel__action--prominent"
                        onClick={() => setLabShowManualControls(true)}
                      >
                        Show manual setup controls
                      </button>
                    </div>
                  </section>
                ) : null}
                {showManualControls ? (
                  <>
                {batteryStatus ? (
                  <p className="panel__success">{batteryStatus}</p>
                ) : null}
                <p className="panel__subheading">
                  Step 1 · Create query battery foundation
                </p>
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
                  className="panel__action panel__action--prominent"
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
                {batteryForm.generationMode === "bottom_up" && !hasBottomUpMetadata ? (
                  <div className="panel__notice panel__notice--info">
                    Bottom-up has weak product metadata. Use Advanced overrides below or we
                    will offer fallback to top-down at generation time.
                  </div>
                ) : null}
                <details
                  open={advancedOverridesOpen}
                  onToggle={(event) =>
                    setAdvancedOverridesOpen(event.currentTarget.open)
                  }
                >
                  <summary className="panel__label">
                    Advanced overrides (optional)
                  </summary>
                  <div className="panel__form">
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
                  </div>
                </details>
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
                <p className="panel__subheading">Step 2 · Generate queries</p>
                <button
                  type="button"
                  className="panel__action panel__action--prominent"
                  onClick={() => handleGenerateQueries(experimentForm.batteryId)}
                  disabled={Boolean(queryGenerationDisabledReason)}
                >
                  {isSubmitting ? (
                    <>
                      Generating queries<span className="button__dots" />
                    </>
                  ) : (
                    "Generate queries"
                  )}
                </button>
                {queryGenerationDisabledReason ? (
                  <p className="panel__muted">{queryGenerationDisabledReason}</p>
                ) : null}
                <p className="panel__subheading">
                  Step 2a · Review and save battery details and queries
                </p>
                <details
                  open={batteryDetailsOpen}
                  onToggle={(event) =>
                    setBatteryDetailsOpen(event.currentTarget.open)
                  }
                >
                  <summary className="panel__label">
                    Battery details and query settings
                  </summary>
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
                                  onClick={() =>
                                    handleQueryDelete(selectedBattery.id, query.id)
                                  }
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
                      <button
                        type="button"
                        className="panel__action panel__action--prominent"
                        onClick={handleUpdateBattery}
                        disabled={isSubmitting}
                      >
                        Save battery details
                      </button>
                    </div>
                  ) : (
                    <p className="panel__empty">
                      Select a battery to review details and query settings.
                    </p>
                  )}
                </details>
                {batteryGenerationReport ? (
                  <div className="panel__notice panel__notice--info">
                    {typeof batteryGenerationReport.generated_count === "number" ? (
                      <>
                        Generated: {batteryGenerationReport.generated_count} ·{" "}
                      </>
                    ) : null}
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
                    {typeof batteryGenerationReport.audience_segments_generated ===
                    "number" ? (
                      <>
                        {" "}
                        · Audience segments:{" "}
                        {batteryGenerationReport.audience_segments_generated}
                      </>
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
                      <>
                        <p className="panel__error">
                          {batteryGenerationReport.clarification_prompt}
                        </p>
                        <button
                          type="button"
                          className="button button--ghost"
                          onClick={() => router.push("/admin")}
                        >
                          Open Admin to set canonical spec
                        </button>
                      </>
                    ) : null}
                    {batteryGenerationReport.audience_segment_labels &&
                    batteryGenerationReport.audience_segment_labels.length > 0 ? (
                      <>
                        <p className="panel__muted">Behavioral segments applied</p>
                        <ul className="panel__list">
                          {batteryGenerationReport.audience_segment_labels
                            .slice(0, 4)
                            .map((label) => (
                              <li key={label}>{label}</li>
                            ))}
                        </ul>
                      </>
                    ) : null}
                    {batteryGenerationReport.audience_segments_source ===
                      "canonical_fallback" &&
                    batteryGenerationReport.audience_segments_fallback_reason ? (
                      <p className="panel__muted">
                        Fallback:{" "}
                        {batteryGenerationReport.audience_segments_fallback_reason}
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
                    {batteryGenerationReport.generated_preview &&
                    batteryGenerationReport.generated_preview.length > 0 ? (
                      <>
                        <p className="panel__muted">Pre-validation generated sample</p>
                        <ul className="panel__list">
                          {batteryGenerationReport.generated_preview
                            .slice(0, 5)
                            .map((item, index) => (
                              <li key={`${item.query_text}-${index}`}>
                                {item.query_text}
                              </li>
                            ))}
                        </ul>
                      </>
                    ) : null}
                  </div>
                ) : null}
                {selectedBattery ? (
                  <details
                    open={audienceSegmentsOpen}
                    onToggle={(event) =>
                      setAudienceSegmentsOpen(event.currentTarget.open)
                    }
                    className="panel__card"
                  >
                    <summary className="panel__label">
                      Audience segments for top-down generation
                    </summary>
                    <p className="panel__muted">
                      These are session-derived behavioral segments used to condition
                      top-down/hybrid query generation. Disable any segment to exclude it.
                    </p>
                    {audienceSegmentsStatus ? (
                      <p className="panel__status">{audienceSegmentsStatus}</p>
                    ) : null}
                    {audienceSegments.length === 0 ? (
                      <div className="panel__notice panel__notice--info">
                        No session-derived segments yet. Fallback stays active: canonical
                        intent spec + product metadata + stored archetypes.
                      </div>
                    ) : (
                      <ul className="panel__list">
                        {audienceSegments.map((segment) => (
                          <li key={segment.id}>
                            <div
                              className="panel__row"
                              style={{ justifyContent: "space-between" }}
                            >
                              <div>
                                <strong>{segment.label}</strong>
                                {typeof segment.support === "number" ? (
                                  <span className="panel__muted">
                                    {" "}
                                    · support {segment.support}
                                  </span>
                                ) : null}
                                {typeof segment.confidence === "number" ? (
                                  <span className="panel__muted">
                                    {" "}
                                    · confidence{" "}
                                    {Math.round(segment.confidence * 100)}%
                                  </span>
                                ) : null}
                                {segment.description ? (
                                  <p className="panel__muted">{segment.description}</p>
                                ) : null}
                              </div>
                              <button
                                type="button"
                                className="button button--ghost"
                                onClick={() =>
                                  handleSegmentToggle(segment.id, !segment.active)
                                }
                              >
                                {segment.active ? "Disable" : "Enable"}
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </details>
                ) : null}
                {generatedCandidates.length > 0 ? (
                  <div className="panel__card">
                    <div className="panel__header">
                      <h4>Preview & approve queries</h4>
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() => setGeneratedCandidates([])}
                      >
                        Clear preview
                      </button>
                    </div>
                    <div className="panel__form">
                      {generatedCandidates.map((candidate, index) => (
                        <div
                          className="panel__row panel__row--dense"
                          key={`${candidate.query_text}-${index}`}
                        >
                          <label className="panel__toggle">
                            <input
                              type="checkbox"
                              checked={candidate.selected}
                              onChange={(event) =>
                                setGeneratedCandidates((current) =>
                                  current.map((item, idx) =>
                                    idx === index
                                      ? { ...item, selected: event.target.checked }
                                      : item,
                                  ),
                                )
                              }
                            />
                            <span>{candidate.query_text}</span>
                          </label>
                          <input
                            className="panel__input panel__input--tiny"
                            type="number"
                            min={0}
                            step={0.1}
                            value={candidate.weight ?? 1}
                            onChange={(event) =>
                              setGeneratedCandidates((current) =>
                                current.map((item, idx) =>
                                  idx === index
                                    ? { ...item, weight: Number(event.target.value) }
                                    : item,
                                ),
                              )
                            }
                          />
                        </div>
                      ))}
                      <button
                        type="button"
                        className="panel__action panel__action--prominent"
                        onClick={() =>
                          handleSaveGeneratedCandidates(experimentForm.batteryId)
                        }
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <>
                            Saving queries<span className="button__dots" />
                          </>
                        ) : (
                          "Save selected queries"
                        )}
                      </button>
                    </div>
                  </div>
                ) : null}
                  </>
                ) : null}
                <p className="panel__subheading">
                  Step 3 · Create experiment from the configured battery
                </p>
                <p className="panel__step-helper">
                  {labMode === "lab"
                    ? "Define hypothesis/policy, then create experiment. Lab mode can auto-create and auto-run the baseline path."
                    : "Define hypothesis and competitor policy, then create the experiment."}
                </p>
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
                  {jsonErrors.competitorPolicy ? (
                    <span className="panel__error">{jsonErrors.competitorPolicy}</span>
                  ) : null}
                </label>
                <details
                  className="panel__details"
                  open={setupSecondaryActionsOpen}
                  onToggle={(event) =>
                    setSetupSecondaryActionsOpen(event.currentTarget.open)
                  }
                >
                  <summary className="panel__details-summary">More setup actions</summary>
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() =>
                        setExperimentForm((prev) => ({
                          ...prev,
                          hypothesis:
                            '{"metric":"win_rate","direction":"increase","rationale":"Outcome framing improves intent alignment"}',
                        }))
                      }
                    >
                      Use hypothesis template
                    </button>
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() =>
                        setExperimentForm((prev) => ({
                          ...prev,
                          competitorPolicy:
                            '{"competitor_client_ids":["client-nike","client-adidas"],"strategy":"hold_constant"}',
                        }))
                      }
                    >
                      Use competitor template
                    </button>
                  </div>
                </details>
                {labMode === "lab" && showManualControls ? (
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => setLabShowManualControls(false)}
                    >
                      Hide manual setup controls
                    </button>
                  </div>
                ) : null}
                <button
                  type="button"
                  className="panel__action panel__action--prominent"
                  onClick={handleCreateExperiment}
                  disabled={Boolean(createExperimentDisabledReason)}
                >
                  {isSubmitting ? (
                    <>
                      Creating experiment<span className="button__dots" />
                    </>
                  ) : (
                    "Create experiment"
                  )}
                </button>
                {createExperimentDisabledReason ? (
                  <p className="panel__muted">{createExperimentDisabledReason}</p>
                ) : null}
              </div>
            ) : (
              <p className="panel__empty">Select a product to create a battery.</p>
            )}
          </section>

          <div className="detail__grid">
            <section className="panel__card panel__card--primary panel__card--full-row" ref={variantsSectionRef}>
              <div className="panel__header">
                <h3>{labMode === "lab" ? "Variants and Iteration" : "Variants"}</h3>
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
              <p className="panel__muted">
                Variants are copy candidates tested against the same query battery.
              </p>
              <p className="panel__subheading">Step 4 · Create variants</p>
              <p className="panel__step-helper">
                {labMode === "lab"
                  ? "Automation-first: generate candidate copy, then create and run quickly."
                  : "Choose a source, shape candidate copy, then add the variant."}
              </p>
              <div className="variant-flow">
                <span className="variant-flow__step is-active">1. Define</span>
                <span className="variant-flow__step is-active">2. Create</span>
                <span
                  className={`variant-flow__step ${
                    variants.length > 0 ? "is-active" : ""
                  }`}
                >
                  3. Run
                </span>
              </div>
              {labMode === "lab" && !showManualControls ? (
                <section className="panel__notice panel__notice--info">
                  <strong>Lab iteration path:</strong> generate candidates, create the selected
                  one, then run it.
                  <div className="panel__actions panel__actions--priority">
                    <button
                      type="button"
                      className="panel__action panel__action--prominent"
                      onClick={() =>
                        hasValidationSignals
                          ? void handleGenerateLoopVariants()
                          : void handleGenerateColdStartVariants()
                      }
                      disabled={!selectedExperimentId || isGeneratingLoopVariant}
                    >
                      {isGeneratingLoopVariant
                        ? "Generating candidates…"
                        : hasValidationSignals
                          ? "Generate candidate from loop evidence"
                          : "Generate cold-start candidate"}
                    </button>
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={handleCreateAndRunVariantFromLoopCandidate}
                      disabled={loopGeneratedVariants.length === 0 || isSubmitting}
                    >
                      {isSubmitting
                        ? "Creating + running candidate…"
                        : "Create + run selected candidate"}
                    </button>
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => setLabShowManualControls(true)}
                    >
                      Show manual variant controls
                    </button>
                  </div>
                  {loopGeneratedVariants.length > 0 ? (
                    <label className="panel__label">
                      Selected candidate
                      <select
                        className="panel__input"
                        value={String(selectedLoopCandidateIndex)}
                        onChange={(event) =>
                          setSelectedLoopCandidateIndex(Number(event.target.value))
                        }
                      >
                        {loopGeneratedVariants.map((candidate, index) => (
                          <option key={`${candidate.label}-${index}`} value={String(index)}>
                            {index + 1}. {candidate.label} · conf {candidate.confidence.toFixed(2)}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                  {loopGeneratedVariants[selectedLoopCandidateIndex]?.rationale ? (
                    <p className="panel__muted">
                      {loopGeneratedVariants[selectedLoopCandidateIndex]?.rationale}
                    </p>
                  ) : null}
                  {loopGenerationStatus ? (
                    <p className="panel__success">{loopGenerationStatus}</p>
                  ) : null}
                </section>
              ) : (
                <>
              <div className="variant-source">
                <div className="variant-source__header">
                  <h4>Choose variant source</h4>
                  <span className="panel__muted">
                    Recommended now:{" "}
                    <strong>{recommendedVariantSource.replace("_", " ")}</strong>
                  </span>
                </div>
                <div className="variant-source__tabs">
                  <button
                    type="button"
                    className={`variant-source__tab ${
                      variantSourceMode === "manual" ? "is-active" : ""
                    }`}
                    onClick={() => {
                      setVariantSourceMode("manual");
                      setVariantSourceManualOverride(true);
                    }}
                  >
                    Manual
                  </button>
                  <button
                    type="button"
                    className={`variant-source__tab ${
                      variantSourceMode === "simulation" ? "is-active" : ""
                    }`}
                    onClick={() => {
                      setVariantSourceMode("simulation");
                      setVariantSourceManualOverride(true);
                    }}
                  >
                    Simulation prefill
                  </button>
                  <button
                    type="button"
                    className={`variant-source__tab ${
                      variantSourceMode === "loop_evidence" ? "is-active" : ""
                    }`}
                    onClick={() => {
                      setVariantSourceMode("loop_evidence");
                      setVariantSourceManualOverride(true);
                    }}
                  >
                    Loop evidence
                  </button>
                  <button
                    type="button"
                    className={`variant-source__tab ${
                      variantSourceMode === "cold_start" ? "is-active" : ""
                    }`}
                    onClick={() => {
                      setVariantSourceMode("cold_start");
                      setVariantSourceManualOverride(true);
                    }}
                  >
                    Cold-start
                  </button>
                </div>
                <p className="panel__step-helper">{recommendedVariantSourceReason}</p>
                <p className="variant-source__hint">
                  {variantSourceMode === "manual"
                    ? "Use when you already have candidate copy and want full control."
                    : variantSourceMode === "simulation"
                      ? "Use when simulation already produced a useful revision for this product."
                      : variantSourceMode === "loop_evidence"
                        ? "Use when runs/metrics/validation history exists and you want evidence-weighted candidates."
                        : "Use when history is sparse and you need a first set of aligned variants."}
                </p>
                {variantSourceManualOverride &&
                variantSourceMode !== recommendedVariantSource ? (
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => {
                        setVariantSourceMode(recommendedVariantSource);
                        setVariantSourceManualOverride(false);
                      }}
                    >
                      Use recommended source
                    </button>
                  </div>
                ) : null}
              </div>
              <p className="panel__subheading">Step 8 · Generate next variants from updated evidence</p>
              <p className="panel__step-helper">
                Prefer loop evidence once runs and validation signals are available.
              </p>
              <div className="panel__form">
                <label className="panel__label">
                  Role
                  <select
                    className="panel__input"
                    value={variantForm.role}
                    onChange={(event) => {
                      const role = event.target.value as "candidate" | "control";
                      setVariantForm((prev) => ({
                        ...prev,
                        role,
                        label:
                          role === "control"
                            ? "Control (current copy)"
                            : prev.label === "Control (current copy)"
                              ? "Hypothesis (variant)"
                              : prev.label,
                      }));
                    }}
                  >
                    <option value="candidate">Candidate</option>
                    <option value="control">Control</option>
                  </select>
                </label>
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
                  Candidate description
                  <textarea
                    className="panel__textarea"
                    value={variantForm.description}
                    onChange={(event) =>
                      setVariantForm((prev) => ({
                        ...prev,
                        description: event.target.value,
                      }))
                    }
                    rows={5}
                    placeholder="Write the copy variation to test..."
                  />
                </label>
                {variantSourceMode === "simulation" ? (
                  <>
                    <label className="panel__label">
                      Prefill from simulation revision (same product)
                      <select
                        className="panel__input"
                        value={selectedSimulationRevisionId}
                        onChange={(event) => setSelectedSimulationRevisionId(event.target.value)}
                        disabled={simulationRevisions.length === 0}
                      >
                        {simulationRevisions.length === 0 ? (
                          <option value="">No simulation revisions found</option>
                        ) : null}
                        {simulationRevisions.map((revision) => (
                          <option key={revision.id} value={revision.id}>
                            {new Date(
                              revision.updated_at ?? revision.created_at ?? "",
                            ).toLocaleString()} · {revision.status ?? "draft"}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="panel__action panel__action--ghost"
                        onClick={handleUseSimulationRevision}
                        disabled={simulationRevisions.length === 0}
                      >
                        Use selected simulation revision
                      </button>
                    </div>
                    {simulationRevisionStatus ? (
                      <p className="panel__success">{simulationRevisionStatus}</p>
                    ) : null}
                    <div className="panel__separator" />
                  </>
                ) : null}
                {variantSourceMode === "loop_evidence" ? (
                  <>
                    <label className="panel__label">
                      Prefill from loop evidence (experiment + simulation + validation)
                      <select
                        className="panel__input"
                        value={String(selectedLoopCandidateIndex)}
                        onChange={(event) =>
                          setSelectedLoopCandidateIndex(Number(event.target.value))
                        }
                        disabled={loopGeneratedVariants.length === 0}
                      >
                        {loopGeneratedVariants.length === 0 ? (
                          <option value="0">No generated candidates yet</option>
                        ) : null}
                        {loopGeneratedVariants.map((candidate, index) => (
                          <option key={`${candidate.label}-${index}`} value={String(index)}>
                            {index + 1}. {candidate.label} · conf {candidate.confidence.toFixed(2)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="panel__action panel__action--ghost"
                        onClick={handleGenerateLoopVariants}
                        disabled={!selectedExperimentId || isGeneratingLoopVariant}
                      >
                        {isGeneratingLoopVariant &&
                        variantGenerationRequestType === "loop"
                          ? "Generating from loop…"
                          : "Generate from loop evidence"}
                      </button>
                    </div>
                    {loopGeneratedVariants[selectedLoopCandidateIndex]?.rationale ? (
                      <p className="panel__muted">
                        {loopGeneratedVariants[selectedLoopCandidateIndex]?.rationale}
                      </p>
                    ) : null}
                    {loopGenerationStatus ? (
                      <p className="panel__success">{loopGenerationStatus}</p>
                    ) : null}
                    {loopEvidenceAdvisory ? (
                      <p className="panel__muted">{loopEvidenceAdvisory}</p>
                    ) : null}
                    <div className="panel__separator" />
                  </>
                ) : null}
                {variantSourceMode === "cold_start" ? (
                  <>
                    <label className="panel__label">
                      Generate cold-start copy (no prior loop evidence)
                      <select
                        className="panel__input"
                        value={coldStartGenerationStrategy}
                        onChange={(event) =>
                          setColdStartGenerationStrategy(
                            event.target.value as "bottom_up" | "top_down" | "both",
                          )
                        }
                      >
                        <option value="both">Both (recommended)</option>
                        <option value="bottom_up">Bottom-up (features/use-cases)</option>
                        <option value="top_down">Top-down (goals/positioning)</option>
                      </select>
                    </label>
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="panel__action panel__action--ghost"
                        onClick={handleGenerateColdStartVariants}
                        disabled={!selectedExperimentId || isGeneratingLoopVariant}
                      >
                        {isGeneratingLoopVariant &&
                        variantGenerationRequestType === "cold_start"
                          ? "Generating cold-start copy…"
                          : "Generate cold-start copy"}
                      </button>
                    </div>
                    {loopGenerationStatus ? (
                      <p className="panel__success">{loopGenerationStatus}</p>
                    ) : null}
                    <div className="panel__separator" />
                  </>
                ) : null}
                <details
                  className="panel__details"
                  open={variantSecondaryActionsOpen}
                  onToggle={(event) =>
                    setVariantSecondaryActionsOpen(event.currentTarget.open)
                  }
                >
                  <summary className="panel__details-summary">More variant actions</summary>
                  <div className="panel__actions">
                    {variantSourceMode === "loop_evidence" ? (
                      <>
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={handleUseGeneratedLoopVariant}
                          disabled={loopGeneratedVariants.length === 0}
                        >
                          Use selected loop candidate
                        </button>
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={handleCreateVariantFromLoopCandidate}
                          disabled={loopGeneratedVariants.length === 0 || isSubmitting}
                        >
                          {isSubmitting
                            ? "Creating variant…"
                            : "Create variant from selected loop candidate"}
                        </button>
                      </>
                    ) : null}
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() =>
                        setVariantForm((prev) => ({
                          ...prev,
                          description:
                            "Outcome-led copy that emphasizes user goals and capabilities.",
                        }))
                      }
                    >
                      Use description template
                    </button>
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => setVariantAdvancedOpen((open) => !open)}
                    >
                      {variantAdvancedOpen ? "Hide advanced" : "Advanced JSON"}
                    </button>
                  </div>
                </details>
                {variantAdvancedOpen ? (
                  <>
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
                      Payload overrides (JSON)
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
                        placeholder='{"metadata":{"channel":"web"}}'
                      />
                    </label>
                    {jsonErrors.variantPayload ? (
                      <span className="panel__error">{jsonErrors.variantPayload}</span>
                    ) : null}
                  </>
                ) : null}
                <button
                  type="button"
                  className="panel__action panel__action--prominent"
                  onClick={handleCreateVariant}
                  disabled={Boolean(addVariantDisabledReason)}
                >
                  {isSubmitting ? (
                    <>
                      Adding variant<span className="button__dots" />
                    </>
                  ) : (
                    "Add variant"
                  )}
                </button>
                {addVariantDisabledReason ? (
                  <p className="panel__muted">{addVariantDisabledReason}</p>
                ) : null}
              </div>
                {labMode === "lab" ? (
                  <div className="panel__actions">
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => setLabShowManualControls(false)}
                    >
                      Hide manual variant controls
                    </button>
                  </div>
                ) : null}
                </>
              )}
              <p className="panel__subheading">Step 5 · Run experiment across battery queries</p>
              {runVariantDisabledReason ? (
                <p className="panel__muted">{runVariantDisabledReason}</p>
              ) : null}
              {variants.length === 0 ? (
                <p className="panel__empty">Add variants to run experiments.</p>
              ) : (
                <ul className="panel__list">
                {variants.map((variant) => (
                  <li key={variant.id}>
                    {(() => {
                      const resolvedDescription = resolveVariantDescription(variant);
                      const isExpanded = expandedVariantId === variant.id;
                      return (
                        <>
                    <div className="panel__meta">
                      <span>{variant.label}</span>
                      <span className="panel__badge panel__badge--secondary">
                        {variant.type}
                      </span>
                      <span
                        className={`panel__badge ${
                          metricsByVariant.has(variant.id)
                            ? "panel__badge--success"
                            : "panel__badge--secondary"
                        }`}
                      >
                        {metricsByVariant.has(variant.id) ? "Tested" : "Draft"}
                      </span>
                    </div>
                    {resolvedDescription ? (
                      <div className="panel__actions">
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={() =>
                            setExpandedVariantId((current) =>
                              current === variant.id ? null : variant.id,
                            )
                          }
                        >
                          {isExpanded ? "Hide tested copy" : "View tested copy"}
                        </button>
                      </div>
                    ) : (
                      <span className="panel__muted">No copy payload yet.</span>
                    )}
                    {isExpanded && resolvedDescription ? (
                      <pre className="panel__pre">{resolvedDescription}</pre>
                    ) : null}
                    {metricsByVariant.has(variant.id) ? (
                      <div className="panel__meta">
                        <span className="panel__muted">
                          Win rate:{" "}
                          {renderMetricValue(
                            ((metricsByVariant.get(variant.id)?.metrics ?? {}) as Record<
                              string,
                              unknown
                            >).win_rate,
                          )}
                        </span>
                        <span className="panel__muted">
                          Runs:{" "}
                          {renderMetricValue(
                            ((metricsByVariant.get(variant.id)?.metrics ?? {}) as Record<
                              string,
                              unknown
                            >).total_runs,
                          )}
                        </span>
                      </div>
                    ) : null}
                    <button
                      type="button"
                      className={`panel__action ${
                        labMode === "lab" && !showManualControls
                          ? "panel__action--ghost"
                          : "panel__action--prominent"
                      }`}
                      onClick={() => handleRunVariant(variant.id)}
                      disabled={runningVariantId === variant.id || !canRunVariantTests}
                    >
                        {runningVariantId === variant.id ? "Running…" : "Run variant test"}
                    </button>
                        </>
                      );
                    })()}
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
                        disabled={runningVariantId === nextTest.variant_id || !canRunVariantTests}
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
              <section className="panel__notice panel__notice--info outcome-snapshot">
                <div className="panel__meta">
                  <strong>Outcome snapshot</strong>
                  <span className="panel__badge panel__badge--secondary">Unified view</span>
                </div>
                <div className="outcome-snapshot__grid">
                  <div className="outcome-snapshot__item">
                    <span className="outcome-snapshot__label">Latest run</span>
                    <span className="outcome-snapshot__value">
                      {outcomeSnapshot.runVariantLabel}
                    </span>
                    <span className="panel__muted">
                      Query: {outcomeSnapshot.runQueryLabel}
                      {outcomeSnapshot.runCreatedAt
                        ? ` · ${new Date(outcomeSnapshot.runCreatedAt).toLocaleString()}`
                        : ""}
                    </span>
                  </div>
                  <div className="outcome-snapshot__item">
                    <span className="outcome-snapshot__label">Key metrics</span>
                    <span className="outcome-snapshot__value">
                      Win rate: {outcomeSnapshot.winRate}
                    </span>
                    <span className="panel__muted">Avg score: {outcomeSnapshot.avgScore}</span>
                  </div>
                  <div className="outcome-snapshot__item">
                    <span className="outcome-snapshot__label">Validation state</span>
                    <span className="outcome-snapshot__value">
                      {outcomeSnapshot.validationState}
                    </span>
                    {!hasValidationSignals ? (
                      <button
                        type="button"
                        className="panel__action panel__action--ghost"
                        onClick={() =>
                          router.push(
                            selectedExperimentId
                              ? `/validation?experiment_id=${selectedExperimentId}`
                              : "/validation",
                          )
                        }
                      >
                        Go to Validation
                      </button>
                    ) : (
                      <span className="panel__muted">Signals are being tracked.</span>
                    )}
                  </div>
                </div>
              </section>
              <div className="panel__grid">
                <div className="panel__column">
                  <h4 className="panel__subtitle">Step 6 · Review outcomes and metrics</h4>
                  {latestMetric ? (
                    <ul className="panel__list panel__list--compact">
                      <li>Total runs: {renderMetricValue(latestMetric.total_runs, "-")}</li>
                      <li>Wins: {renderMetricValue(latestMetric.wins, "-")}</li>
                      <li>Win rate: {renderMetricValue(latestMetric.win_rate, "-")}</li>
                      <li>
                        Win rate (keyword):{" "}
                        {renderMetricValue(latestMetric.win_rate_keyword, "-")}
                      </li>
                      <li>
                        Win rate (robust):{" "}
                        {renderMetricValue(latestMetric.win_rate_robust, "-")}
                      </li>
                      <li>Avg score: {renderMetricValue(latestMetric.avg_score, "-")}</li>
                      <li>
                        Judge consensus win rate:{" "}
                        {renderMetricValue(latestMetric.judge_consensus_win_rate, "-")}
                      </li>
                    </ul>
                  ) : (
                    <p className="panel__muted">Run a variant to generate metrics.</p>
                  )}
                </div>
                <div className="panel__column">
                  <div className="panel__meta">
                    <h4 className="panel__subtitle">Why we lost (experiment deltas)</h4>
                    {experimentGapSummary?.total ? (
                      <span className="panel__badge panel__badge--secondary">
                        {experimentGapSummary.total} linked runs
                      </span>
                    ) : null}
                  </div>
                  {!experimentGapSummary || experimentGapSummary.total === 0 ? (
                    <p className="panel__muted">
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
                </div>
              </div>
            </section>

            <section className="panel__card panel__card--secondary panel__card--full-row">
              <div className="panel__header">
                <h3>Orchestrator Recommendations</h3>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => setRecommendationsOpen((open) => !open)}
                >
                  {recommendationsOpen ? "Hide details" : "Show details"}
                </button>
              </div>
              <p className="panel__subheading">Optional guidance</p>
              <p className="panel__muted">
                Suggested next actions based on current variant outcomes and run history.
              </p>
              {!recommendationsOpen ? (
                <p className="panel__muted">
                  Recommendations are collapsed to keep focus on execution steps.
                </p>
              ) : recommendations.length === 0 ? (
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
                            disabled={
                              runningVariantId === rec.recommendation.variant_id ||
                              !canRunVariantTests
                            }
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

          </div>

          <section className="panel__card panel__card--secondary panel__card--full-row">
            <div className="panel__header">
              <h3>History</h3>
              <div className="panel__meta">
                <span className="panel__badge panel__badge--secondary">
                  Experiments: {experiments.length}
                </span>
                <span className="panel__badge panel__badge--secondary">
                  Runs: {runs.length}
                </span>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => setHistoryCollapsed((open) => !open)}
                >
                  {historyCollapsed ? "Expand history" : "Collapse history"}
                </button>
              </div>
            </div>
            <p className="panel__subheading">Reference history</p>
            <p className="panel__step-helper">
              Review past experiments, runs, and metrics without interrupting the active flow.
            </p>
            {historyCollapsed ? (
              <p className="panel__muted">
                History is collapsed to keep focus on the active experiment flow.
              </p>
            ) : (
              <div className="panel__grid">
              <div className="panel__column">
                <div className="panel__meta">
                  <h4 className="panel__subtitle">Experiments</h4>
                  {experiments.length > 0 ? (
                    <span className="panel__badge">{experiments.length}</span>
                  ) : null}
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
                          <span className="history-panel__meta">
                            Created: {formatTimestamp(experiment.created_at)}
                          </span>
                          {typeof experimentSnapshots[experiment.id]?.winRate ===
                          "number" ? (
                            <span className="history-panel__meta">
                              Latest win rate:{" "}
                              {Math.round(
                                (experimentSnapshots[experiment.id]?.winRate ?? 0) * 100,
                              )}
                              % · Winner:{" "}
                              {experimentSnapshots[experiment.id]?.winnerLabel ?? "—"}
                            </span>
                          ) : (
                            <span className="history-panel__meta">
                              Latest win rate: — · Winner: —
                            </span>
                          )}
                        </button>
                        {experiment.id === selectedExperimentId ? (
                          <div className="panel__meta panel__meta--stack">
                            <span className="panel__muted">
                              Battery:{" "}
                              {batteries.find(
                                (battery) => battery.id === experiment.battery_id,
                              )?.name ??
                                experiment.battery_id ??
                                "Not linked"}
                            </span>
                            <span className="panel__muted">
                              Updated: {formatTimestamp(experiment.updated_at)}
                            </span>
                            <span className="panel__muted">
                              Variants: {variants.length}
                            </span>
                            <span className="panel__muted">Runs: {runs.length}</span>
                            <span className="panel__muted">
                              Metrics: {metrics.length}
                            </span>
                            <div className="panel__actions">
                              {experiment.status === "draft" ? (
                                <button
                                  type="button"
                                  className="panel__action"
                                  onClick={() =>
                                    handleSaveExperimentDraft(experiment.id)
                                  }
                                  disabled={savingExperimentId === experiment.id}
                                >
                                  {savingExperimentId === experiment.id
                                    ? "Saving…"
                                    : "Save draft"}
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="panel__action panel__action--ghost"
                                onClick={() =>
                                  variantsSectionRef.current?.scrollIntoView({
                                    behavior: "smooth",
                                  })
                                }
                              >
                                View variants
                              </button>
                              <button
                                type="button"
                                className="panel__action panel__action--ghost"
                                onClick={() =>
                                  runsSectionRef.current?.scrollIntoView({
                                    behavior: "smooth",
                                  })
                                }
                              >
                                View runs
                              </button>
                              <button
                                type="button"
                                className="panel__action panel__action--ghost"
                                onClick={() =>
                                  metricsSectionRef.current?.scrollIntoView({
                                    behavior: "smooth",
                                  })
                                }
                              >
                                View metrics
                              </button>
                            </div>
                          </div>
                        ) : experiment.status === "draft" ? (
                          <div className="panel__actions">
                            <button
                              type="button"
                              className="panel__action panel__action--ghost"
                              onClick={() => handleSaveExperimentDraft(experiment.id)}
                              disabled={savingExperimentId === experiment.id}
                            >
                              {savingExperimentId === experiment.id
                                ? "Saving…"
                                : "Save draft"}
                            </button>
                          </div>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="panel__column" ref={runsSectionRef}>
                <div className="panel__meta">
                  <h4 className="panel__subtitle">Runs</h4>
                  {runs.length > 0 ? (
                    <span className="panel__badge">{runs.length}</span>
                  ) : null}
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
                        <div className="panel__actions">
                          <button
                            type="button"
                            className="panel__action panel__action--ghost"
                            onClick={() => void handleDeleteExperimentRun(run.id)}
                          >
                            Delete run
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            )}
          </section>

          <section className="panel__card panel__card--secondary" ref={metricsSectionRef}>
            <div className="panel__header">
              <h3>Metrics</h3>
              <div className="panel__meta">
                <span className="panel__muted">Experiment-scoped (compact)</span>
              </div>
            </div>
            <div className="panel__meta panel__meta--stack">
              <span className="panel__muted">
                Entries: {metricsHistory.length}
                {latestMetricEntry?.created_at
                  ? ` · Last update: ${new Date(latestMetricEntry.created_at).toLocaleString()}`
                  : ""}
              </span>
              {renderSparkline(metricsTrend) ?? (
                <span className="panel__muted">No trend yet.</span>
              )}
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
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={() => setMetricsHistoryExpanded((open) => !open)}
                disabled={metricsHistory.length === 0}
              >
                {metricsHistoryExpanded ? "Hide history" : "Show history"}
              </button>
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={() => router.push("/overview")}
              >
                Open Overview analytics
              </button>
            </div>
            {metricsHistory.length === 0 ? (
              <p className="panel__empty">No metrics history yet.</p>
            ) : !metricsHistoryExpanded ? (
              <p className="panel__muted">
                History is collapsed to keep this page focused on execution.
              </p>
            ) : (
              <ul className="panel__list">
                {recentMetrics.map((metric) => {
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
                        Win rate: {renderMetricValue(values.win_rate)} · Avg score:{" "}
                        {renderMetricValue(values.avg_score)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="panel__card panel__card--primary panel__card--full-row">
            <div className="panel__header">
              <h3>Step 7 · Validate synthetic and observed results</h3>
              <span
                className={`panel__badge ${
                  hasValidationSignals ? "panel__badge--success" : "panel__badge--secondary"
                }`}
              >
                {hasValidationSignals ? "Validation started" : "Validation pending"}
              </span>
            </div>
            <p className="panel__muted">
              Validation is required to ground lab signals with observed evidence and build
              decision trust.
            </p>
            <div className="panel__meta panel__meta--stack">
              <span className="panel__muted">
                Logged: {validationSummary?.total_logged ?? 0} · Verified:{" "}
                {validationSummary?.verified_runs ?? 0} · Accuracy:{" "}
                {typeof validationSummary?.accuracy === "number"
                  ? `${Math.round(validationSummary.accuracy * 100)}%`
                  : "—"}
              </span>
              <span className="panel__muted">
                Observed logs: {validationSummary?.observed_signals_logged ?? 0} · Observed
                accuracy:{" "}
                {typeof validationSummary?.observed_accuracy === "number"
                  ? `${Math.round(validationSummary.observed_accuracy * 100)}%`
                  : "—"}
              </span>
            </div>
            <div className="panel__actions">
              <button
                type="button"
                className="panel__action panel__action--prominent"
                onClick={() =>
                  router.push(
                    selectedExperimentId
                      ? `/validation?experiment_id=${selectedExperimentId}`
                      : "/validation",
                  )
                }
              >
                Open Validation
              </button>
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={() =>
                  variantsSectionRef.current?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  })
                }
              >
                Back to variants (Step 8)
              </button>
            </div>
          </section>

          {brandId ? (
            validationSummary?.unlock_ready ? (
              <div ref={(node) => (beliefsRef.current = node)}>
                <BrandBeliefs
                  brandId={brandId}
                  clientId={clientId ?? undefined}
                  userId={userId ?? undefined}
                  limit={50}
                  onUseBelief={(belief) => handleUseBelief(belief as BrandBelief)}
                  viewMode={beliefsViewMode}
                  onViewModeChange={setBeliefsViewMode}
                />
              </div>
            ) : (
              <section className="panel__card">
                <div className="panel__header">
                  <h3>Pattern Insights (Locked)</h3>
                  <span className="panel__badge panel__badge--secondary">
                    Locked
                  </span>
                </div>
                <p className="panel__muted">
                  Insights appear after enough experiment evidence accumulates.
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
                  Progress: {Math.round((validationSummary?.progress ?? 0) * 100)}%
                </p>
              </section>
            )
          ) : null}

          <section className="panel__card panel__card--secondary panel__card--full-row">
            <div className="panel__header">
              <h3>Scheduling</h3>
            </div>
            <p className="panel__subheading">Operational scheduling</p>
            <p className="panel__step-helper">
              Configure recurring reruns and backfills after the main experiment cycle is set.
            </p>
            {selectedExperiment ? (
              <div className="panel__form">
                {scheduleStatus ? <p className="panel__success">{scheduleStatus}</p> : null}
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
                    className="panel__action panel__action--prominent product__tooltip tooltip--below"
                    data-tooltip="Save interval settings and schedule future due runs."
                    onClick={handleScheduleSave}
                  >
                    Save schedule
                  </button>
                  <button
                    type="button"
                    className="panel__action panel__action--ghost product__tooltip tooltip--below"
                    data-tooltip="Run all variants now and refresh last/next run timestamps."
                    onClick={handleBackfill}
                  >
                    Backfill schedule
                  </button>
                </div>
              </div>
            ) : (
              <p className="panel__empty">Select an experiment to schedule reruns.</p>
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
