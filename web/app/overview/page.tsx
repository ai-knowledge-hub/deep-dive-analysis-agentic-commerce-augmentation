"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  SessionSummary,
  OverviewSummaryResponse,
  OverviewTimeseriesResponse,
  OverviewChangesResponse,
  SimulationRunSummary,
  Experiment,
} from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import {
  deleteConversationSession,
  deleteExperiment,
  deleteSimulationRun,
  listConversationSessions,
  getOverviewSummary,
  getOverviewTimeseries,
  getOverviewChanges,
  listSimulationRuns,
  listExperiments,
} from "../../lib/api";
import { useTenant } from "../../components/tenant/TenantProvider";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";

export default function OverviewPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { clientId } = useTenant();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [summary, setSummary] = useState<OverviewSummaryResponse | null>(null);
  const [timeseries, setTimeseries] = useState<OverviewTimeseriesResponse | null>(
    null,
  );
  const [changes, setChanges] = useState<OverviewChangesResponse | null>(null);
  const [rangeDays, setRangeDays] = useState(30);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
    void listExperiments(userId).then((response) => {
      setExperiments(response.experiments ?? []);
    });
  }, [userId, clientId]);

  useEffect(() => {
    if (!userId) return;
    void getOverviewSummary("client", rangeDays, userId).then(setSummary);
    void getOverviewTimeseries("client", rangeDays, userId).then(setTimeseries);
    void getOverviewChanges("client", rangeDays, userId).then(setChanges);
  }, [clientId, rangeDays, userId]);

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
      } catch {
        // ignore delete errors
      }
    },
    [clientId, userId],
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
    },
    [clientId, userId],
  );

  const combinedExperimentSeries = useMemo(() => {
    const winRateSeries = timeseries?.series.win_rate ?? [];
    const avgScoreSeries = timeseries?.series.avg_score ?? [];
    const map = new Map<string, { date: string; win_rate?: number; avg_score?: number }>();
    winRateSeries.forEach((item) => {
      map.set(item.date, { date: item.date, win_rate: item.value });
    });
    avgScoreSeries.forEach((item) => {
      map.set(item.date, {
        date: item.date,
        ...(map.get(item.date) ?? {}),
        avg_score: item.value,
      });
    });
    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [timeseries?.series.avg_score, timeseries?.series.win_rate]);

  const latestWinRate = summary?.kpis.experiments.latest_win_rate;
  const latestAvgScore = summary?.kpis.experiments.latest_avg_score;
  const evidenceLift = summary?.kpis.evidence.avg_lift;
  const simulationLift = summary?.kpis.simulation.avg_lift;
  const validationAccuracy = summary?.kpis.validation.accuracy;
  const batteryCoverage = summary?.kpis.battery_health.coverage_score;
  const redundancyRate = summary?.kpis.battery_health.redundancy_rate;
  const protocolScore = summary?.kpis.protocol_readiness.score;

  const tooltipStyle = {
    backgroundColor: "rgba(10, 12, 16, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: 8,
    color: "#f3f4f6",
    boxShadow: "0 12px 30px rgba(0,0,0,0.45)",
  };

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/lab")}
        sessions={sessions}
        activeSessionId={null}
        onSelectSession={(sessionId) => router.push(`/?session=${sessionId}`)}
        onDeleteSession={(sessionId) => setDeleteTargetId(sessionId)}
        onOpenHistory={() => {
          setHistoryOpen(true);
          setHistoryClosing(false);
        }}
      />
      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay is-visible"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close menu"
        />
      )}
      {deleteTargetId && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal">
            <h4>Delete conversation?</h4>
            <p>This will permanently remove the chat history.</p>
            <div className="modal__actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setDeleteTargetId(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={confirmDeleteSession}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        isClosing={isHistoryClosing}
        sessions={sessions}
        simulations={simulationRuns}
        experiments={experiments}
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(session) => {
          router.push(`/?session=${session.id}`);
          handleCloseHistory();
        }}
        onSelectSimulation={(run) => {
          router.push(`/simulation?run_id=${run.id}`);
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(`/experiments?experiment_id=${experiment.id}`);
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
        onRequestDeleteSimulation={handleDeleteSimulationRun}
        onRequestDeleteExperiment={handleDeleteExperiment}
        onRequestDeleteSessionsBulk={handleBulkDeleteSessions}
        onRequestDeleteSimulationsBulk={handleBulkDeleteSimulations}
        onRequestDeleteExperimentsBulk={handleBulkDeleteExperiments}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Overview"
            subtitle="A compact dashboard of the latest simulation, evidence, and alignment signals."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/lab")}
            backLabel="Back to chat"
          />
          <div className="overview__controls">
            <div className="overview__control">
              <span className="overview__label">Scope</span>
              <span className="overview__value">Client</span>
            </div>
            <label className="overview__control">
              <span className="overview__label">Range</span>
              <select
                className="panel__input"
                value={rangeDays}
                onChange={(event) => setRangeDays(Number(event.target.value))}
              >
                <option value={7}>7 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
                <option value={365}>All</option>
              </select>
            </label>
          </div>
          <div className="detail__grid">
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Experiment performance</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/experiments")}
                >
                  Open
                </button>
              </div>
              <div className="summary-card__meta">
                <span>
                  Win rate:{" "}
                  {typeof latestWinRate === "number"
                    ? `${Math.round(latestWinRate * 100)}%`
                    : "—"}
                </span>
                <span>
                  Avg score:{" "}
                  {typeof latestAvgScore === "number"
                    ? Math.round(latestAvgScore * 100) / 100
                    : "—"}
                </span>
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Validation accuracy</h4>
              </div>
              <div className="summary-card__meta">
                <span>
                  Accuracy:{" "}
                  {typeof validationAccuracy === "number"
                    ? `${Math.round(validationAccuracy * 100)}%`
                    : "—"}
                </span>
                <span>
                  Verified runs: {summary?.kpis.validation.verified_runs ?? 0}
                </span>
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Simulation lift</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/simulation")}
                >
                  Open
                </button>
              </div>
              <div className="summary-card__meta">
                <span>
                  Avg lift:{" "}
                  {typeof simulationLift === "number"
                    ? `${Math.round(simulationLift * 100)}%`
                    : "—"}
                </span>
                <span>Runs: {summary?.kpis.simulation.runs ?? 0}</span>
                <span>Lessons: {summary?.kpis.simulation.lessons ?? 0}</span>
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Evidence signals</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/evidence")}
                >
                  Open
                </button>
              </div>
              <div className="summary-card__meta">
                <span>
                  Avg lift:{" "}
                  {typeof evidenceLift === "number"
                    ? `${Math.round(evidenceLift * 100)}%`
                    : "—"}
                </span>
                <span>Evidence items: {summary?.kpis.evidence.evidence_items ?? 0}</span>
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Battery health</h4>
              </div>
              <div className="summary-card__meta">
                <span>
                  Coverage:{" "}
                  {typeof batteryCoverage === "number"
                    ? `${Math.round(batteryCoverage * 100)}%`
                    : "—"}
                </span>
                <span>
                  Redundancy:{" "}
                  {typeof redundancyRate === "number"
                    ? `${Math.round(redundancyRate * 100)}%`
                    : "—"}
                </span>
                <span>
                  Enabled: {summary?.kpis.battery_health.enabled_queries ?? 0}
                </span>
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Protocol readiness</h4>
              </div>
              <div className="summary-card__meta">
                <span>
                  Score:{" "}
                  {typeof protocolScore === "number" ? `${protocolScore}/100` : "—"}
                </span>
              </div>
            </div>
          </div>
          <div className="overview__charts">
            <section className="panel__card">
              <div className="panel__header">
                <h3>Experiment trend</h3>
              </div>
              <div className="panel__chart panel__chart--tall">
                {combinedExperimentSeries.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={combinedExperimentSeries}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="date" tick={{ fill: "#8f98a8" }} />
                      <YAxis tick={{ fill: "#8f98a8" }} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        itemStyle={{ color: "#e2e8f0" }}
                        labelStyle={{ color: "#94a3b8" }}
                        cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="win_rate"
                        stroke="#1cc486"
                        strokeWidth={2}
                        dot={false}
                        name="Win rate"
                      />
                      <Line
                        type="monotone"
                        dataKey="avg_score"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                        dot={false}
                        name="Avg score"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="summary-card__empty">No experiment trend yet.</div>
                )}
              </div>
            </section>
            <section className="panel__card">
              <div className="panel__header">
                <h3>Validation accuracy</h3>
              </div>
              <div className="panel__chart">
                {timeseries?.series.validation_accuracy?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeseries.series.validation_accuracy}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="date" tick={{ fill: "#8f98a8" }} />
                      <YAxis tick={{ fill: "#8f98a8" }} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        itemStyle={{ color: "#e2e8f0" }}
                        labelStyle={{ color: "#94a3b8" }}
                        cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#1cc486"
                        strokeWidth={2}
                        dot={false}
                        name="Accuracy"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="summary-card__empty">No validations yet.</div>
                )}
              </div>
            </section>
            <section className="panel__card">
              <div className="panel__header">
                <h3>Simulation lift</h3>
              </div>
              <div className="panel__chart">
                {timeseries?.series.simulation_lift?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeseries.series.simulation_lift}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="date" tick={{ fill: "#8f98a8" }} />
                      <YAxis tick={{ fill: "#8f98a8" }} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        itemStyle={{ color: "#e2e8f0" }}
                        labelStyle={{ color: "#94a3b8" }}
                        cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#1cc486"
                        strokeWidth={2}
                        dot={false}
                        name="Lift"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="summary-card__empty">No simulation lift yet.</div>
                )}
              </div>
            </section>
            <section className="panel__card">
              <div className="panel__header">
                <h3>Belief updates</h3>
              </div>
              <div className="panel__chart">
                {timeseries?.series.belief_count?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={timeseries.series.belief_count}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="date" tick={{ fill: "#8f98a8" }} />
                      <YAxis tick={{ fill: "#8f98a8" }} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        itemStyle={{ color: "#e2e8f0" }}
                        labelStyle={{ color: "#94a3b8" }}
                        cursor={{ fill: "rgba(255,255,255,0.04)" }}
                      />
                      <Bar dataKey="value" fill="#1cc486" name="Beliefs" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="summary-card__empty">No belief updates yet.</div>
                )}
              </div>
            </section>
          </div>
          <div className="overview__changes">
            <section className="panel__card">
              <div className="panel__header">
                <h3>What changed</h3>
              </div>
              <div className="panel__grid">
                <div>
                  <p className="panel__subtitle">Latest experiment</p>
                  <p className="panel__text">
                    {changes?.latest_experiment?.name ?? "No experiment yet."}
                  </p>
                  <p className="panel__muted">
                    {changes?.latest_experiment?.created_at
                      ? new Date(changes.latest_experiment.created_at).toLocaleString()
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="panel__subtitle">Latest simulation lesson</p>
                  <p className="panel__text">
                    {changes?.latest_simulation_lesson?.summary ??
                      "No lessons yet."}
                  </p>
                </div>
                <div>
                  <p className="panel__subtitle">Top gap signals</p>
                  {changes?.top_gap_signals?.length ? (
                    <ul className="panel__list panel__list--compact">
                      {changes.top_gap_signals.map((item) => (
                        <li key={item.signal}>
                          {item.signal} · {item.count}x
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="panel__muted">No gap signals yet.</p>
                  )}
                </div>
                <div>
                  <p className="panel__subtitle">Next test</p>
                  <p className="panel__text">
                    {typeof changes?.next_test?.reason === "string"
                      ? changes.next_test.reason
                      : "No recommendation yet."}
                  </p>
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
