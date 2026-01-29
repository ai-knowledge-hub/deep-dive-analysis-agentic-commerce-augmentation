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
  const [batteryEdit, setBatteryEdit] = useState({
    name: "",
    purpose: "",
    status: "draft",
  });
  const [batteryMetrics, setBatteryMetrics] = useState<Record<string, unknown> | null>(
    null,
  );
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
  const [queryStatus, setQueryStatus] = useState<string | null>(null);
  const [scheduleForm, setScheduleForm] = useState({
    enabled: false,
    intervalMinutes: "1440",
  });
  const [scheduleStatus, setScheduleStatus] = useState<string | null>(null);
  const [metricsTrendMetric, setMetricsTrendMetric] = useState<
    "win_rate" | "avg_score"
  >("win_rate");
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
  }, [selectedExperimentId, selectedExperiment?.battery_id, userId]);

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
  }, [experimentForm, jsonErrors, productId, userId]);

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

  const latestMetric = metrics[0]?.metrics as Record<string, unknown> | undefined;
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

  const metricsHistory = useMemo(() => {
    return [...metrics]
      .filter((metric) => metric.variant_id)
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
      .slice(0, 10);
  }, [metrics]);

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
          </div>

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
                          Win rate: {values.win_rate ?? "—"}
                        </span>
                        <span className="panel__muted">
                          Avg score: {values.avg_score ?? "—"}
                        </span>
                        <span className="panel__muted">
                          Runs: {values.total_runs ?? "—"}
                        </span>
                      </div>
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
