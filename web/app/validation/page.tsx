"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAppUser } from "../../lib/auth";
import type {
  Experiment,
  ExperimentMetric,
  ExperimentRun,
  ExperimentVariant,
  ValidationSummary,
  QueryBattery,
  QueryBatteryQuery,
  SimulationRunSummary,
  CopyRevision,
  ValidationJob,
  ValidationResult,
  LLMConfigSummaryResponse,
} from "../../lib/types";
import {
  createValidationJob,
  runValidationJob,
  submitValidationExternal,
  startValidationProviderRun,
  listExperiments,
  listSimulationRuns,
  getSimulationRun,
  listExperimentRuns,
  listExperimentMetrics,
  listExperimentVariants,
  listBatteries,
  listBatteryQueries,
  getLlmConfig,
  listCopyRevisions,
  getCopyRevision,
  publishCopyRevision,
  getExperimentValidationSummary,
  getBrandPredictionAccuracy,
  logExperimentValidation,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";
import { ValidationFlowHeader } from "../../components/validation/ValidationFlowHeader";
import {
  buildExperimentHref,
  buildRunsHref,
  buildSimulationHref,
} from "../../lib/routes";

type EntityType = "experiment_run" | "simulation_run" | "battery" | "copy_revision";
type ProviderType = "openai" | "gemini" | "anthropic" | "openrouter";
type ModeType =
  | "in_app"
  | "external"
  | "in_app_byok"
  | "provider_openai_mcp"
  | "provider_gemini_function"
  | "manual_fallback";

type ProviderRunLaunchInfo = {
  launch_url?: string | null;
  setup_url?: string | null;
  setup_required?: boolean | null;
  instructions?: string | null;
  provider_run_id?: string | null;
};

function isManualFallbackMode(mode: ModeType | string | null | undefined): boolean {
  return mode === "external" || mode === "manual_fallback";
}

function isInAppByokMode(mode: ModeType | string | null | undefined): boolean {
  return mode === "in_app" || mode === "in_app_byok";
}

function isProviderIntegrationMode(mode: ModeType | string | null | undefined): boolean {
  return mode === "provider_openai_mcp" || mode === "provider_gemini_function";
}

function formatSetupStatus(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "Unknown";
  return value ? "Setup needed" : "Ready";
}

function formatReturnStatus(value: boolean | null | undefined): string {
  return value ? "Result returned" : "Waiting for result";
}

function formatDisplayToken(value: string | null | undefined, fallback: string): string {
  const text = String(value || fallback)
    .replace(/[._-]+/g, " ")
    .trim();
  if (!text) return fallback;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatCopyRevisionOption(revision: CopyRevision): string {
  const source = formatDisplayToken(revision.source_type, "Copy");
  const status = formatDisplayToken(revision.status, "Draft");
  const reference = revision.id.replace(/^copy-revision[-_]?/, "").slice(0, 8);
  return `${source} revision · ${status} · Ref ${reference}`;
}

type ValidationNextAction =
  | "configure_provider"
  | "select_synthetic_item"
  | "create_synthetic"
  | "complete_provider_run"
  | "submit_external_result"
  | "log_observed"
  | "open_experiments";

const DEFAULT_MODELS: Record<ProviderType, string> = {
  openai: "gpt-5.2-2025-12-11",
  gemini: "gemini-3-flash-preview",
  anthropic: "claude-sonnet-4-5-20250929",
  openrouter: "openai/gpt-oss-120b",
};

const MODEL_OPTIONS: Record<ProviderType, string[]> = {
  openai: ["gpt-5.2-2025-12-11"],
  gemini: ["gemini-3-flash-preview"],
  anthropic: ["claude-sonnet-4-5-20250929"],
  openrouter: ["openai/gpt-oss-120b"],
};

const OBSERVED_PLATFORM_LABELS: Record<ProviderType, string> = {
  openai: "ChatGPT (OpenAI)",
  gemini: "Gemini",
  anthropic: "Claude (Anthropic)",
  openrouter: "OpenRouter",
};

function normalizeProvider(value: string | null | undefined): ProviderType | null {
  if (!value) return null;
  if (value === "claude") return "anthropic";
  if (value === "openai") return "openai";
  if (value === "gemini") return "gemini";
  if (value === "anthropic") return "anthropic";
  if (value === "openrouter") return "openrouter";
  return null;
}

function getPreferredProvider(
  config: LLMConfigSummaryResponse | null,
): ProviderType | null {
  if (!config) return null;
  const active = normalizeProvider(config.active_provider);
  if (active) return active;
  const configured = (Object.keys(OBSERVED_PLATFORM_LABELS) as ProviderType[]).find(
    (name) => {
      const entry = config.providers?.[name];
      return Boolean(entry?.validation_configured ?? entry?.configured);
    },
  );
  return configured ?? null;
}

function observedSummaryValue(
  summary: ValidationSummary | null,
  nextKey: keyof ValidationSummary,
  legacyKey: keyof ValidationSummary,
) {
  if (!summary) return null;
  return (summary[nextKey] ?? summary[legacyKey] ?? null) as
    | number
    | boolean
    | null;
}

function ValidationPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAppUser();
  const userId = user?.id ?? null;
  const { clientId } = useTenant();
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [batteries, setBatteries] = useState<QueryBattery[]>([]);
  const [copyRevisions, setCopyRevisions] = useState<CopyRevision[]>([]);
  const [llmConfig, setLlmConfig] = useState<LLMConfigSummaryResponse | null>(null);
  const [llmConfigError, setLlmConfigError] = useState<string | null>(null);
  const [entityType, setEntityType] = useState<EntityType>("experiment_run");
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [provider, setProvider] = useState<ProviderType>("openai");
  const [mode, setMode] = useState<ModeType>("in_app_byok");
  const [model, setModel] = useState<string>("");
  const [job, setJob] = useState<ValidationJob | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [externalJson, setExternalJson] = useState("");
  const [externalRaw, setExternalRaw] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const [manualExperimentId, setManualExperimentId] = useState<string>("");
  const [manualVariants, setManualVariants] = useState<ExperimentVariant[]>([]);
  const [manualMetrics, setManualMetrics] = useState<ExperimentMetric[]>([]);
  const [manualSummary, setManualSummary] = useState<ValidationSummary | null>(null);
  const [manualBrandSummary, setManualBrandSummary] = useState<ValidationSummary | null>(
    null,
  );
  const [manualStatus, setManualStatus] = useState<string | null>(null);
  const [manualError, setManualError] = useState<string | null>(null);
  const [providerLaunchInfo, setProviderLaunchInfo] =
    useState<ProviderRunLaunchInfo | null>(null);
  const [queryPrefillApplied, setQueryPrefillApplied] = useState(false);
  const experimentIdParam = searchParams.get("experiment_id")?.trim() || "";
  const runIdParam = searchParams.get("run_id")?.trim() || "";

  const experimentsHref = useMemo(() => {
    return buildExperimentHref(manualExperimentId || experimentIdParam || null, {
      runId: runIdParam || null,
    });
  }, [experimentIdParam, manualExperimentId, runIdParam]);

  const validationBackHref = useMemo(() => {
    if (!runIdParam) {
      return experimentsHref;
    }
    return buildRunsHref({
      experimentId: manualExperimentId || experimentIdParam || null,
      runId: runIdParam,
    });
  }, [experimentIdParam, experimentsHref, manualExperimentId, runIdParam]);

  const simulationHref = useCallback(
    (simulationRunId: string) => {
      return buildSimulationHref(simulationRunId, {
        experimentId: manualExperimentId || experimentIdParam || null,
      });
    },
    [experimentIdParam, manualExperimentId],
  );

  const renderMetricValue = useCallback((value: unknown, fallback = "—") => {
    if (value === null || value === undefined) return fallback;
    if (typeof value === "number") return Number.isFinite(value) ? String(value) : fallback;
    if (typeof value === "string") return value;
    if (typeof value === "boolean") return value ? "true" : "false";
    return fallback;
  }, []);
  const [manualForm, setManualForm] = useState({
    variantId: "",
    platform: "openrouter",
    queryText: "",
    observedProducts: "",
    observedWinnerVariantId: "",
    observedPosition: "",
    notes: "",
  });

  useEffect(() => {
    if (!userId) return;
    void listExperiments(userId).then((response) =>
      setExperiments(response.experiments ?? []),
    );
    void listSimulationRuns(userId).then((response) =>
      setSimulationRuns(response.runs ?? []),
    );
    void listBatteries(userId).then((response) =>
      setBatteries(response.batteries ?? []),
    );
    void listCopyRevisions({ user_id: userId, limit: 200 }).then((response) =>
      setCopyRevisions(response.revisions ?? []),
    );
  }, [userId, clientId]);

  useEffect(() => {
    if (!experiments.length) {
      setManualExperimentId("");
      return;
    }
    if (manualExperimentId) return;
    setManualExperimentId(experiments[0].id);
  }, [experiments, manualExperimentId]);

  useEffect(() => {
    if (queryPrefillApplied) return;
    if (!experimentIdParam || !experiments.length) return;
    const exists = experiments.some((exp) => exp.id === experimentIdParam);
    if (!exists) {
      setQueryPrefillApplied(true);
      return;
    }
    setManualExperimentId(experimentIdParam);
    setEntityType("experiment_run");
    setSelectedEntityId(experimentIdParam);
    setQueryPrefillApplied(true);
  }, [experimentIdParam, experiments, queryPrefillApplied]);

  useEffect(() => {
    if (!manualExperimentId || !userId) {
      setManualVariants([]);
      setManualMetrics([]);
      setManualSummary(null);
      setManualBrandSummary(null);
      return;
    }
    const selectedExperiment = experiments.find((exp) => exp.id === manualExperimentId);
    void listExperimentVariants(manualExperimentId, userId).then((response) => {
      const variants = response.variants ?? [];
      setManualVariants(variants);
      setManualForm((prev) => ({
        ...prev,
        variantId: prev.variantId || variants[0]?.id || "",
      }));
    });
    void listExperimentMetrics(manualExperimentId, userId).then((response) => {
      setManualMetrics(response.metrics ?? []);
    });
    void getExperimentValidationSummary(manualExperimentId, userId).then((response) =>
      setManualSummary(response.summary),
    );
    if (selectedExperiment?.brand_id) {
      void getBrandPredictionAccuracy(selectedExperiment.brand_id, userId).then(
        (response) => setManualBrandSummary(response.summary),
      );
    } else {
      setManualBrandSummary(null);
    }
  }, [experiments, manualExperimentId, userId]);

  const manualMetricsByVariant = useMemo(() => {
    const map = new Map<string, ExperimentMetric>();
    manualMetrics.forEach((metric) => {
      if (!metric.variant_id) return;
      const existing = map.get(metric.variant_id);
      if (!existing || (metric.created_at || "") > (existing.created_at || "")) {
        map.set(metric.variant_id, metric);
      }
    });
    return map;
  }, [manualMetrics]);

  const observedLogged = Number(
    observedSummaryValue(
      manualSummary,
      "observed_signals_logged",
      "total_logged",
    ) ?? 0,
  );
  const observedVerified = Number(
    observedSummaryValue(
      manualSummary,
      "observed_runs_verified",
      "verified_runs",
    ) ?? 0,
  );
  const observedAccuracyRaw = observedSummaryValue(
    manualSummary,
    "observed_accuracy",
    "accuracy",
  );
  const observedAccuracy = typeof observedAccuracyRaw === "number" ? observedAccuracyRaw : null;
  const observedProgress = Number(
    observedSummaryValue(
      manualSummary,
      "observed_progress",
      "progress",
    ) ?? 0,
  );
  const observedBrandAccuracyRaw = observedSummaryValue(
    manualBrandSummary,
    "observed_accuracy",
    "accuracy",
  );
  const observedBrandAccuracy =
    typeof observedBrandAccuracyRaw === "number" ? observedBrandAccuracyRaw : null;
  const observedBrandVerified = Number(
    observedSummaryValue(
      manualBrandSummary,
      "observed_runs_verified",
      "verified_runs",
    ) ?? 0,
  );
  const observedUnlockReadyRaw = observedSummaryValue(
    manualSummary,
    "observed_unlock_ready",
    "unlock_ready",
  );
  const observedUnlockReady =
    typeof observedUnlockReadyRaw === "boolean" ? observedUnlockReadyRaw : false;

  const validationFlowSteps = useMemo(() => {
    const providerReady = !llmConfigError;
    const syntheticReady = Boolean(result);
    const observedReady = observedLogged > 0;
    const comparisonReady = Boolean(manualExperimentId && manualVariants.length > 0);
    const decisionReady = syntheticReady && (observedReady || observedVerified > 0);
    return [
      { id: 1, label: "Configure provider defaults", done: providerReady },
      { id: 2, label: "Run synthetic validation", done: syntheticReady },
      { id: 3, label: "Log observed reality", done: observedReady },
      { id: 4, label: "Compare variant outcomes", done: comparisonReady },
      { id: 5, label: "Decide next experiment step", done: decisionReady },
    ];
  }, [
    llmConfigError,
    manualExperimentId,
    manualVariants.length,
    observedLogged,
    observedVerified,
    result,
  ]);

  const validationCurrentStep = useMemo(
    () => validationFlowSteps.find((step) => !step.done)?.id ?? 5,
    [validationFlowSteps],
  );

  const validationNextAction = useMemo(() => {
    if (llmConfigError) {
      return {
        action: "configure_provider" as ValidationNextAction,
        label: "Configure provider keys",
        helper:
          "Validation cannot run without a configured provider. Set API keys in Admin first.",
      };
    }
    if (!selectedEntityId) {
      return {
        action: "select_synthetic_item" as ValidationNextAction,
        label: "Select a validation item",
        helper:
          "Pick experiment, simulation, battery, or copy revision in Step 2 before creating a validation job.",
      };
    }
    if (!job && !result) {
      return {
        action: "create_synthetic" as ValidationNextAction,
        label: "Create synthetic validation",
        helper:
          "Run in-app judge validation to get a fast winner/score signal for this item.",
      };
    }
    if (isProviderIntegrationMode(mode) && job && !result) {
      return {
        action: "complete_provider_run" as ValidationNextAction,
        label: "Complete provider run",
        helper:
          "Finish validation in the provider UI. The result will be saved when it returns.",
      };
    }
    if (isManualFallbackMode(mode) && job && !result) {
      return {
        action: "submit_external_result" as ValidationNextAction,
        label: "Submit external result",
        helper:
          "Paste the provider result so this validation can be saved and tracked.",
      };
    }
    if (observedLogged === 0) {
      return {
        action: "log_observed" as ValidationNextAction,
        label: "Log observed reality signal",
        helper:
          "Add at least one real platform observation to ground synthetic validation with live evidence.",
      };
    }
    return {
      action: "open_experiments" as ValidationNextAction,
      label: "Return to Experiments (Step 8)",
      helper:
        "Use combined synthetic + observed validation evidence to generate the next variant.",
    };
  }, [job, llmConfigError, mode, observedLogged, result, selectedEntityId]);

  useEffect(() => {
    void getLlmConfig(userId ?? undefined)
      .then((response) => {
        setLlmConfig(response);
        setLlmConfigError(null);
        const preferred = getPreferredProvider(response);
        if (preferred) {
          setProvider(preferred);
          setManualForm((prev) => ({ ...prev, platform: preferred }));
        }
      })
      .catch((err) => {
        setLlmConfig(null);
        setLlmConfigError(err instanceof Error ? err.message : "Unavailable");
      });
  }, [userId]);

  useEffect(() => {
    const providerConfig = llmConfig?.providers?.[provider];
    const fallback =
      providerConfig?.validation_model ||
      providerConfig?.model ||
      DEFAULT_MODELS[provider];
    setModel(fallback);
  }, [llmConfig, provider]);

  const entityOptions = useMemo(() => {
    if (entityType === "experiment_run") {
      return experiments.map((exp) => ({
        id: exp.id,
        label: exp.name || "Experiment",
      }));
    }
    if (entityType === "simulation_run") {
      return simulationRuns.map((run) => ({
        id: run.id,
        label: run.query || "Simulation run",
      }));
    }
    if (entityType === "copy_revision") {
      return copyRevisions.map((revision) => ({
        id: revision.id,
        label: formatCopyRevisionOption(revision),
      }));
    }
    return batteries.map((battery) => ({
      id: battery.id,
      label: battery.name || "Battery",
    }));
  }, [batteries, copyRevisions, entityType, experiments, simulationRuns]);

  const winnerContext = useMemo(() => {
    if (!result?.winner_id || !job?.input_payload) return null;
    if (job.entity_type === "copy_revision") {
      const payload = job.input_payload as Record<string, unknown>;
      const revision =
        payload.revision && typeof payload.revision === "object"
          ? (payload.revision as Record<string, unknown>)
          : null;
      const winner = String(result.winner_id || "").toLowerCase();
      const winnerLabel =
        winner === "candidate"
          ? "Candidate copy"
          : winner === "control"
            ? "Control copy"
            : result.winner_id;
      const simulationRunId =
        revision && revision.source_type === "simulation"
          ? String(revision.source_id || "")
          : null;
      return {
        winnerLabel,
        experimentName: null,
        queryText: null,
        simulationRunId: simulationRunId || null,
      };
    }
    if (job.entity_type !== "experiment_run") return null;

    const payload = job.input_payload as Record<string, unknown>;
    const experiment =
      payload.experiment && typeof payload.experiment === "object"
        ? (payload.experiment as Record<string, unknown>)
        : null;
    const variants = Array.isArray(payload.variants)
      ? (payload.variants as Record<string, unknown>[])
      : [];
    const runs = Array.isArray(payload.runs)
      ? (payload.runs as Record<string, unknown>[])
      : [];

    const winnerId = String(result.winner_id);
    const winnerVariant = variants.find(
      (variant) => String(variant.id ?? "") === winnerId,
    );
    const winnerRuns = runs.filter(
      (run) => String(run.variant_id ?? "") === winnerId,
    );
    const linkedRun =
      winnerRuns.find(
        (run) =>
          typeof run.simulation_run_id === "string" && run.simulation_run_id.length > 0,
      ) ?? winnerRuns[0];

    const simulationRunId =
      linkedRun && typeof linkedRun.simulation_run_id === "string"
        ? linkedRun.simulation_run_id
        : null;
    const queryText =
      linkedRun && typeof linkedRun.query_text === "string"
        ? linkedRun.query_text
        : linkedRun && typeof linkedRun.query_id === "string"
          ? linkedRun.query_id
          : null;
    const experimentName =
      experiment && typeof experiment.name === "string" ? experiment.name : null;
    const winnerLabel =
      winnerVariant && typeof winnerVariant.label === "string"
        ? winnerVariant.label
        : winnerId;

    return {
      winnerLabel,
      experimentName,
      queryText,
      simulationRunId,
    };
  }, [job?.entity_type, job?.input_payload, result?.winner_id]);

  const observedPlatformOptions = useMemo(() => {
    const configured = (Object.keys(OBSERVED_PLATFORM_LABELS) as ProviderType[]).filter(
      (name) => {
        const entry = llmConfig?.providers?.[name];
        return Boolean(entry?.validation_configured ?? entry?.configured);
      },
    );
    if (configured.length > 0) {
      return configured.map((name) => ({
        value: name,
        label: OBSERVED_PLATFORM_LABELS[name],
      }));
    }
    return [
      { value: "openai", label: OBSERVED_PLATFORM_LABELS.openai },
      { value: "gemini", label: OBSERVED_PLATFORM_LABELS.gemini },
      { value: "anthropic", label: OBSERVED_PLATFORM_LABELS.anthropic },
      { value: "openrouter", label: OBSERVED_PLATFORM_LABELS.openrouter },
    ];
  }, [llmConfig]);

  const providerStatusItems = useMemo(
    () =>
      (
        [
          ["openai", "OPENAI_API_KEY"],
          ["gemini", "GEMINI_API_KEY"],
          ["anthropic", "ANTHROPIC_API_KEY"],
          ["openrouter", "OPENROUTER_API_KEY"],
        ] as const
      ).map(([name, envKey]) => {
        const entry = llmConfig?.providers?.[name];
        const configured = entry?.configured ?? false;
        const label = name === "anthropic" ? "claude" : name;
        const tooltip = configured
          ? `${label} is configured`
          : `Missing ${envKey}`;
        return { name, label, configured, isActive: entry?.is_active ?? false, tooltip };
      }),
    [llmConfig],
  );

  useEffect(() => {
    if (!observedPlatformOptions.length) return;
    const current = manualForm.platform;
    const exists = observedPlatformOptions.some((item) => item.value === current);
    if (exists) return;
    setManualForm((prev) => ({
      ...prev,
      platform: observedPlatformOptions[0].value,
    }));
  }, [manualForm.platform, observedPlatformOptions]);

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

  const buildPayload = useCallback(async () => {
    if (!userId || !selectedEntityId) return null;
    if (entityType === "simulation_run") {
      const detail = await getSimulationRun(selectedEntityId, userId);
      return {
        type: "simulation_run",
        run: detail.run,
      };
    }
    if (entityType === "experiment_run") {
      const experiment = experiments.find((item) => item.id === selectedEntityId);
      const [runsResponse, metricsResponse, variantsResponse] = await Promise.all([
        listExperimentRuns(selectedEntityId, userId),
        listExperimentMetrics(selectedEntityId, userId),
        listExperimentVariants(selectedEntityId, userId),
      ]);
      return {
        type: "experiment",
        experiment,
        runs: runsResponse.runs as ExperimentRun[],
        metrics: metricsResponse.metrics as ExperimentMetric[],
        variants: variantsResponse.variants as ExperimentVariant[],
      };
    }
    if (entityType === "copy_revision") {
      const revisionResponse = await getCopyRevision(selectedEntityId, userId);
      const revision = revisionResponse.revision;
      return {
        type: "copy_revision",
        revision,
        control: { id: "control", text: revision.base_description },
        candidate: { id: "candidate", text: revision.candidate_description },
        query_set:
          (revision.metadata?.query_set as string[] | undefined) ??
          (revision.metadata?.query ? [String(revision.metadata.query)] : []),
      };
    }
    const battery = batteries.find((item) => item.id === selectedEntityId);
    const queriesResponse = await listBatteryQueries(selectedEntityId, userId);
    return {
      type: "battery",
      battery,
      queries: queriesResponse.queries as QueryBatteryQuery[],
    };
  }, [batteries, entityType, experiments, selectedEntityId, userId]);

  const handleCreateJob = useCallback(async () => {
    if (!userId || !selectedEntityId) return;
    setSubmitting(true);
    setError(null);
    setStatus("Preparing validation payload...");
    try {
      const inputPayload = await buildPayload();
      if (!inputPayload) {
        setError("Missing payload data.");
        return;
      }
      const response = await createValidationJob(
        {
          entity_type: entityType,
          entity_id: selectedEntityId,
          provider,
          mode,
          model: model || null,
          input_payload: inputPayload,
        },
        userId,
      );
      setJob(response.job);
      setResult(response.result ?? null);
      if (isInAppByokMode(mode)) {
        setProviderLaunchInfo(null);
        setStatus("Running validation...");
        const runResponse = await runValidationJob(response.job.id, userId);
        setJob(runResponse.job);
        setResult(runResponse.result ?? null);
        setStatus("Validation complete.");
      } else if (isProviderIntegrationMode(mode)) {
        setStatus("Starting provider run...");
        const providerRun = await startValidationProviderRun(
          response.job.id,
          {},
          userId,
        );
        setJob(providerRun.job ?? response.job);
        setProviderLaunchInfo({
          launch_url: providerRun.launch_url ?? null,
          setup_url: providerRun.setup_url ?? null,
          setup_required: providerRun.setup_required ?? null,
          instructions: providerRun.instructions ?? null,
          provider_run_id: providerRun.provider_run_id ?? null,
        });
        if (providerRun.launch_url) {
          window.open(providerRun.launch_url, "_blank", "noopener,noreferrer");
          setStatus(
            providerRun.instructions ||
              "Provider run launched. Complete it in the provider UI so the result can be saved.",
          );
        } else {
          setStatus("Provider run initialized. Waiting for the result.");
        }
      } else {
        setStatus("Awaiting validation completion.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to validate.");
    } finally {
      setSubmitting(false);
      window.setTimeout(() => setStatus(null), 4000);
    }
  }, [buildPayload, entityType, mode, model, provider, selectedEntityId, userId]);

  useEffect(() => {
    if (mode === "provider_openai_mcp" && provider !== "openai") {
      setProvider("openai");
      setManualForm((prev) => ({ ...prev, platform: "openai" }));
      return;
    }
    if (mode === "provider_gemini_function" && provider !== "gemini") {
      setProvider("gemini");
      setManualForm((prev) => ({ ...prev, platform: "gemini" }));
    }
  }, [mode, provider]);

  useEffect(() => {
    if (!isProviderIntegrationMode(mode)) {
      setProviderLaunchInfo(null);
    }
  }, [mode]);

  const handleSubmitExternal = useCallback(async () => {
    if (!userId || !job) return;
    setSubmitting(true);
    setError(null);
    try {
      const parsed = JSON.parse(externalJson || "{}");
      const response = await submitValidationExternal(
        job.id,
        {
          provider,
          model: model || null,
          structured_result: parsed,
          raw_response: externalRaw || null,
        },
        userId,
      );
      setJob(response.job);
      setResult(response.result ?? null);
      setStatus("Validation stored.");
      setExternalJson("");
      setExternalRaw("");
    } catch (err) {
      setError(
        err instanceof SyntaxError
          ? "Invalid provider result format."
          : err instanceof Error
            ? err.message
            : "Invalid provider result format.",
      );
    } finally {
      setSubmitting(false);
      window.setTimeout(() => setStatus(null), 4000);
    }
  }, [externalJson, externalRaw, job, model, provider, userId]);

  const handlePublishCandidate = useCallback(async () => {
    if (!job || !result || !userId) return;
    if (job.entity_type !== "copy_revision") return;
    if (String(result.winner_id || "").toLowerCase() !== "candidate") return;
    await publishCopyRevision(job.entity_id, { user_id: userId });
    setStatus("Candidate copy published to product.");
    window.setTimeout(() => setStatus(null), 4000);
  }, [job, result, userId]);

  const handleLogObservedValidation = useCallback(async () => {
    if (!manualExperimentId || !userId) return;
    setManualStatus(null);
    setManualError(null);
    setSubmitting(true);
    try {
      const observedProducts = manualForm.observedProducts
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await logExperimentValidation(manualExperimentId, {
        variant_id: manualForm.variantId || undefined,
        platform: manualForm.platform || undefined,
        query_text: manualForm.queryText || undefined,
        observed_products: observedProducts,
        observed_winner_variant_id:
          manualForm.observedWinnerVariantId || undefined,
        observed_position: manualForm.observedPosition
          ? Number(manualForm.observedPosition)
          : undefined,
        notes: manualForm.notes || undefined,
        user_id: userId,
      });
      setManualSummary(response.summary);
      const selectedExperiment = experiments.find(
        (exp) => exp.id === manualExperimentId,
      );
      if (selectedExperiment?.brand_id) {
        const brandResponse = await getBrandPredictionAccuracy(
          selectedExperiment.brand_id,
          userId,
        );
        setManualBrandSummary(brandResponse.summary);
      }
      setManualStatus("Observed reality signal logged.");
      setManualForm((prev) => ({
        ...prev,
        queryText: "",
        observedProducts: "",
        observedWinnerVariantId: "",
        observedPosition: "",
        notes: "",
      }));
    } catch (err) {
      setManualError(
        err instanceof Error ? err.message : "Unable to log observed reality signal.",
      );
    } finally {
      setSubmitting(false);
      window.setTimeout(() => setManualStatus(null), 4000);
    }
  }, [experiments, manualExperimentId, manualForm, userId]);

  const handleRunValidationNextAction = useCallback(() => {
    switch (validationNextAction.action) {
      case "configure_provider":
        router.push("/admin");
        return;
      case "select_synthetic_item":
        setStatus("Select an item in Step 2 to create a synthetic validation job.");
        window.setTimeout(() => setStatus(null), 3000);
        return;
      case "create_synthetic":
        void handleCreateJob();
        return;
      case "submit_external_result":
        if (!externalJson.trim()) {
          setStatus("Add the provider result in Step 2 before submitting external results.");
          window.setTimeout(() => setStatus(null), 3000);
          return;
        }
        void handleSubmitExternal();
        return;
      case "complete_provider_run":
        if (job?.id) {
          void (async () => {
            try {
              const providerRun = await startValidationProviderRun(job.id, {}, userId);
              setProviderLaunchInfo({
                launch_url: providerRun.launch_url ?? null,
                setup_url: providerRun.setup_url ?? null,
                setup_required: providerRun.setup_required ?? null,
                instructions: providerRun.instructions ?? null,
                provider_run_id: providerRun.provider_run_id ?? null,
              });
              if (providerRun.launch_url) {
                window.open(providerRun.launch_url, "_blank", "noopener,noreferrer");
                setStatus(
                  providerRun.instructions ||
                    "Provider run opened. Complete it to return scored validation.",
                );
              } else {
                setStatus("Provider run is waiting for the result.");
              }
            } catch (err) {
              setError(err instanceof Error ? err.message : "Unable to start provider run.");
            } finally {
              window.setTimeout(() => setStatus(null), 4000);
            }
          })();
        }
        return;
      case "log_observed":
        void handleLogObservedValidation();
        return;
      case "open_experiments":
        router.push(experimentsHref);
        return;
      default:
        return;
    }
  }, [
    externalJson,
    handleCreateJob,
    handleLogObservedValidation,
    handleSubmitExternal,
    job?.id,
    router,
    userId,
    validationNextAction.action,
    experimentsHref,
  ]);

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/lab")}
        sessions={[]}
        activeSessionId={null}
        onSelectSession={() => {}}
        onDeleteSession={() => {}}
        onOpenHistory={() => setHistoryOpen(true)}
      />
      <HistoryDrawer
        isOpen={isHistoryOpen}
        isClosing={isHistoryClosing}
        sessions={[]}
        simulations={simulationRuns}
        experiments={experiments}
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={() => {}}
        onSelectSimulation={(run) => {
          router.push(
            buildSimulationHref(run.id, {
              experimentId: manualExperimentId || experimentIdParam || null,
            }),
          );
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(buildExperimentHref(experiment.id, { runId: runIdParam || null }));
          handleCloseHistory();
        }}
        onRequestDelete={() => {}}
      />
      <main className="main main--detail">
        <div className="detail detail--validation">
          <DetailHeader
            title="Validation"
            subtitle="Run in-app validation or add provider results."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push(validationBackHref)}
            backLabel={runIdParam ? "Back to selected run" : "Back to experiments"}
          />
          {runIdParam ? (
            <section className="panel__notice panel__notice--info">
              <strong>Run context preserved:</strong> this validation view was opened from the
              selected run.
              <div className="panel__actions">
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => router.push(validationBackHref)}
                >
                  Return to run
                </button>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => router.push(experimentsHref)}
                >
                  Open experiments
                </button>
              </div>
            </section>
          ) : null}
          <ValidationFlowHeader
            currentStep={validationCurrentStep}
            steps={validationFlowSteps}
            nextAction={validationNextAction}
            winnerLabel={winnerContext?.winnerLabel ?? result?.winner_id ?? "No result yet"}
            scoreText={renderMetricValue(result?.score)}
            evidenceText={renderMetricValue(result?.evidence_strength)}
            observedLogged={observedLogged}
            observedVerified={observedVerified}
            observedAccuracyText={
              observedAccuracy !== null ? `${Math.round(observedAccuracy * 100)}%` : "—"
            }
            observedUnlockReady={observedUnlockReady}
            hasSyntheticResult={Boolean(result)}
            onRunNextAction={handleRunValidationNextAction}
            onOpenExperiments={() => router.push(experimentsHref)}
          />
          <section className="panel__card panel__card--secondary panel__card--compact">
            <div className="panel__subheading">Step 1 · Configure provider defaults</div>
            <p className="panel__step-helper">
              Set the default validation provider once. This applies to both synthetic and observed
              validation panels.
            </p>
            {llmConfigError ? (
              <div className="panel__notice panel__notice--error">
                Unable to load provider configuration.
              </div>
            ) : (
              <>
                <div className="panel__chips">
                  {providerStatusItems.map((item) => (
                    <button
                      key={item.name}
                      type="button"
                      className={`panel__chip panel__chip--button ${
                        item.isActive ? "is-ready" : item.configured ? "is-ready" : "is-missing"
                      }`}
                      title={item.tooltip}
                      onClick={() => {
                        setProvider(item.name);
                        setManualForm((prev) => ({ ...prev, platform: item.name }));
                      }}
                    >
                      {item.label}:{" "}
                      {item.isActive ? "active" : item.configured ? "ready" : "missing"}
                    </button>
                  ))}
                </div>
                <p className="panel__muted">
                  Selecting a provider here sets the default for both synthetic and observed validation panels.
                </p>
              </>
            )}
          </section>
          <section className="panel__card panel__card--primary">
            <div className="panel__header">
              <h3>Synthetic validation signal</h3>
            </div>
            <div className="panel__subheading">Step 2 · Run synthetic validation</div>
            <p className="panel__step-helper">
              Create one validation job for the selected item. In-app mode executes immediately;
              manual entry lets you save a provider result when automatic return is unavailable.
            </p>
            <p className="panel__muted">
              LLM judge validation for fast screening, consistency checks, and copy-vs-copy comparisons.
            </p>
            <div className="panel__separator" />
            <div className="panel__grid validation__grid">
              <label className="panel__label">
                <span>Entity type</span>
                <select
                  className="panel__input"
                  value={entityType}
                  onChange={(event) => {
                    setEntityType(event.target.value as EntityType);
                    setSelectedEntityId("");
                    setJob(null);
                    setResult(null);
                  }}
                >
                  <option value="experiment_run">Experiment</option>
                  <option value="simulation_run">Simulation</option>
                  <option value="battery">Query battery</option>
                  <option value="copy_revision">Copy revision</option>
                </select>
              </label>
              <label className="panel__label">
                <span>Item</span>
                <select
                  className="panel__input"
                  value={selectedEntityId}
                  onChange={(event) => setSelectedEntityId(event.target.value)}
                >
                  <option value="">Select</option>
                  {entityOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="panel__label">
                <span>Provider</span>
                <select
                  className="panel__input"
                  value={provider}
                  onChange={(event) => {
                    const selected = event.target.value as ProviderType;
                    setProvider(selected);
                    setManualForm((prev) => ({ ...prev, platform: selected }));
                  }}
                >
                  <option
                    value="openai"
                    disabled={
                      mode === "provider_gemini_function" ||
                      (llmConfig
                        ? !(
                            llmConfig.providers?.openai?.validation_configured ??
                            llmConfig.providers?.openai?.configured
                          )
                        : false)
                    }
                  >
                    OpenAI (direct)
                  </option>
                  <option
                    value="gemini"
                    disabled={
                      mode === "provider_openai_mcp" ||
                      (llmConfig
                        ? !(
                            llmConfig.providers?.gemini?.validation_configured ??
                            llmConfig.providers?.gemini?.configured
                          )
                        : false)
                    }
                  >
                    Gemini
                  </option>
                  <option
                    value="anthropic"
                    disabled={
                      llmConfig
                        ? !(
                            llmConfig.providers?.anthropic?.validation_configured ??
                            llmConfig.providers?.anthropic?.configured
                          )
                        : false
                    }
                  >
                    Claude (Anthropic)
                  </option>
                  <option
                    value="openrouter"
                    disabled={
                      llmConfig
                        ? !(
                            llmConfig.providers?.openrouter?.validation_configured ??
                            llmConfig.providers?.openrouter?.configured
                          )
                        : false
                    }
                  >
                    OpenRouter
                  </option>
                </select>
              </label>
              <label className="panel__label">
                <span>Mode</span>
                <select
                  className="panel__input"
                  value={mode}
                  onChange={(event) => setMode(event.target.value as ModeType)}
                >
                  <option value="in_app_byok">In-app (BYOK)</option>
                  <option value="provider_openai_mcp">ChatGPT provider run</option>
                  <option value="provider_gemini_function">Gemini provider run</option>
                  <option value="manual_fallback">Add result manually</option>
                </select>
              </label>
              <label className="panel__label">
                <span>
                  Model (optional)
                  {llmConfig?.providers?.[provider]?.is_active ? (
                    <span className="panel__meta"></span>
                  ) : null}
                </span>
                <input
                  className="panel__input"
                  type="text"
                  list={`validation-models-${provider}`}
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder={`e.g. ${DEFAULT_MODELS[provider]}`}
                />
                <datalist id={`validation-models-${provider}`}>
                  {MODEL_OPTIONS[provider].map((option) => (
                    <option key={option} value={option} />
                  ))}
                </datalist>
              </label>
            </div>
            <div className="panel__actions panel__actions--priority">
              <button
                type="button"
                className="panel__action panel__action--prominent"
                disabled={!selectedEntityId || isSubmitting}
                onClick={handleCreateJob}
              >
                {isSubmitting ? "Working..." : "Create validation"}
              </button>
            </div>
            {isProviderIntegrationMode(mode) ? (
              <section className="panel__notice panel__notice--info">
                <strong>External validation status</strong>
                <p className="panel__muted">
                  {providerLaunchInfo?.instructions ??
                    "Complete one-time provider setup, then run validation in the provider workspace. Results return here when the provider finishes."}
                </p>
                <div className="panel__meta panel__meta--stack">
                  <span className="panel__muted">
                    Setup status: {formatSetupStatus(providerLaunchInfo?.setup_required)}
                  </span>
                  <span className="panel__muted">
                    Result status: {formatReturnStatus(job?.callback_verified)}
                  </span>
                </div>
                <details className="validation__advanced">
                  <summary>Show provider handoff details</summary>
                  <p className="panel__muted">
                    Handoff reference:{" "}
                    {providerLaunchInfo?.provider_run_id ??
                      job?.provider_run_id ??
                      "Not started"}
                  </p>
                </details>
                <div className="panel__actions">
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={() => {
                      if (!providerLaunchInfo?.setup_url) return;
                      window.open(
                        providerLaunchInfo.setup_url,
                        "_blank",
                        "noopener,noreferrer",
                      );
                    }}
                    disabled={!providerLaunchInfo?.setup_url}
                  >
                    Open one-time setup
                  </button>
                  <button
                    type="button"
                    className="panel__action panel__action--ghost"
                    onClick={() => {
                      if (!providerLaunchInfo?.launch_url) return;
                      window.open(
                        providerLaunchInfo.launch_url,
                        "_blank",
                        "noopener,noreferrer",
                      );
                    }}
                    disabled={!providerLaunchInfo?.launch_url}
                  >
                    Open provider run
                  </button>
                </div>
              </section>
            ) : null}
            {status ? (
              <div className="panel__notice panel__notice--info">{status}</div>
            ) : null}
            {error ? (
              <div className="panel__notice panel__notice--error">{error}</div>
            ) : null}
          </section>

          <section className="panel__card panel__card--primary">
            <div className="panel__header">
              <h3>Observed reality signal</h3>
            </div>
            <div className="panel__subheading">Step 3 · Log observed reality</div>
            <p className="panel__step-helper">
              Record what surfaced on real platforms for real queries to validate synthetic winners
              against external behavior.
            </p>
            <p className="panel__muted">
              Observed reality logging of what actually surfaced on real platforms for real queries.
            </p>
            <div className="panel__separator" />
            <div className="panel__form">
              <div className="panel__meta panel__meta--stack">
                <span className="panel__muted">
                  Logged observed signals: {observedLogged}
                </span>
                <span className="panel__muted">
                  Verified runs: {observedVerified} / 10
                </span>
                <span className="panel__muted">
                  Accuracy:{" "}
                  {observedAccuracy !== null ? `${Math.round(observedAccuracy * 100)}%` : "—"}
                </span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-bar__fill"
                  style={{
                    width: `${Math.round(observedProgress * 100)}%`,
                  }}
                />
              </div>
              {manualBrandSummary ? (
                <div className="panel__meta panel__meta--stack">
                  <span className="panel__muted">
                    Brand accuracy:{" "}
                    {observedBrandAccuracy !== null
                      ? `${Math.round(observedBrandAccuracy * 100)}%`
                      : "—"}
                  </span>
                  <span className="panel__muted">
                    Verified (brand): {observedBrandVerified}
                  </span>
                </div>
              ) : null}
              <div className="panel__grid validation__grid">
                <label className="panel__label">
                  <span>Experiment</span>
                  <select
                    className="panel__input"
                    value={manualExperimentId}
                    onChange={(event) => setManualExperimentId(event.target.value)}
                  >
                    <option value="">Select experiment</option>
                    {experiments.map((experiment) => (
                      <option key={experiment.id} value={experiment.id}>
                        {experiment.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="panel__label">
                  <span>Variant (lab winner)</span>
                  <select
                    className="panel__input"
                    value={manualForm.variantId}
                    onChange={(event) =>
                      setManualForm((prev) => ({ ...prev, variantId: event.target.value }))
                    }
                  >
                    <option value="">Select variant</option>
                    {manualVariants.map((variant) => (
                      <option key={variant.id} value={variant.id}>
                        {variant.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="panel__label">
                  <span>Platform</span>
                <select
                  className="panel__input"
                  value={manualForm.platform}
                  onChange={(event) => {
                    const selected = event.target.value as ProviderType;
                    setManualForm((prev) => ({ ...prev, platform: selected }));
                    setProvider(selected);
                  }}
                >
                    {observedPlatformOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="panel__label">
                  <span>Query tested</span>
                  <input
                    className="panel__input"
                    value={manualForm.queryText}
                    onChange={(event) =>
                      setManualForm((prev) => ({ ...prev, queryText: event.target.value }))
                    }
                    placeholder="e.g., running shoes for marathon training"
                  />
                </label>
                <label className="panel__label">
                  <span>Products shown (comma-separated)</span>
                  <input
                    className="panel__input"
                    value={manualForm.observedProducts}
                    onChange={(event) =>
                      setManualForm((prev) => ({
                        ...prev,
                        observedProducts: event.target.value,
                      }))
                    }
                    placeholder="Product A, Product B"
                  />
                </label>
                <label className="panel__label">
                  <span>Observed winner variant (optional)</span>
                  <input
                    className="panel__input"
                    value={manualForm.observedWinnerVariantId}
                    onChange={(event) =>
                      setManualForm((prev) => ({
                        ...prev,
                        observedWinnerVariantId: event.target.value,
                      }))
                    }
                    placeholder="Paste a saved variant reference if needed"
                  />
                </label>
                <label className="panel__label">
                  <span>Observed position (optional)</span>
                  <input
                    className="panel__input"
                    value={manualForm.observedPosition}
                    onChange={(event) =>
                      setManualForm((prev) => ({
                        ...prev,
                        observedPosition: event.target.value,
                      }))
                    }
                    placeholder="1"
                  />
                </label>
                <label className="panel__label">
                  <span>Notes</span>
                  <textarea
                    className="panel__textarea"
                    value={manualForm.notes}
                    onChange={(event) =>
                      setManualForm((prev) => ({ ...prev, notes: event.target.value }))
                    }
                    rows={2}
                    placeholder="Any observations..."
                  />
                </label>
              </div>
              <div className="panel__actions panel__actions--priority">
                <button
                  type="button"
                  className="panel__action panel__action--prominent"
                  onClick={handleLogObservedValidation}
                  disabled={isSubmitting || !manualExperimentId}
                >
                  {isSubmitting ? "Logging..." : "Log observed reality signal"}
                </button>
              </div>
              {manualStatus ? (
                <div className="panel__notice panel__notice--info">{manualStatus}</div>
              ) : null}
              {manualError ? (
                <div className="panel__notice panel__notice--error">{manualError}</div>
              ) : null}
            </div>
          </section>

          <section className="panel__card panel__card--secondary">
            <div className="panel__header">
              <h3>Variant comparison</h3>
            </div>
            <div className="panel__subheading">Step 4 · Compare outcomes</div>
            <p className="panel__step-helper">
              Keep this collapsed by default. Expand when you need side-by-side variant metrics to
              support the next experiment decision.
            </p>
            <details className="panel__details">
              <summary className="panel__details-summary">Compare variants</summary>
              <p className="panel__muted">
                Latest per-variant lab metrics for the selected experiment.
              </p>
              {!manualExperimentId || manualVariants.length === 0 ? (
                <p className="panel__empty">
                  Select an experiment to compare variants.
                </p>
              ) : (
                <ul className="panel__list">
                  {manualVariants.map((variant) => {
                    const metric = manualMetricsByVariant.get(variant.id);
                    const values = (metric?.metrics ?? {}) as Record<string, unknown>;
                    return (
                      <li key={variant.id}>
                        <div className="panel__meta">
                          <span>{variant.label}</span>
                          <span className="panel__badge panel__badge--secondary">
                            {variant.type}
                          </span>
                        </div>
                        <div className="panel__meta">
                          <span className="panel__muted">
                            Win rate: {renderMetricValue(values.win_rate)}
                          </span>
                          <span className="panel__muted">
                            Robust win rate: {renderMetricValue(values.win_rate_robust)}
                          </span>
                          <span className="panel__muted">
                            Avg score: {renderMetricValue(values.avg_score)}
                          </span>
                          <span className="panel__muted">
                            Runs: {renderMetricValue(values.total_runs)}
                          </span>
                        </div>
                        {metric?.created_at ? (
                          <span className="panel__muted">
                            Last run: {new Date(metric.created_at).toLocaleDateString()}
                          </span>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </details>
          </section>

          {isManualFallbackMode(job?.mode) && job?.external_instructions ? (
            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>External validation instructions</h3>
              </div>
              <div className="panel__subheading">Supplement · Paste external result</div>
              <p className="panel__step-helper">
                Use this only when adding a result manually. Submit the provider result to complete
                the synthetic validation.
              </p>
              <details className="panel__details">
                <summary className="panel__details-summary">Open manual instructions</summary>
                <pre className="panel__pre">{job.external_instructions}</pre>
                <div className="panel__grid validation__grid">
                  <label className="panel__label">
                    <span>Provider result</span>
                    <textarea
                      className="panel__textarea"
                      rows={6}
                      value={externalJson}
                      onChange={(event) => setExternalJson(event.target.value)}
                      placeholder='{"winner_id":"candidate","score":0.72,"confidence":0.8,"evidence_strength":"moderate","rationale_bullets":["..."],"flags":[]}'
                    />
                  </label>
                  <label className="panel__label">
                    <span>Raw response (optional)</span>
                    <textarea
                      className="panel__textarea"
                      rows={6}
                      value={externalRaw}
                      onChange={(event) => setExternalRaw(event.target.value)}
                      placeholder="Paste raw provider output"
                    />
                  </label>
                </div>
                <div className="panel__actions panel__actions--priority">
                  <button
                    type="button"
                    className="panel__action panel__action--prominent"
                    disabled={!externalJson || isSubmitting}
                    onClick={handleSubmitExternal}
                  >
                    {isSubmitting ? "Saving..." : "Submit external result"}
                  </button>
                </div>
              </details>
            </section>
          ) : null}

          {result ? (
            <section className="panel__card panel__card--primary">
              <div className="panel__header">
                <h3>Validation result</h3>
              </div>
              <div className="panel__subheading">Step 5 · Decide next move</div>
              <p className="panel__step-helper">
                Use the winner signal, confidence, and observed evidence readiness before generating
                the next experiment variant.
              </p>
              <div className="panel__metrics">
                <div className="panel__label">
                  <span>Winner</span>
                  {winnerContext?.simulationRunId ? (
                    <strong>
                      <a
                        className="panel__link"
                        href={simulationHref(winnerContext.simulationRunId)}
                      >
                        {winnerContext.winnerLabel}
                      </a>
                    </strong>
                  ) : (
                    <strong>{winnerContext?.winnerLabel ?? result.winner_id ?? "—"}</strong>
                  )}
                </div>
                <div className="panel__label">
                  <span>Score</span>
                  <strong>{result.score ?? "—"}</strong>
                </div>
                <div className="panel__label">
                  <span>Evidence</span>
                  <strong>{result.evidence_strength ?? "—"}</strong>
                </div>
              </div>
              {winnerContext?.experimentName || winnerContext?.queryText ? (
                <div className="panel__meta panel__meta--stack">
                  {winnerContext.experimentName ? (
                    <span>Experiment: {winnerContext.experimentName}</span>
                  ) : null}
                  {winnerContext.queryText ? (
                    <span>Query: {winnerContext.queryText}</span>
                  ) : null}
                </div>
              ) : null}
              {job?.entity_type === "copy_revision" &&
              String(result.winner_id || "").toLowerCase() === "candidate" ? (
                <div className="panel__actions panel__actions--priority">
                  <button
                    type="button"
                    className="panel__action panel__action--prominent"
                    onClick={handlePublishCandidate}
                  >
                    Publish candidate copy
                  </button>
                </div>
              ) : null}
              {result.structured_result ? (
                <details className="panel__details">
                  <summary className="panel__details-summary">
                    View validation data
                  </summary>
                  <pre className="panel__pre">
                    {JSON.stringify(result.structured_result, null, 2)}
                  </pre>
                </details>
              ) : null}
            </section>
          ) : null}
        </div>
      </main>
    </div>
  );
}

export default function ValidationPage() {
  return (
    <Suspense fallback={null}>
      <ValidationPageContent />
    </Suspense>
  );
}
