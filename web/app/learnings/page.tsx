"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppUser } from "../../lib/auth";

import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { Sidebar } from "../../components/layout/Sidebar";
import {
  getAgentRunEvents,
  getOverviewChanges,
  getOverviewSummary,
  listAgentRuns,
} from "../../lib/api";
import { buildRunsHref } from "../../lib/routes";
import type {
  AgentRun,
  AgentRunEvent,
  OverviewChangesResponse,
  OverviewSummaryResponse,
} from "../../lib/types";

type LearningSignal = {
  run: AgentRun;
  event: AgentRunEvent;
  title: string;
  summary: string;
  category: "policy" | "failure" | "execution";
};

type Recommendation = {
  title: string;
  summary: string;
  href: string;
  cta: string;
};

type LearningGroup = {
  id: string;
  title: string;
  summary: string;
  emptyLabel: string;
  signals: LearningSignal[];
};

function formatPercent(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "Unavailable";
  return `${Math.round(value * 100)}%`;
}

function formatDecimal(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "Unavailable";
  return value.toFixed(2);
}

function formatDateTime(value?: string | null): string {
  if (!value) return "time unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "time unavailable";
  return parsed.toLocaleString();
}

function formatRunLabel(run: AgentRun): string {
  if (run.experiment_id) {
    return `Experiment ${run.experiment_id.slice(0, 8)}`;
  }
  return `Run ${run.id.slice(0, 8)}`;
}

function buildSignal(run: AgentRun, event: AgentRunEvent): LearningSignal {
  const status = String(event.status || "").toLowerCase();
  const category = event.is_policy_event
    ? "policy"
    : status === "failed"
      ? "failure"
      : "execution";
  const title =
    category === "policy"
      ? `${formatRunLabel(run)} triggered a policy learning`
      : category === "failure"
        ? `${formatRunLabel(run)} exposed a failure mode`
        : `${formatRunLabel(run)} completed an execution step`;
  const summary =
    event.note ||
    `Recent ${category} signal on ${event.capability_name ?? "the active workflow"}.`;
  return { run, event, title, summary, category };
}

function isLearningCandidateRun(run: AgentRun): boolean {
  const status = String(run.status || "").toLowerCase();
  return (
    Boolean(run.requires_approval) ||
    ["failed", "completed", "executed", "running", "paused"].includes(status)
  );
}

function pickInterestingEvent(events: AgentRunEvent[]): AgentRunEvent | null {
  return (
    [...events]
      .reverse()
      .find((event) => {
        const status = String(event.status || "").toLowerCase();
        return (
          Boolean(event.is_policy_event) ||
          status === "failed" ||
          status === "executed" ||
          status === "completed"
        );
      }) ?? null
  );
}

function buildRecommendations(
  summary: OverviewSummaryResponse | null,
  changes: OverviewChangesResponse | null,
  signals: LearningSignal[],
): Recommendation[] {
  const recommendations: Recommendation[] = [];

  if ((summary?.kpis.validation.unlock_ready ?? false) === false) {
    recommendations.push({
      title: "Close validation gaps",
      summary:
        "Observed validation is still not consistently unlock-ready. Tighten validation coverage before broadening autonomous execution.",
      href: "/validation",
      cta: "Open validation",
    });
  }

  if ((summary?.kpis.protocol_readiness.score ?? 1) < 0.7) {
    recommendations.push({
      title: "Raise protocol readiness",
      summary:
        "Protocol readiness is still soft. Use readiness issues and product semantics to improve external agent interoperability.",
      href: "/alignment",
      cta: "Open alignment",
    });
  }

  if ((changes?.top_gap_signals?.length ?? 0) > 0) {
    recommendations.push({
      title: "Address top gap signals",
      summary: `The strongest gap signal right now is ${changes?.top_gap_signals?.[0]?.signal ?? "unknown"}. This should shape the next experiment or representation update.`,
      href: "/experiments",
      cta: "Open experiments",
    });
  }

  if (signals.some((signal) => signal.category === "failure" || signal.category === "policy")) {
    recommendations.push({
      title: "Review recent execution drift",
      summary:
        "Recent failed or policy-sensitive runs suggest the system still needs guided supervision on some paths. Review the intervention queue before increasing autonomy.",
      href: "/interventions",
      cta: "Open interventions",
    });
  }

  if (recommendations.length === 0) {
    recommendations.push({
      title: "Keep supervised execution moving",
      summary:
        "Current signals look stable. Use recent learnings to keep the next batch of runs moving and expand autonomy carefully.",
      href: "/runs",
      cta: "Open runs",
    });
  }

  return recommendations.slice(0, 4);
}

export default function LearningsPage() {
  const router = useRouter();
  const { user } = useAppUser();
  const userId = user?.id ?? null;

  const [summary, setSummary] = useState<OverviewSummaryResponse | null>(null);
  const [changes, setChanges] = useState<OverviewChangesResponse | null>(null);
  const [signals, setSignals] = useState<LearningSignal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  const loadLearnings = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const [summaryData, changesData, runsResponse] = await Promise.all([
        getOverviewSummary("client", 30, userId),
        getOverviewChanges("client", 30, userId),
        listAgentRuns({ limit: 8 }, userId),
      ]);
      setSummary(summaryData);
      setChanges(changesData);

      const runs = runsResponse.runs ?? [];
      const eventCandidates = runs.filter(isLearningCandidateRun).slice(0, 6);
      const eventRows = await Promise.all(
        eventCandidates.map(async (run) => {
          try {
            const response = await getAgentRunEvents(
              run.id,
              { limit: 12, event_type: "all" },
              userId,
            );
            const interesting = pickInterestingEvent(response.events ?? []);
            return interesting ? buildSignal(run, interesting) : null;
          } catch {
            return null;
          }
        }),
      );
      setSignals(eventRows.filter((item): item is LearningSignal => Boolean(item)).slice(0, 4));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load learnings.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void loadLearnings();
  }, [loadLearnings]);

  const recommendations = useMemo(
    () => buildRecommendations(summary, changes, signals),
    [changes, signals, summary],
  );
  const signalGroups = useMemo<LearningGroup[]>(
    () => [
      {
        id: "decisions",
        title: "Decision signals",
        summary: "Policy and failure signals that should shape operator judgement.",
        emptyLabel: "No policy or failure learning signals were found in recent runs.",
        signals: signals.filter(
          (signal) => signal.category === "policy" || signal.category === "failure",
        ),
      },
      {
        id: "execution",
        title: "Execution signals",
        summary: "Completed execution steps that help explain what changed.",
        emptyLabel: "No completed execution learning signals were found in recent runs.",
        signals: signals.filter((signal) => signal.category === "execution"),
      },
    ],
    [signals],
  );

  const briefing = useMemo(() => {
    if (!userId) {
      return "Sign in to review what changed across validation, experiments, and recent execution.";
    }
    const latestExperiment = changes?.latest_experiment?.name || "No recent experiment recorded";
    const latestLesson = changes?.latest_simulation_lesson?.summary || "No recent simulation lesson recorded";
    return `Latest experiment signal: ${latestExperiment}. Latest simulation learning: ${latestLesson}`;
  }, [changes, userId]);

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
        onOpenHistory={() => {}}
        showHistoryButton={false}
      />

      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Learnings"
            subtitle="What changed recently, why it matters, and where the operator should look next."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/runs")}
            backLabel="Open runs"
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => loadLearnings()}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh"}
              </button>
            }
          />

          <ControlPlaneBriefing
            label="Review"
            title="Learning briefing"
            subtitle="Learnings compress recent platform behavior into operator-readable takeaways."
            summary={briefing}
            metrics={[
              {
                label: "Decision signals",
                value: signalGroups[0]?.signals.length ?? 0,
                tone: (signalGroups[0]?.signals.length ?? 0) > 0 ? "warning" : "default",
              },
              { label: "Signals", value: signals.length },
              { label: "Follow-ups", value: recommendations.length },
            ]}
            error={error}
          />

          <section className="agent-workspace inbox-workspace">
            <section className="control-surface">
              <div className="control-section__header">
                <div>
                  <span className="control-section__eyebrow">Operator path</span>
                  <h3 className="control-section__title">Recommended follow-ups</h3>
                  <div className="control-section__summary">
                    Operator actions ordered before raw learning context.
                  </div>
                </div>
                <span className="control-chip control-chip--attention">
                  {recommendations.length}
                </span>
              </div>
              <div className="control-list">
                {recommendations.map((item) => (
                  <div key={item.title} className="control-list__row">
                    <div className="control-list__title">{item.title}</div>
                    <div className="panel__muted">{item.summary}</div>
                    <div className="detail__actions">
                      <button
                        type="button"
                        className="button button--ghost button--sm"
                        onClick={() => router.push(item.href)}
                      >
                        {item.cta}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="control-surface">
              <div className="control-section__header">
                <div>
                  <span className="control-section__eyebrow">Change log</span>
                  <h3 className="control-section__title">What changed</h3>
                </div>
                <span className="control-chip">30d</span>
              </div>
              <div className="control-list">
                <div className="control-list__row">
                  <div className="control-list__title">Latest experiment</div>
                  <div className="control-list__meta">
                    {changes?.latest_experiment?.winner_label || "No winner recorded"}
                  </div>
                  <div className="panel__muted">
                    {changes?.latest_experiment?.name || "No recent experiment has been recorded in the selected window."}
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">Latest simulation lesson</div>
                  <div className="control-list__meta">
                    Confidence {formatDecimal(changes?.latest_simulation_lesson?.confidence ?? null)}
                  </div>
                  <div className="panel__muted">
                    {changes?.latest_simulation_lesson?.summary || "No recent simulation lesson is available yet."}
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">Top gap signal</div>
                  <div className="control-list__meta">
                    {(changes?.top_gap_signals?.[0]?.count ?? 0) > 0
                      ? `${changes?.top_gap_signals?.[0]?.count} sightings`
                      : "No gap signals recorded"}
                  </div>
                  <div className="panel__muted">
                    {changes?.top_gap_signals?.[0]?.signal || "No dominant gap signal surfaced in this window."}
                  </div>
                </div>
              </div>
            </section>

            <section className="control-surface">
              <div className="control-section__header">
                <div>
                  <span className="control-section__eyebrow">Readiness</span>
                  <h3 className="control-section__title">Readiness snapshot</h3>
                </div>
                <span className="control-chip">KPIs</span>
              </div>
              <div className="control-list">
                <div className="control-list__row">
                  <div className="control-list__title">Validation accuracy</div>
                  <div className="control-list__meta">{formatPercent(summary?.kpis.validation.accuracy ?? null)}</div>
                  <div className="panel__muted">
                    Unlock ready: {summary?.kpis.validation.unlock_ready ? "Yes" : "Not yet"}
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">Protocol readiness</div>
                  <div className="control-list__meta">{formatPercent(summary?.kpis.protocol_readiness.score ?? null)}</div>
                  <div className="panel__muted">
                    Improve this before relying on external agent-to-agent execution contracts.
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">Battery coverage</div>
                  <div className="control-list__meta">{formatPercent(summary?.kpis.battery_health.coverage_score ?? null)}</div>
                  <div className="panel__muted">
                    Redundancy: {formatPercent(summary?.kpis.battery_health.redundancy_rate ?? null)}
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">Observed lift</div>
                  <div className="control-list__meta">
                    Simulation {formatDecimal(summary?.kpis.simulation.avg_lift ?? null)} · Evidence {formatDecimal(summary?.kpis.evidence.avg_lift ?? null)}
                  </div>
                  <div className="panel__muted">
                    Compare modeled improvement against evidence-backed lift before expanding autonomy.
                  </div>
                </div>
              </div>
            </section>

            {signalGroups.map((group) => (
              <section key={group.id} className="control-surface">
                <div className="control-section__header">
                  <div>
                    <span className="control-section__eyebrow">Signals</span>
                    <h3 className="control-section__title">{group.title}</h3>
                    <div className="control-section__summary">{group.summary}</div>
                  </div>
                  <span
                    className={`control-chip ${
                      group.id === "decisions" ? "control-chip--attention" : ""
                    }`}
                  >
                    {group.signals.length}
                  </span>
                </div>
                {group.signals.length === 0 ? (
                  <div className="panel__muted">{group.emptyLabel}</div>
                ) : (
                  <div className="control-list">
                    {group.signals.map((signal) => (
                      <button
                        key={`${signal.run.id}-${signal.event.id}`}
                        type="button"
                        className="control-list__row"
                        onClick={() => router.push(buildRunsHref({ runId: signal.run.id }))}
                      >
                        <div className="control-list__title">{signal.title}</div>
                        <div className="control-list__meta">
                          {signal.category} · {signal.run.status ?? "unknown"} ·{" "}
                          {formatDateTime(signal.event.timestamp)}
                        </div>
                        <div className="panel__muted">{signal.summary}</div>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            ))}
          </section>
        </div>
      </main>
    </div>
  );
}
