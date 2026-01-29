"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  ConversationResponse,
  EvidenceAnalyzeResponse,
  ExperimentMetric,
  Experiment,
  RecommendationVerifyResponse,
  RepresentationOptimizeResponse,
  SessionSummary,
  SimulationLesson,
  SimulationRunSummary,
} from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import {
  deleteConversationSession,
  listConversationSessions,
  listExperimentMetrics,
  listExperiments,
  listSimulationLessons,
  listSimulationRuns,
} from "../../lib/api";
import { useTenant } from "../../components/tenant/TenantProvider";

type AlignmentSnapshot = {
  intent?: ConversationResponse["intent"];
  goal_state?: ConversationResponse["goal_state"];
  plan?: ConversationResponse["plan"];
  clarifications?: string[];
  product_reasoning?: ConversationResponse["product_explanations"];
  research_results?: ConversationResponse["plan"]["research_results"];
  last_query?: string | null;
};

type EvidenceSnapshot = {
  analysis?: EvidenceAnalyzeResponse | null;
  optimization?: RepresentationOptimizeResponse | null;
  verification?: RecommendationVerifyResponse | null;
};

type SimulationSnapshot = {
  scenario?: string;
  products?: unknown[];
  run?: unknown;
};

export default function OverviewPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { productId } = useTenant();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [simulationLessons, setSimulationLessons] = useState<SimulationLesson[]>([]);
  const [experimentMetrics, setExperimentMetrics] = useState<ExperimentMetric[]>([]);
  const [latestExperiment, setLatestExperiment] = useState<Experiment | null>(null);
  const [trendMetric, setTrendMetric] = useState<"win_rate" | "avg_score">(
    "win_rate",
  );
  const [alignment, setAlignment] = useState<AlignmentSnapshot>({});
  const [evidence, setEvidence] = useState<EvidenceSnapshot>({});
  const [simulation, setSimulation] = useState<SimulationSnapshot>({});
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const alignmentStorageKey = useMemo(
    () => (userId ? `intentionality.alignment.${userId}` : "intentionality.alignment.anonymous"),
    [userId],
  );
  const evidenceStorageKey = useMemo(
    () => (userId ? `intentionality.evidence.${userId}` : "intentionality.evidence.anonymous"),
    [userId],
  );
  const simulationStorageKey = useMemo(
    () => (userId ? `intentionality.simulation.${userId}` : "intentionality.simulation.anonymous"),
    [userId],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const rawAlignment = localStorage.getItem(alignmentStorageKey);
    if (rawAlignment) {
      try {
        setAlignment(JSON.parse(rawAlignment) as AlignmentSnapshot);
      } catch {
        localStorage.removeItem(alignmentStorageKey);
      }
    }
    const rawEvidence = localStorage.getItem(evidenceStorageKey);
    if (rawEvidence) {
      try {
        setEvidence(JSON.parse(rawEvidence) as EvidenceSnapshot);
      } catch {
        localStorage.removeItem(evidenceStorageKey);
      }
    }
    const rawSimulation = localStorage.getItem(simulationStorageKey);
    if (rawSimulation) {
      try {
        setSimulation(JSON.parse(rawSimulation) as SimulationSnapshot);
      } catch {
        localStorage.removeItem(simulationStorageKey);
      }
    }
  }, [alignmentStorageKey, evidenceStorageKey, simulationStorageKey]);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
    void listSimulationLessons(userId).then((response) => {
      setSimulationLessons(response.lessons ?? []);
    });
    void listExperiments(userId, productId ?? undefined).then((response) => {
      const experiment = response.experiments?.[0] ?? null;
      setLatestExperiment(experiment);
      if (!experiment) {
        setExperimentMetrics([]);
        return;
      }
      void listExperimentMetrics(experiment.id, userId).then((metricsResponse) => {
        setExperimentMetrics(metricsResponse.metrics ?? []);
      });
    });
  }, [productId, userId]);

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

  const plan = alignment.plan;
  const lastQuery = alignment.last_query;
  const evidenceCount = evidence.analysis?.evidence_products?.length ?? 0;
  const evidenceLift =
    evidence.verification?.lift !== undefined
      ? `${Math.round(evidence.verification.lift * 100)}%`
      : "—";

  const experimentTrend = useMemo(() => {
    if (!experimentMetrics.length) return [];
    return [...experimentMetrics]
      .filter((metric) =>
        trendMetric === "win_rate"
          ? metric.metrics?.win_rate !== undefined
          : metric.metrics?.avg_score !== undefined,
      )
      .sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""))
      .slice(-12)
      .map((metric) =>
        Number(
          trendMetric === "win_rate"
            ? metric.metrics?.win_rate ?? 0
            : metric.metrics?.avg_score ?? 0,
        ),
      );
  }, [experimentMetrics, trendMetric]);

  const latestTrendValue = experimentTrend.length
    ? trendMetric === "win_rate"
      ? `${Math.round(experimentTrend[experimentTrend.length - 1] * 100)}%`
      : `${Math.round(experimentTrend[experimentTrend.length - 1] * 100) / 100}`
    : "—";

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
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(selectedId) => {
          router.push(`/?session=${selectedId}`);
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Overview"
            subtitle="A compact dashboard of the latest simulation, evidence, and alignment signals."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/")}
            backLabel="Back to chat"
          />
          <div className="detail__grid">
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Experiment Trend</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/experiments")}
                >
                  Open
                </button>
              </div>
              <p className="summary-card__meta">
                {latestExperiment?.name ?? "No experiment selected"}
              </p>
              <div className="summary-card__row">
                <div className="summary-card__stat">
                  <span className="summary-card__label">Latest {trendMetric.replace("_", " ")}</span>
                  <span className="summary-card__value">{latestTrendValue}</span>
                  <div className="summary-card__toggle">
                    <button
                      type="button"
                      className={`summary-card__toggle-btn ${
                        trendMetric === "win_rate" ? "is-active" : ""
                      }`}
                      onClick={() => setTrendMetric("win_rate")}
                    >
                      Win rate
                    </button>
                    <button
                      type="button"
                      className={`summary-card__toggle-btn ${
                        trendMetric === "avg_score" ? "is-active" : ""
                      }`}
                      onClick={() => setTrendMetric("avg_score")}
                    >
                      Avg score
                    </button>
                  </div>
                </div>
                <div className="summary-card__sparkline">
                  {renderSparkline(experimentTrend) ?? (
                    <span className="summary-card__empty">No trend yet.</span>
                  )}
                </div>
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Simulation Sandbox</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/simulation")}
                >
                  Open
                </button>
              </div>
              <p className="summary-card__text">
                {simulation.scenario?.trim() || lastQuery
                  ? `Scenario: ${simulation.scenario?.trim() || lastQuery}`
                  : "No scenario yet."}
              </p>
              <div className="summary-card__meta">
                <span>Runs: {simulationRuns.length}</span>
                <span>Lessons: {simulationLessons.length}</span>
                {typeof simulationRuns?.[0]?.protocol_readiness_score === "number" && (
                  <span>
                    <span
                      title="UCP readiness score based on business profile validation and platform capability intersection."
                    >
                      Protocol readiness: {simulationRuns[0].protocol_readiness_score}/100
                    </span>
                  </span>
                )}
              </div>
            </div>

            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Evidence + Research</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/evidence")}
                >
                  Open
                </button>
              </div>
              <p className="summary-card__text">
                {evidenceCount > 0
                  ? `${evidenceCount} evidence items analyzed.`
                  : "No evidence analysis yet."}
              </p>
              <div className="summary-card__meta">
                <span>Lift: {evidenceLift}</span>
                <span>Research: {alignment.research_results?.length ?? 0}</span>
              </div>
            </div>

            <div className="summary-card">
              <div className="summary-card__header">
                <h4>Alignment</h4>
                <button
                  type="button"
                  className="summary-card__link"
                  onClick={() => router.push("/alignment")}
                >
                  Open
                </button>
              </div>
              <p className="summary-card__text">
                {plan?.products?.length
                  ? `${plan.products.length} products scored.`
                  : "No alignment results yet."}
              </p>
              <div className="summary-card__meta">
                <span>
                  Score:{" "}
                  {plan?.alignment?.goal_alignment?.score !== undefined
                    ? `${Math.round(plan.alignment.goal_alignment.score * 100)}%`
                    : "—"}
                </span>
                <span>Clarifications: {alignment.clarifications?.length ?? 0}</span>
              </div>
            </div>
          </div>
          <div className="detail__note">
            Overview snapshots update after each chat run. Open any section to dive deeper.
          </div>
        </div>
      </main>
    </div>
  );
}
