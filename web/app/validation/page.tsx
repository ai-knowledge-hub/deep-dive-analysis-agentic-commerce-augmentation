"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  Experiment,
  ExperimentMetric,
  ExperimentRun,
  ExperimentVariant,
  QueryBattery,
  QueryBatteryQuery,
  SimulationRunSummary,
  ValidationJob,
  ValidationResult,
  LLMConfigSummaryResponse,
} from "../../lib/types";
import {
  createValidationJob,
  runValidationJob,
  submitValidationExternal,
  listExperiments,
  listSimulationRuns,
  getSimulationRun,
  listExperimentRuns,
  listExperimentMetrics,
  listExperimentVariants,
  listBatteries,
  listBatteryQueries,
  getLlmConfig,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";

type EntityType = "experiment_run" | "simulation_run" | "battery";
type ProviderType = "openai" | "gemini" | "anthropic" | "openrouter";
type ModeType = "in_app" | "external";

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

export default function ValidationPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { clientId } = useTenant();
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [batteries, setBatteries] = useState<QueryBattery[]>([]);
  const [llmConfig, setLlmConfig] = useState<LLMConfigSummaryResponse | null>(null);
  const [llmConfigError, setLlmConfigError] = useState<string | null>(null);
  const [entityType, setEntityType] = useState<EntityType>("experiment_run");
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [provider, setProvider] = useState<ProviderType>("openai");
  const [mode, setMode] = useState<ModeType>("in_app");
  const [model, setModel] = useState<string>("");
  const [job, setJob] = useState<ValidationJob | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [externalJson, setExternalJson] = useState("");
  const [externalRaw, setExternalRaw] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);

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
  }, [userId, clientId]);

  useEffect(() => {
    void getLlmConfig(userId ?? undefined)
      .then((response) => {
        setLlmConfig(response);
        setLlmConfigError(null);
        if (response.active_provider) {
          const active =
            response.active_provider === "claude"
              ? "anthropic"
              : response.active_provider;
          setProvider(active as ProviderType);
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
    return batteries.map((battery) => ({
      id: battery.id,
      label: battery.name || "Battery",
    }));
  }, [batteries, entityType, experiments, simulationRuns]);

  const winnerContext = useMemo(() => {
    if (!result?.winner_id || !job?.input_payload) return null;
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
      if (mode === "in_app") {
        setStatus("Running validation...");
        const runResponse = await runValidationJob(response.job.id, userId);
        setJob(runResponse.job);
        setResult(runResponse.result ?? null);
        setStatus("Validation complete.");
      } else {
        setStatus("Awaiting external validation.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to validate.");
    } finally {
      setSubmitting(false);
      window.setTimeout(() => setStatus(null), 4000);
    }
  }, [buildPayload, entityType, mode, model, provider, selectedEntityId, userId]);

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
      setError(err instanceof Error ? err.message : "Invalid JSON.");
    } finally {
      setSubmitting(false);
      window.setTimeout(() => setStatus(null), 4000);
    }
  }, [externalJson, externalRaw, job, model, provider, userId]);

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/")}
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
          router.push(`/simulation?run_id=${run.id}`);
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(`/experiments?experiment_id=${experiment.id}`);
          handleCloseHistory();
        }}
        onRequestDelete={() => {}}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Validation"
            subtitle="Run in-app validation or collect structured external feedback."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/experiments")}
            backLabel="Back to experiments"
          />
          <section className="panel__card">
            <div className="panel__header">
              <h3>Validation setup</h3>
            </div>
            <div className="panel__subheading">Provider status</div>
            {llmConfigError ? (
              <div className="panel__notice panel__notice--error">
                Unable to load provider configuration.
              </div>
            ) : (
              <div className="panel__chips">
                {(
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
                  return (
                    <span
                      key={name}
                      className={`panel__chip ${
                        entry?.is_active ? "is-ready" : configured ? "is-ready" : "is-missing"
                      }`}
                      title={tooltip}
                    >
                      {label}:{" "}
                      {entry?.is_active ? "active" : configured ? "ready" : "missing"}
                    </span>
                  );
                })}
              </div>
            )}
            <div className="panel__grid">
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
                  onChange={(event) =>
                    setProvider(event.target.value as ProviderType)
                  }
                >
                  <option
                    value="openai"
                    disabled={
                      llmConfig
                        ? !(
                            llmConfig.providers?.openai?.validation_configured ??
                            llmConfig.providers?.openai?.configured
                          )
                        : false
                    }
                  >
                    OpenAI (direct)
                  </option>
                  <option
                    value="gemini"
                    disabled={
                      llmConfig
                        ? !(
                            llmConfig.providers?.gemini?.validation_configured ??
                            llmConfig.providers?.gemini?.configured
                          )
                        : false
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
                  <option value="in_app">In-app (BYOK)</option>
                  <option value="external">External paste-back</option>
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
            <div className="panel__actions">
              <button
                type="button"
                className="panel__action"
                disabled={!selectedEntityId || isSubmitting}
                onClick={handleCreateJob}
              >
                {isSubmitting ? "Working..." : "Create validation"}
              </button>
            </div>
            {status ? (
              <div className="panel__notice panel__notice--info">{status}</div>
            ) : null}
            {error ? (
              <div className="panel__notice panel__notice--error">{error}</div>
            ) : null}
          </section>

          {job?.mode === "external" && job?.external_instructions ? (
            <section className="panel__card">
              <div className="panel__header">
                <h3>External validation instructions</h3>
              </div>
              <pre className="panel__pre">{job.external_instructions}</pre>
              <div className="panel__grid">
                <label className="panel__label">
                  <span>Paste structured JSON</span>
                  <textarea
                    className="panel__textarea"
                    rows={6}
                    value={externalJson}
                    onChange={(event) => setExternalJson(event.target.value)}
                    placeholder='{"winner_id":"variant_a","score":0.72,"confidence":0.8,"evidence_strength":"moderate","rationale_bullets":["..."],"flags":[]}'
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
              <div className="panel__actions">
                <button
                  type="button"
                  className="panel__action"
                  disabled={!externalJson || isSubmitting}
                  onClick={handleSubmitExternal}
                >
                  {isSubmitting ? "Saving..." : "Submit external result"}
                </button>
              </div>
            </section>
          ) : null}

          {result ? (
            <section className="panel__card">
              <div className="panel__header">
                <h3>Validation result</h3>
              </div>
              <div className="panel__metrics">
                <div className="panel__label">
                  <span>Winner</span>
                  {winnerContext?.simulationRunId ? (
                    <strong>
                      <a
                        className="panel__link"
                        href={`/simulation?run_id=${winnerContext.simulationRunId}`}
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
              {result.structured_result ? (
                <pre className="panel__pre">
                  {JSON.stringify(result.structured_result, null, 2)}
                </pre>
              ) : null}
            </section>
          ) : null}
        </div>
      </main>
    </div>
  );
}
