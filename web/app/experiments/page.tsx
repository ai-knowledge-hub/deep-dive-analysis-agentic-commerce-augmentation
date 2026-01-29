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
  SessionSummary,
} from "../../lib/types";
import {
  createBattery,
  createExperiment,
  createExperimentVariant,
  deleteConversationSession,
  generateBatteryQueries,
  listConversationSessions,
  listBatteries,
  listExperimentMetrics,
  listExperimentRuns,
  listExperimentVariants,
  listExperiments,
  listBatteryQueries,
  runExperiment,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";

export default function ExperimentsPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { productId, productName } = useTenant();

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(null);
  const [variants, setVariants] = useState<ExperimentVariant[]>([]);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [metrics, setMetrics] = useState<ExperimentMetric[]>([]);
  const [queries, setQueries] = useState<QueryBatteryQuery[]>([]);
  const [batteries, setBatteries] = useState<QueryBattery[]>([]);
  const [runningVariantId, setRunningVariantId] = useState<string | null>(null);
  const [batteryForm, setBatteryForm] = useState({
    name: "",
    purpose: "",
    generationMode: "bottom_up",
  });
  const [batterySeedQueries, setBatterySeedQueries] = useState("");
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
  const [experimentStatus, setExperimentStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
  }, [userId]);

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

  const selectedExperiment = useMemo(
    () => experiments.find((item) => item.id === selectedExperimentId) ?? null,
    [experiments, selectedExperimentId],
  );

  useEffect(() => {
    if (!selectedExperimentId) {
      setVariants([]);
      setRuns([]);
      setMetrics([]);
      setQueries([]);
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
    const batteryId = selectedExperiment?.battery_id;
    if (batteryId) {
      void listBatteryQueries(batteryId, userId).then((response) => {
        setQueries(response.queries ?? []);
      });
    } else {
      setQueries([]);
    }
  }, [selectedExperimentId, selectedExperiment?.battery_id, userId]);

  const queryMap = useMemo(() => {
    const map = new Map<string, string>();
    queries.forEach((query) => map.set(query.id, query.query_text));
    return map;
  }, [queries]);

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
    [selectedExperimentId, userId],
  );

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

  const handleGenerateQueries = useCallback(
    async (batteryId: string) => {
      if (!batteryId) return;
      setFormError(null);
      setSubmitting(true);
      try {
        const seedList = batterySeedQueries
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);
        await generateBatteryQueries(batteryId, {
          source: batteryForm.generationMode,
          seed_queries: seedList.length ? seedList : undefined,
          user_id: userId,
        });
        const refreshed = await listBatteryQueries(batteryId, userId);
        setQueries(refreshed.queries ?? []);
      } finally {
        setSubmitting(false);
      }
    },
    [batterySeedQueries, batteryForm.generationMode, userId],
  );

  const handleCreateExperiment = useCallback(async () => {
    if (!productId || !experimentForm.name.trim()) return;
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
      const response = await createExperiment({
        name: experimentForm.name.trim(),
        product_id: productId,
        battery_id: experimentForm.batteryId || undefined,
        hypothesis,
        competitor_policy: competitorPolicy,
        user_id: userId,
      });
      const refreshed = await listExperiments(userId, productId ?? undefined);
      setExperiments(refreshed.experiments ?? []);
      setSelectedExperimentId(response.experiment.id);
      setExperimentForm({
        name: "",
        batteryId: "",
        hypothesis: "",
        competitorPolicy: "",
      });
      setExperimentStatus("Experiment created.");
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Invalid JSON payload.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [experimentForm, productId, userId]);

  const handleCreateVariant = useCallback(async () => {
    if (!selectedExperimentId || !variantForm.label.trim()) return;
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
  }, [selectedExperimentId, userId, variantForm]);

  const latestMetric = metrics[0]?.metrics as Record<string, unknown> | undefined;

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
      <main className="detail">
        <DetailHeader
          title="Experiments"
          subtitle={
            productName
              ? `Experiment results for ${productName}`
              : "Track query batteries, variants, and outcomes."
          }
          onMenu={() => setSidebarOpen(true)}
          onBack={() => router.push("/")}
        />
        <div className="detail__stack">
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
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleCreateBattery}
                  disabled={isSubmitting || batteryForm.name.trim() === ""}
                >
                  Create battery
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
                  Generate queries
                </button>
              </div>
            ) : (
              <p className="panel__empty">Select a product to create a battery.</p>
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
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleCreateExperiment}
                  disabled={isSubmitting || experimentForm.name.trim() === ""}
                >
                  Create experiment
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
                </label>
                <button
                  type="button"
                  className="panel__action"
                  onClick={handleCreateVariant}
                  disabled={isSubmitting || !selectedExperimentId}
                >
                  Add variant
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
                  <li>Avg score: {latestMetric.avg_score ?? "-"}</li>
                </ul>
              ) : (
                <p className="panel__empty">Run a variant to generate metrics.</p>
              )}
            </section>
          </div>

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
                    <span className="history-panel__meta">
                      Variant: {run.variant_id}
                    </span>
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
      </main>
    </div>
  );
}
