"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppUser } from "../lib/auth";

import { Sidebar } from "../components/layout/Sidebar";
import { ControlPlaneBriefing } from "../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../components/layout/DetailHeader";
import { listAgentRuns } from "../lib/api";
import type { AgentRun } from "../lib/types";

type EntryCard = {
  title: string;
  summary: string;
  href: string;
  cta: string;
  badge?: string;
};

const PRIMARY_ENTRY_CARDS: EntryCard[] = [
  {
    title: "Inbox",
    summary: "Start with blocked, failed, and approval-needed execution items.",
    href: "/inbox",
    cta: "Open inbox",
    badge: "Triage",
  },
  {
    title: "Runs",
    summary: "Inspect active and recent runs with the operator chat beside execution state.",
    href: "/runs",
    cta: "Open runs",
    badge: "Primary",
  },
  {
    title: "Interventions",
    summary: "Approve, pause, reject, resume, and manually review high-signal execution paths.",
    href: "/interventions",
    cta: "Open interventions",
    badge: "Control",
  },
  {
    title: "Insights",
    summary: "Review what changed recently and where operator attention should go next.",
    href: "/learnings",
    cta: "Open insights",
    badge: "Review",
  },
];

const SECONDARY_ENTRY_CARDS: EntryCard[] = [
  {
    title: "Open the lab",
    summary: "Use the full conversational workspace when you want to run the exploratory, human-led lab flow directly.",
    href: "/lab",
    cta: "Open lab",
  },
  {
    title: "Open overview",
    summary: "Keep the legacy cross-surface dashboard available while the control plane takes shape.",
    href: "/overview",
    cta: "Open overview",
  },
];

type ControlPlaneSnapshot = {
  attentionCount: number;
  activeCount: number;
  approvalHintCount: number;
  recentCount: number;
  recommendedHref: string;
  recommendedCta: string;
  recommendedSummary: string;
};

function buildControlPlaneSnapshot(runs: AgentRun[]): ControlPlaneSnapshot {
  const failed = runs.filter(
    (run) => String(run.status || "").toLowerCase() === "failed",
  );
  const active = runs.filter((run) =>
    ["running", "active", "executing", "paused"].includes(
      String(run.status || "").toLowerCase(),
    ),
  );
  const approvalHints = runs.filter((run) => Boolean(run.requires_approval));
  const attentionRunIds = new Set(
    [...failed, ...approvalHints].map((run) => run.id),
  );
  const attentionCount = attentionRunIds.size;

  if (attentionCount > 0) {
    return {
      attentionCount,
      activeCount: active.length,
      approvalHintCount: approvalHints.length,
      recentCount: runs.length,
      recommendedHref: failed.length > 0 ? "/inbox" : "/interventions",
      recommendedCta: failed.length > 0 ? "Review inbox" : "Review interventions",
      recommendedSummary:
        failed.length > 0
          ? `${failed.length} recent run${failed.length === 1 ? " needs" : "s need"} failure triage.`
          : `${approvalHints.length} run${approvalHints.length === 1 ? "" : "s"} may need operator approval.`,
    };
  }

  if (active.length > 0) {
    return {
      attentionCount,
      activeCount: active.length,
      approvalHintCount: approvalHints.length,
      recentCount: runs.length,
      recommendedHref: "/runs",
      recommendedCta: "Open active runs",
      recommendedSummary: `${active.length} run${active.length === 1 ? " is" : "s are"} active or paused. Continue supervision from Runs.`,
    };
  }

  return {
    attentionCount,
    activeCount: active.length,
    approvalHintCount: approvalHints.length,
    recentCount: runs.length,
    recommendedHref: runs.length > 0 ? "/learnings" : "/runs",
    recommendedCta: runs.length > 0 ? "Review insights" : "Start in runs",
    recommendedSummary:
      runs.length > 0
        ? "No immediate execution blockers found. Review what changed recently."
        : "No recent runs found. Start a supervised agent run when you are ready.",
  };
}

export default function HomePage() {
  const router = useRouter();
  const { user } = useAppUser();
  const userId = user?.id ?? null;
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  const greeting = useMemo(() => {
    const firstName = user?.firstName?.trim();
    return firstName ? `Welcome back, ${firstName}.` : "Welcome back.";
  }, [user?.firstName]);

  const snapshot = useMemo(() => buildControlPlaneSnapshot(runs), [runs]);

  const loadSnapshot = useCallback(async () => {
    if (!userId) return;
    setLoadingSnapshot(true);
    setSnapshotError(null);
    try {
      const response = await listAgentRuns({ limit: 24 }, userId);
      setRuns(response.runs ?? []);
    } catch (error) {
      setSnapshotError(
        error instanceof Error
          ? error.message
          : "Unable to load the control-plane snapshot.",
      );
    } finally {
      setLoadingSnapshot(false);
    }
  }, [userId]);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

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
            title="Control Plane"
            subtitle="The default entry for supervising autonomous execution, handling interventions, and reviewing what changed."
            onMenu={() => setSidebarOpen(true)}
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => router.push("/lab")}
              >
                Open lab
              </button>
            }
          />

          <ControlPlaneBriefing
            label="Entry"
            title="Operator briefing"
            subtitle={`${greeting} This surface is now optimized for supervision first, with the lab available when you want to drive the workflow directly.`}
            summary={snapshot.recommendedSummary}
            metrics={[
              { label: "Needs attention", value: loadingSnapshot ? "..." : snapshot.attentionCount },
              { label: "Active runs", value: loadingSnapshot ? "..." : snapshot.activeCount },
              { label: "Approval hints", value: loadingSnapshot ? "..." : snapshot.approvalHintCount },
              { label: "Recent runs", value: loadingSnapshot ? "..." : snapshot.recentCount },
            ]}
          />
          {snapshotError ? (
            <div className="panel__notice panel__notice--warning">
              Control-plane snapshot unavailable: {snapshotError}
            </div>
          ) : null}

          <section className="control-grid control-grid--full">
            <section className="control-surface control-grid__full">
              <div className="control-section__header">
                <div>
                  <span className="control-section__eyebrow">Next move</span>
                  <h3 className="control-section__title">Recommended next move</h3>
                  <div className="control-section__summary">
                    Based on the latest run statuses available to the control plane.
                  </div>
                </div>
                <span className="control-chip control-chip--attention">
                  {loadingSnapshot ? "Loading" : "Live"}
                </span>
              </div>
              <div className="panel__notice panel__notice--info">
                {snapshot.recommendedSummary}
              </div>
              <div className="panel__actions">
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => router.push(snapshot.recommendedHref)}
                >
                  {snapshot.recommendedCta}
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => loadSnapshot()}
                  disabled={loadingSnapshot}
                >
                  Refresh snapshot
                </button>
              </div>
            </section>

            <section className="control-surface">
              <div className="control-section__header">
                <div>
                  <span className="control-section__eyebrow">Primary</span>
                  <h3 className="control-section__title">Primary control plane</h3>
                </div>
                <span className="control-chip control-chip--attention">Default</span>
              </div>
              <div className="control-list">
                {PRIMARY_ENTRY_CARDS.map((item) => (
                  <div key={item.title} className="control-list__row">
                    <div className="control-list__title">{item.title}</div>
                    {item.badge ? (
                      <div className="control-list__meta">
                        <span className="control-chip">{item.badge}</span>
                      </div>
                    ) : null}
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
                  <span className="control-section__eyebrow">Guidance</span>
                  <h3 className="control-section__title">Suggested operator paths</h3>
                </div>
                <span className="control-chip">Guided</span>
              </div>
              <div className="control-list">
                <div className="control-list__row">
                  <div className="control-list__title">If execution feels unstable</div>
                  <div className="panel__muted">
                    Start in `Inbox`, move into `Interventions`, then inspect the affected run in `Runs`.
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">If execution is healthy but opaque</div>
                  <div className="panel__muted">
                    Start in `Runs`, use the operator chat for explanation, then finish in `Insights` to understand what changed.
                  </div>
                </div>
                <div className="control-list__row">
                  <div className="control-list__title">If you want to drive the system directly</div>
                  <div className="panel__muted">
                    Open the `Lab` and use the chat-led workspace for exploratory, human-guided operation.
                  </div>
                </div>
              </div>
            </section>

            <section className="control-surface">
              <div className="control-section__header">
                <div>
                  <span className="control-section__eyebrow">Bridge</span>
                  <h3 className="control-section__title">Secondary surfaces</h3>
                </div>
                <span className="control-chip">Bridge</span>
              </div>
              <div className="control-list">
                {SECONDARY_ENTRY_CARDS.map((item) => (
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
          </section>
        </div>
      </main>
    </div>
  );
}
