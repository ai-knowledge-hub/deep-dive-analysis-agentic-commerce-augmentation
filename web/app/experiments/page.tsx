"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAppUser } from "../../lib/auth";
import type {
  AdminProduct,
  BrandBelief,
  CopyRevision,
  Experiment,
  ExperimentExecutionState,
  ExperimentHypothesis,
  ExperimentMetric,
  ExperimentRecommendation,
  ExperimentRun,
  LoopGeneratedVariantCandidate,
  ExperimentVariant,
  NextTestRecommendation,
  AgentRun,
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
  getExperimentExecutionState,
  listExperimentHypotheses,
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
  listAgentRuns,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";
import { BrandBeliefs } from "../../components/beliefs/BrandBeliefs";
import { ExperimentOutcomeReview } from "../../components/experiments/ExperimentOutcomeReview";
import { ExperimentRunSettings } from "../../components/experiments/ExperimentRunSettings";
import { ExperimentHistoryPanel } from "../../components/experiments/ExperimentHistoryPanel";
import { ExperimentVariantRunItem } from "../../components/experiments/ExperimentVariantRunItem";
import { NextTestNotice } from "../../components/experiments/NextTestNotice";
import { OutcomeSnapshot } from "../../components/experiments/OutcomeSnapshot";
import { VariantCreationPanel } from "../../components/experiments/VariantCreationPanel";
import {
  BatteryGenerationReportNotice,
  type BatteryGenerationReport,
} from "../../components/experiments/BatteryGenerationReportNotice";
import { BatteryCreationPanel } from "../../components/experiments/BatteryCreationPanel";
import { AgentOperatorModePanel } from "../../components/experiments/AgentOperatorModePanel";
import { ExperimentSetupFlowPanel } from "../../components/experiments/ExperimentSetupFlowPanel";
import { LabLoopPanel } from "../../components/experiments/LabLoopPanel";
import {
  buildExperimentHref,
  buildRunsHref,
  buildSimulationHref,
  buildValidationHref,
} from "../../lib/routes";
import { buildTenantStorageKey } from "../../lib/storage";

function ExperimentsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAppUser();
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
  const runIdParam = searchParams.get("run_id")?.trim() || "";

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
  const [executionState, setExecutionState] = useState<ExperimentExecutionState | null>(
    null,
  );
  const [hypotheses, setHypotheses] = useState<ExperimentHypothesis[]>([]);
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
  const [experimentRunMode, setExperimentRunMode] = useState<
    "simulation" | "retrieval_backed"
  >("retrieval_backed");
  const [retrievalMaxResults, setRetrievalMaxResults] = useState("5");
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
  const [batteryUseLlm, setBatteryUseLlm] = useState(true);
  const [batterySeedFeatures, setBatterySeedFeatures] = useState("");
  const [batterySeedUseCases, setBatterySeedUseCases] = useState("");
  const [advancedOverridesOpen, setAdvancedOverridesOpen] = useState(false);
  const [batteryDetailsOpen, setBatteryDetailsOpen] = useState(true);
  const [setupFlowCollapsed, setSetupFlowCollapsed] = useState(true);
  const [historyCollapsed, setHistoryCollapsed] = useState(true);
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
  const [isGeneratingQueries, setIsGeneratingQueries] = useState(false);
  const [isCreatingVariant, setIsCreatingVariant] = useState(false);
  const [isCreatingLoopCandidateVariant, setIsCreatingLoopCandidateVariant] =
    useState(false);
  const [variantSourceMode, setVariantSourceMode] = useState<
    "manual" | "simulation" | "loop_evidence" | "cold_start"
  >("manual");
  const [variantSourceManualOverride, setVariantSourceManualOverride] = useState(false);
  const [coldStartGenerationStrategy, setColdStartGenerationStrategy] = useState<
    "bottom_up" | "top_down" | "both"
  >("both");
  const [expandedVariantId, setExpandedVariantId] = useState<string | null>(null);
  const [expandedHypothesisId, setExpandedHypothesisId] = useState<string | null>(null);
  const [variantAdvancedOpen, setVariantAdvancedOpen] = useState(false);
  const [isSubmitting, setSubmitting] = useState(false);
  const [savingExperimentId, setSavingExperimentId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [batteryStatus, setBatteryStatus] = useState<string | null>(null);
  const [batteryGenerationReport, setBatteryGenerationReport] =
    useState<BatteryGenerationReport | null>(null);
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
  const [isCreatingSuggestedVariant, setIsCreatingSuggestedVariant] =
    useState(false);
  const [validationSummary, setValidationSummary] = useState<ValidationSummary | null>(
    null,
  );
  const [latestAgentRun, setLatestAgentRun] = useState<AgentRun | null>(null);
  const [jsonErrors, setJsonErrors] = useState({
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
  const runExperimentWithSelectedMode = useCallback(
    async (experimentId: string, variantId: string) => {
      const parsedRetrievalLimit = Number.parseInt(retrievalMaxResults, 10);
      const safeRetrievalLimit = Number.isFinite(parsedRetrievalLimit)
        ? Math.max(1, Math.min(10, parsedRetrievalLimit))
        : 5;
      return runExperiment(experimentId, variantId, userId, {
        execution_mode: experimentRunMode,
        retrieval_max_results: safeRetrievalLimit,
      });
    },
    [experimentRunMode, retrievalMaxResults, userId],
  );

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
    if (labMode !== "lab") return;
    setBatteryUseLlm(true);
    setExperimentRunMode("retrieval_backed");
  }, [labMode]);

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

  const runsWorkspaceHref = useMemo(() => {
    return buildRunsHref({
      experimentId: selectedExperimentId,
      runId: runIdParam || null,
    });
  }, [runIdParam, selectedExperimentId]);

  const experimentBackHref = useMemo(() => {
    if (!runIdParam) {
      return "/lab";
    }
    return buildRunsHref({ experimentId: selectedExperimentId, runId: runIdParam });
  }, [runIdParam, selectedExperimentId]);

  const validationHref = useMemo(() => {
    return buildValidationHref({
      experimentId: selectedExperimentId,
      runId: runIdParam || null,
    });
  }, [runIdParam, selectedExperimentId]);

  const simulationHref = useCallback(
    (simulationRunId: string) => {
      return buildSimulationHref(simulationRunId, { experimentId: selectedExperimentId });
    },
    [selectedExperimentId],
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
    void getExperimentExecutionState(selectedExperimentId, userId)
      .then((response) => {
        setExecutionState(response.state ?? null);
      })
      .catch(() => setExecutionState(null));
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
  }, [selectedExperimentId, selectedExperiment?.battery_id, userId]);

  useEffect(() => {
    if (!userId || !selectedExperimentId) {
      setLatestAgentRun(null);
      return;
    }
    void listAgentRuns(
      {
        experiment_id: selectedExperimentId,
        limit: 1,
      },
      userId,
    )
      .then((response) => {
        setLatestAgentRun((response.runs ?? [])[0] ?? null);
      })
      .catch(() => setLatestAgentRun(null));
  }, [selectedExperimentId, userId]);

  useEffect(() => {
    if (selectedExperimentId) return;
    if (!productId || !experimentForm.batteryId) return;
    const existing = [...experiments]
      .filter(
        (item) =>
          item.product_id === productId && item.battery_id === experimentForm.batteryId,
      )
      .sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""))[0];
    if (existing?.id) {
      setSelectedExperimentId(existing.id);
    }
  }, [experimentForm.batteryId, experiments, productId, selectedExperimentId]);

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
      } finally {
        setRunningVariantId(null);
      }
    },
    [refreshExecutionState, runExperimentWithSelectedMode, selectedExperimentId, userId],
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
      await refreshExecutionState(selectedExperimentId);
      setScheduleStatus("Backfill completed.");
    } catch (error) {
      setScheduleStatus("Backfill failed.");
    }
  }, [productId, refreshExecutionState, selectedExperimentId, userId]);

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

  const ensureExperimentContext = useCallback(async (): Promise<string | null> => {
    const batteryId = experimentForm.batteryId;
    if (!productId || !batteryId) {
      setFormError("Complete Step 1-2 first: select battery and save queries.");
      return null;
    }
    if (queries.length === 0) {
      setFormError("Save at least one battery query before creating variants.");
      return null;
    }
    if (selectedExperimentId) return selectedExperimentId;

    const existing = [...experiments]
      .filter(
        (item) => item.product_id === productId && item.battery_id === batteryId,
      )
      .sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""))[0];
    if (existing?.id) {
      setSelectedExperimentId(existing.id);
      await refreshExecutionState(existing.id);
      return existing.id;
    }

    const experimentName =
      selectedBattery?.name?.trim() ||
      `${productName?.trim() || "Product"} experiment`;
    const response = await createExperiment({
      name: experimentName,
      product_id: productId,
      brand_id: brandId ?? undefined,
      battery_id: batteryId,
      hypothesis: {},
      competitor_policy: {},
      status: "active",
      user_id: userId,
    });
    const refreshed = await listExperiments(userId, productId ?? undefined);
    setExperiments(refreshed.experiments ?? []);
    setSelectedExperimentId(response.experiment.id);
    await refreshExecutionState(response.experiment.id);
    setExperimentStatus("Experiment context initialized automatically.");
    return response.experiment.id;
  }, [
    brandId,
    experimentForm.batteryId,
    experiments,
    productId,
    productName,
    queries.length,
    refreshExecutionState,
    selectedBattery?.name,
    selectedExperimentId,
    userId,
  ]);

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

  const handleCreateVariant = useCallback(async () => {
    if (jsonErrors.variantPayload) return;
    setFormError(null);
    setSubmitting(true);
    setIsCreatingVariant(true);
    try {
      const experimentId = await ensureExperimentContext();
      if (!experimentId) return;
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
      setIsCreatingVariant(false);
      setSubmitting(false);
    }
  }, [
    ensureExperimentContext,
    jsonErrors.variantPayload,
    refreshExecutionState,
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
  }, [ensureExperimentContext, userId]);

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
  }, [coldStartGenerationStrategy, ensureExperimentContext, userId]);

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
        label: candidate.label?.trim() || "Hypothesis (variant)",
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
    buildLoopCandidatePayload,
    ensureExperimentContext,
    loopGeneratedVariants,
    refreshExecutionState,
    selectedLoopCandidateIndex,
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
        label: candidate.label?.trim() || "Hypothesis (variant)",
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
    buildLoopCandidatePayload,
    ensureExperimentContext,
    loopGeneratedVariants,
    refreshExecutionState,
    selectedLoopCandidateIndex,
    runExperimentWithSelectedMode,
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
      await runExperimentWithSelectedMode(selectedExperimentId, nextTest.variant_id);
      const [runsResponse, metricsResponse] = await Promise.all([
        listExperimentRuns(selectedExperimentId, userId),
        listExperimentMetrics(selectedExperimentId, userId),
      ]);
      setRuns(runsResponse.runs ?? []);
      setMetrics(metricsResponse.metrics ?? []);
      await refreshExecutionState(selectedExperimentId);
      setNextTestStatus("Recommended variant run completed.");
    } finally {
      setRunningVariantId(null);
    }
  }, [nextTest?.variant_id, refreshExecutionState, runExperimentWithSelectedMode, selectedExperimentId, userId]);

  const handleCreateSuggestedVariant = useCallback(async () => {
    if (!selectedExperimentId || !nextTest || nextTest.action !== "create_variant") {
      return;
    }
    setFormError(null);
    setIsCreatingSuggestedVariant(true);
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
      await refreshExecutionState(selectedExperimentId);
      if (labMode === "lab") {
        await runExperimentWithSelectedMode(selectedExperimentId, response.variant.id);
        const [runsResponse, metricsResponse] = await Promise.all([
          listExperimentRuns(selectedExperimentId, userId),
          listExperimentMetrics(selectedExperimentId, userId),
        ]);
        setRuns(runsResponse.runs ?? []);
        setMetrics(metricsResponse.metrics ?? []);
        await refreshExecutionState(selectedExperimentId);
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
      setIsCreatingSuggestedVariant(false);
    }
  }, [labMode, nextTest, refreshExecutionState, runExperimentWithSelectedMode, selectedExperimentId, userId]);

  const handleCreateVariantFromRecommendation = useCallback(
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
        setIsCreatingSuggestedVariant(false);
      }
    },
    [labMode, refreshExecutionState, runExperimentWithSelectedMode, selectedExperimentId, userId],
  );

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
    [labMode, refreshExecutionState, runExperimentWithSelectedMode, selectedExperimentId, userId],
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
    const snapshotVersion =
      typeof latestRunEntry?.snapshot_version === "number"
        ? latestRunEntry.snapshot_version
        : typeof selectedExperiment?.protocol_snapshot_version === "number"
          ? selectedExperiment.protocol_snapshot_version
          : null;
    return {
      runVariantLabel,
      runQueryLabel,
      runCreatedAt: latestRunEntry?.created_at ?? null,
      winRate,
      avgScore,
      validationState,
      snapshotVersion,
    };
  }, [
    hasValidationSignals,
    metrics,
    queryMap,
    runs,
    selectedExperiment?.protocol_snapshot_version,
    validationSummary?.verified_runs,
    variants,
  ]);

  const currentProtocolSnapshotVersion = useMemo(() => {
    if (typeof selectedExperiment?.protocol_snapshot_version === "number") {
      return selectedExperiment.protocol_snapshot_version;
    }
    const detail = executionState?.phases?.retrieval_snapshots_ready?.detail;
    if (typeof detail !== "string") return null;
    const match = detail.match(/snapshot v(\d+)/i);
    if (!match) return null;
    const parsed = Number.parseInt(match[1] || "", 10);
    return Number.isFinite(parsed) ? parsed : null;
  }, [executionState?.phases?.retrieval_snapshots_ready?.detail, selectedExperiment?.protocol_snapshot_version]);

  const hypothesisLabelById = useMemo(() => {
    const map = new Map<string, string>();
    hypotheses.forEach((hypothesis, index) => {
      const statement = (hypothesis.statement ?? {}) as Record<string, unknown>;
      const explicitName =
        typeof statement.name === "string" && statement.name.trim()
          ? statement.name.trim()
          : null;
      const ifText =
        typeof statement.if === "string" && statement.if.trim()
          ? statement.if.trim()
          : null;
      const forText =
        typeof statement.for === "string" && statement.for.trim()
          ? statement.for.trim()
          : null;
      let label = explicitName ?? "";
      if (!label && ifText) {
        label = forText ? `${ifText} (${forText})` : ifText;
      }
      if (!label) {
        label = `Hypothesis ${index + 1}`;
      }
      if (label.length > 72) {
        label = `${label.slice(0, 69)}...`;
      }
      map.set(hypothesis.id, label);
    });
    return map;
  }, [hypotheses]);

  const hypothesisStatementById = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>();
    hypotheses.forEach((hypothesis) => {
      map.set(
        hypothesis.id,
        ((hypothesis.statement ?? {}) as Record<string, unknown>) || {},
      );
    });
    return map;
  }, [hypotheses]);

  const experimentFlowSteps = useMemo(() => {
    const phases = executionState?.phases ?? {};
    const phaseDone = (name: string, fallback: boolean) =>
      typeof phases[name]?.done === "boolean" ? Boolean(phases[name]?.done) : fallback;
    const batteryReady = phaseDone(
      "battery_ready",
      Boolean(selectedExperiment?.battery_id || experimentForm.batteryId),
    );
    const retrievalSnapshotsReady = phaseDone("retrieval_snapshots_ready", false);
    const baselineScored = phaseDone("baseline_scored", false);
    const hypothesesReady = phaseDone(
      "hypotheses_ready",
      Boolean(selectedExperiment?.hypothesis),
    );
    const variantsReady = phaseDone("variants_ready", variants.length > 0);
    const runCompleted = phaseDone(
      "experiment_run_completed",
      runs.length > 0 || Boolean(selectedExperiment?.last_run_at),
    );
    const validated = phaseDone("validation_completed", hasValidationSignals);
    const posteriorUpdated = phaseDone(
      "posterior_updated",
      loopGeneratedVariants.length > 0 ||
        Boolean(nextTest) ||
        recommendations.length > 0,
    );
    return [
      { id: 1, label: "battery_ready", done: batteryReady },
      { id: 2, label: "retrieval_snapshots_ready", done: retrievalSnapshotsReady },
      { id: 3, label: "baseline_scored", done: baselineScored },
      { id: 4, label: "hypotheses_ready", done: hypothesesReady },
      { id: 5, label: "variants_ready", done: variantsReady },
      { id: 6, label: "experiment_run_completed", done: runCompleted },
      { id: 7, label: "validation_completed", done: validated },
      { id: 8, label: "posterior_updated", done: posteriorUpdated },
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
    executionState?.phases,
    selectedExperiment?.battery_id,
    selectedExperiment?.last_run_at,
    selectedExperimentId,
    variants.length,
  ]);

  const labFlowSteps = useMemo(() => {
    return experimentFlowSteps;
  }, [experimentFlowSteps]);

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
  const addVariantDisabledReason = isSubmitting
    ? "Please wait for the current action to finish."
    : !experimentForm.batteryId
      ? "Select a battery first."
      : queries.length === 0
        ? "Generate and save battery queries first."
      : jsonErrors.variantPayload
        ? "Fix invalid payload JSON."
        : null;
  const batteryReadyForRun =
    typeof executionState?.phases?.battery_ready?.done === "boolean"
      ? Boolean(executionState?.phases?.battery_ready?.done)
      : Boolean((selectedExperiment?.battery_id || experimentForm.batteryId) && queries.length > 0);
  const variantsReadyForRun =
    typeof executionState?.phases?.variants_ready?.done === "boolean"
      ? Boolean(executionState?.phases?.variants_ready?.done)
      : variants.length >= 2;
  const canRunVariantTests = Boolean(
    selectedExperimentId &&
      batteryReadyForRun &&
      variantsReadyForRun &&
      (selectedExperiment?.battery_id || experimentForm.batteryId),
  ) && queries.length > 0;
  const runVariantDisabledReason = !selectedExperimentId
    ? "Create or select an experiment first."
    : !batteryReadyForRun
      ? "Complete Step 1-2 first: battery must have enabled saved queries."
    : !variantsReadyForRun
      ? "Create at least baseline + hypothesis variants first."
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
    const hasBatteryAndQueries = Boolean(experimentForm.batteryId) && queries.length > 0;
    if (!hasBatteryAndQueries && setupFlowCollapsed) {
      return {
        label: "Expand setup and start Step 1",
        helper: "Start by creating a battery and generating queries.",
        action: "expand_setup" as const,
      };
    }
    if (!hasBatteryAndQueries) {
      return {
        label: "Finish battery setup",
        helper: "Create/select battery, generate queries, and save enabled queries.",
        action: "scroll_setup" as const,
      };
    }
    if (!selectedExperimentId) {
      return {
        label: "Continue to variants (auto context)",
        helper: "Experiment context auto-initializes when you generate or add a variant.",
        action: "scroll_variants" as const,
      };
    }
    if (!executionState?.phases?.retrieval_snapshots_ready?.done) {
      return {
        label: "Run retrieval snapshots (Step 2)",
        helper: "Run baseline/control variant to collect retrieval snapshots.",
        action: "run_first_variant" as const,
      };
    }
    if (variants.length === 0) {
      return {
        label: "Create variants (Step 5)",
        helper: "Generate copy variants from retrieval evidence and hypotheses.",
        action: "scroll_variants" as const,
      };
    }
    if (!executionState?.phases?.experiment_run_completed?.done) {
      return {
        label: "Complete experiment run (Step 6)",
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
  }, [
    executionState?.phases,
    experimentForm.batteryId,
    hasValidationSignals,
    queries.length,
    selectedExperimentId,
    setupFlowCollapsed,
    variants,
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
        router.push(validationHref);
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
    validationHref,
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
        onNewConversation={() => router.push("/lab")}
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
          router.push(simulationHref(run.id));
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(buildExperimentHref(experiment.id, { runId: runIdParam || null }));
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
            onBack={() => router.push(experimentBackHref)}
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
            {runIdParam ? (
              <section className="panel__notice panel__notice--info">
                <strong>Run context preserved:</strong> this experiment view was opened from run{" "}
                <span className="panel__badge panel__badge--secondary">{runIdParam.slice(0, 8)}</span>.
                <div className="panel__actions">
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={() => router.push(experimentBackHref)}
                  >
                    Return to run
                  </button>
                </div>
              </section>
            ) : null}
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
            <LabLoopPanel
              labMode={labMode}
              selectedExperimentId={selectedExperimentId}
              batteryLinked={Boolean(selectedExperiment?.battery_id)}
              variantCount={variants.length}
              runCount={runs.length}
              metricCount={metrics.length}
              beliefCount={beliefCount}
              labAutoRunEnabled={labAutoRunEnabled}
              showManualControls={showManualControls}
              currentFlowStep={currentFlowStep}
              activeFlowSteps={activeFlowSteps}
              labLoopSteps={labLoopSteps}
              lastRun={lastRun}
              latestBelief={latestBelief}
              latestBeliefSummary={latestBeliefSummary}
              nextFlowAction={nextFlowAction}
              showValidationCheckpoint={
                labMode === "lab" && runs.length > 0 && !hasValidationSignals
              }
              onLabAutoRunEnabledChange={setLabAutoRunEnabled}
              onShowManualControlsChange={setLabShowManualControls}
              onSwitchToManual={() => {
                setLabMode("manual");
                setLabShowManualControls(true);
                setExperimentStatus(
                  "Switched to Manual mode for explicit control over each step.",
                );
              }}
              onOpenBeliefsTimeline={handleOpenBeliefsTimeline}
              onUseLatestBelief={handleUseLatestBelief}
              onRunNextFlowAction={handleRunNextFlowAction}
              onOpenValidation={() => router.push(validationHref)}
            />
            <AgentOperatorModePanel
              latestAgentRun={latestAgentRun}
              hasSelectedExperiment={Boolean(selectedExperimentId)}
              onOpenRuns={() => router.push(runsWorkspaceHref)}
            />
          {formError ? (
            <div className="panel__notice panel__notice--error">{formError}</div>
          ) : null}
          <ExperimentSetupFlowPanel
            labMode={labMode}
            collapsed={setupFlowCollapsed}
            hasProduct={Boolean(productId)}
            protocolSnapshotVersion={currentProtocolSnapshotVersion}
            hypothesesReady={Boolean(executionState?.phases?.hypotheses_ready?.done)}
            onCollapsedChange={setSetupFlowCollapsed}
          >
              <div className="panel__form">
                {labMode === "lab" && !showManualControls ? (
                  <section className="panel__notice panel__notice--info">
                    <strong>Lab setup path:</strong> Keep setup explicit. Build battery, generate queries, and save them before running experiments.
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
                <BatteryCreationPanel
                  status={batteryStatus}
                  form={batteryForm}
                  useLlm={batteryUseLlm}
                  isSubmitting={isSubmitting}
                  hasBottomUpMetadata={hasBottomUpMetadata}
                  advancedOverridesOpen={advancedOverridesOpen}
                  seedQueries={batterySeedQueries}
                  seedFeatures={batterySeedFeatures}
                  seedUseCases={batterySeedUseCases}
                  onFormChange={setBatteryForm}
                  onUseLlmChange={setBatteryUseLlm}
                  onAdvancedOverridesOpenChange={setAdvancedOverridesOpen}
                  onSeedQueriesChange={setBatterySeedQueries}
                  onSeedFeaturesChange={setBatterySeedFeatures}
                  onSeedUseCasesChange={setBatterySeedUseCases}
                  onCreateBattery={handleCreateBattery}
                />
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
                  {isGeneratingQueries ? (
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
                  <BatteryGenerationReportNotice
                    report={batteryGenerationReport}
                    onOpenAdmin={() => router.push("/admin")}
                  />
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
                <p className="panel__subheading">Experiment context</p>
                <p className="panel__step-helper">
                  Experiment records are now initialized automatically when you start Step 4.
                </p>
                {experimentStatus ? <p className="panel__success">{experimentStatus}</p> : null}
              </div>
          </ExperimentSetupFlowPanel>

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
                      disabled={
                        !experimentForm.batteryId ||
                        queries.length === 0 ||
                        isGeneratingLoopVariant
                      }
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
                      {isCreatingLoopCandidateVariant
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
              <VariantCreationPanel
                variantSourceMode={variantSourceMode}
                setVariantSourceMode={setVariantSourceMode}
                setVariantSourceManualOverride={setVariantSourceManualOverride}
                recommendedVariantSource={recommendedVariantSource}
                recommendedVariantSourceReason={recommendedVariantSourceReason}
                variantSourceManualOverride={variantSourceManualOverride}
                variantForm={variantForm}
                setVariantForm={setVariantForm}
                selectedSimulationRevisionId={selectedSimulationRevisionId}
                setSelectedSimulationRevisionId={setSelectedSimulationRevisionId}
                simulationRevisions={simulationRevisions}
                handleUseSimulationRevision={handleUseSimulationRevision}
                simulationRevisionStatus={simulationRevisionStatus}
                loopGeneratedVariants={loopGeneratedVariants}
                selectedLoopCandidateIndex={selectedLoopCandidateIndex}
                setSelectedLoopCandidateIndex={setSelectedLoopCandidateIndex}
                handleGenerateLoopVariants={handleGenerateLoopVariants}
                handleUseGeneratedLoopVariant={handleUseGeneratedLoopVariant}
                handleCreateVariantFromLoopCandidate={handleCreateVariantFromLoopCandidate}
                loopGenerationStatus={loopGenerationStatus}
                loopEvidenceAdvisory={loopEvidenceAdvisory}
                coldStartGenerationStrategy={coldStartGenerationStrategy}
                setColdStartGenerationStrategy={setColdStartGenerationStrategy}
                handleGenerateColdStartVariants={handleGenerateColdStartVariants}
                variantSecondaryActionsOpen={variantSecondaryActionsOpen}
                setVariantSecondaryActionsOpen={setVariantSecondaryActionsOpen}
                variantAdvancedOpen={variantAdvancedOpen}
                setVariantAdvancedOpen={setVariantAdvancedOpen}
                jsonErrorVariantPayload={jsonErrors.variantPayload}
                addVariantDisabledReason={addVariantDisabledReason}
                handleCreateVariant={handleCreateVariant}
                labMode={labMode}
                setLabShowManualControls={setLabShowManualControls}
                isSubmitting={isSubmitting}
                isGeneratingLoopVariant={isGeneratingLoopVariant}
                variantGenerationRequestType={variantGenerationRequestType}
                isCreatingVariant={isCreatingVariant}
                isCreatingLoopCandidateVariant={isCreatingLoopCandidateVariant}
                canGenerateCandidates={
                  Boolean(experimentForm.batteryId) && queries.length > 0
                }
              />
                </>
              )}
              <p className="panel__subheading">Step 5 · Run experiment across battery queries</p>
              <p className="panel__step-helper">
                Runs in retrieval-backed mode use frozen protocol snapshots to keep variant comparisons fair.
              </p>
              <ExperimentRunSettings
                runMode={experimentRunMode}
                retrievalMaxResults={retrievalMaxResults}
                currentProtocolSnapshotVersion={currentProtocolSnapshotVersion}
                runVariantDisabledReason={runVariantDisabledReason}
                onRunModeChange={setExperimentRunMode}
                onRetrievalMaxResultsChange={setRetrievalMaxResults}
              />
              {variants.length === 0 ? (
                <p className="panel__empty">Add variants to run experiments.</p>
              ) : (
                <ul className="panel__list">
                  {variants.map((variant) => {
                    const resolvedDescription = resolveVariantDescription(variant);
                    const hypothesisId = variant.hypothesis_id ?? null;
                    const tested = metricsByVariant.has(variant.id);
                    const metricValues = tested
                      ? (((metricsByVariant.get(variant.id)?.metrics ?? {}) as Record<
                          string,
                          unknown
                        >) ?? null)
                      : null;
                    return (
                      <li key={variant.id}>
                        <ExperimentVariantRunItem
                          variant={variant}
                          tested={tested}
                          hypothesisLabel={
                            hypothesisId
                              ? hypothesisLabelById.get(hypothesisId) ?? "Hypothesis-linked"
                              : "Hypothesis-linked"
                          }
                          hypothesisStatement={
                            hypothesisId
                              ? (hypothesisStatementById.get(hypothesisId) ?? null)
                              : null
                          }
                          hypothesisExpanded={
                            Boolean(hypothesisId) && expandedHypothesisId === hypothesisId
                          }
                          copyExpanded={expandedVariantId === variant.id}
                          resolvedDescription={resolvedDescription}
                          metricValues={metricValues}
                          runButtonProminent={!(labMode === "lab" && !showManualControls)}
                          running={runningVariantId === variant.id}
                          canRun={canRunVariantTests}
                          renderMetricValue={renderMetricValue}
                          onToggleHypothesis={() =>
                            setExpandedHypothesisId((current) =>
                              current === hypothesisId ? null : hypothesisId,
                            )
                          }
                          onToggleCopy={() =>
                            setExpandedVariantId((current) =>
                              current === variant.id ? null : variant.id,
                            )
                          }
                          onRun={() => handleRunVariant(variant.id)}
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
              <NextTestNotice
                nextTest={nextTest}
                canRunVariantTests={canRunVariantTests}
                runningVariantId={runningVariantId}
                isSubmitting={isSubmitting}
                isCreatingSuggestedVariant={isCreatingSuggestedVariant}
                onRunRecommended={handleRunRecommended}
                onCreateSuggestedVariant={handleCreateSuggestedVariant}
              />
              {nextTestStatus ? (
                <p className="panel__success">{nextTestStatus}</p>
              ) : null}
              <OutcomeSnapshot
                snapshot={outcomeSnapshot}
                hasValidationSignals={hasValidationSignals}
                onOpenValidation={() => router.push(validationHref)}
              />
              <ExperimentOutcomeReview
                latestMetric={latestMetric}
                experimentGapSummary={experimentGapSummary}
                renderMetricValue={renderMetricValue}
              />
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
                            {isCreatingSuggestedVariant ? (
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

          <ExperimentHistoryPanel
            experiments={experiments}
            runs={runs}
            metricsCount={metrics.length}
            variantCount={variants.length}
            historyCollapsed={historyCollapsed}
            selectedExperimentId={selectedExperimentId}
            experimentSnapshots={experimentSnapshots}
            batteries={batteries}
            savingExperimentId={savingExperimentId}
            queryMap={queryMap}
            runGapDetails={runGapDetails}
            hypothesisLabelById={hypothesisLabelById}
            hypothesisStatementById={hypothesisStatementById}
            expandedHypothesisId={expandedHypothesisId}
            runsSectionRef={runsSectionRef}
            formatTimestamp={formatTimestamp}
            onToggleHistory={() => setHistoryCollapsed((open) => !open)}
            onSelectExperiment={setSelectedExperimentId}
            onSaveExperimentDraft={handleSaveExperimentDraft}
            onScrollVariants={() =>
              variantsSectionRef.current?.scrollIntoView({
                behavior: "smooth",
              })
            }
            onScrollRuns={() =>
              runsSectionRef.current?.scrollIntoView({
                behavior: "smooth",
              })
            }
            onScrollMetrics={() =>
              metricsSectionRef.current?.scrollIntoView({
                behavior: "smooth",
              })
            }
            onToggleHypothesis={setExpandedHypothesisId}
            onDeleteRun={(runId) => {
              void handleDeleteExperimentRun(runId);
            }}
          />

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
                onClick={() => router.push(validationHref)}
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

export default function ExperimentsPage() {
  return (
    <Suspense fallback={null}>
      <ExperimentsPageContent />
    </Suspense>
  );
}
