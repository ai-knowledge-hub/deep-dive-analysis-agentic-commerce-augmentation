"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";

import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import {
  getAgentRun,
  getAgentRunEvents,
  listAgentRuns,
} from "../../lib/api";
import { buildRunsHref } from "../../lib/routes";
import type { AgentAction, AgentRun, AgentRunEvent } from "../../lib/types";

type InboxItem = {
  run: AgentRun;
  title: string;
  summary: string;
  statusLabel: string;
  kind: "failed" | "policy" | "approval";
  latestEvent?: AgentRunEvent | null;
  proposedCount?: number;
};

function formatRunLabel(run: AgentRun): string {
  if (run.experiment_id) {
    return `Experiment ${run.experiment_id.slice(0, 8)}`;
  }
  return `Run ${run.id.slice(0, 8)}`;
}

function formatEventTime(value?: string | null): string {
  if (!value) return "time unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "time unavailable";
  return parsed.toLocaleString();
}

function buildApprovalSummary(run: AgentRun, actions: AgentAction[]): InboxItem | null {
  const proposed = actions.filter(
    (item) => String(item.status || "").toLowerCase() === "proposed",
  );
  if (proposed.length === 0) return null;
  const first = proposed[0];
  return {
    run,
    kind: "approval",
    title: `${formatRunLabel(run)} needs approval`,
    summary: first?.rationale
      ? `Next proposed action is ${first.capability_name}. ${first.rationale}`
      : `There are ${proposed.length} proposed action${proposed.length === 1 ? "" : "s"} waiting for operator review.`,
    statusLabel: `${proposed.length} proposed`,
    proposedCount: proposed.length,
  };
}

function buildPolicySummary(run: AgentRun, events: AgentRunEvent[]): InboxItem | null {
  const policyEvents = events.filter((item) => Boolean(item.is_policy_event));
  const latest = policyEvents.at(-1) ?? null;
  if (!latest) return null;
  return {
    run,
    kind: "policy",
    title: `${formatRunLabel(run)} triggered a policy alert`,
    summary:
      latest.note ||
      `Policy event recorded for ${latest.capability_name ?? "unknown capability"}.`,
    statusLabel: latest.status || "policy",
    latestEvent: latest,
  };
}

function buildFailureSummary(run: AgentRun, events: AgentRunEvent[]): InboxItem | null {
  if (String(run.status || "").toLowerCase() !== "failed") return null;
  const failureEvent =
    [...events]
      .reverse()
      .find((item) => String(item.status || "").toLowerCase() === "failed") ?? null;
  return {
    run,
    kind: "failed",
    title: `${formatRunLabel(run)} failed`,
    summary:
      failureEvent?.note ||
      run.error ||
      `Run is in failed state at ${run.state ?? "unknown"} stage.`,
    statusLabel: run.state || "failed",
    latestEvent: failureEvent,
  };
}

export default function InboxPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;

  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [failedItems, setFailedItems] = useState<InboxItem[]>([]);
  const [policyItems, setPolicyItems] = useState<InboxItem[]>([]);
  const [approvalItems, setApprovalItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  const loadInbox = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await listAgentRuns({ limit: 12 }, userId);
      const nextRuns = response.runs ?? [];
      setRuns(nextRuns);

      const detailRows = await Promise.all(
        nextRuns.map(async (run) => {
          try {
            const [detail, eventData] = await Promise.all([
              getAgentRun(run.id, { limit: 50 }, userId),
              getAgentRunEvents(
                run.id,
                { limit: 50, event_type: "all" },
                userId,
              ),
            ]);
            return {
              run,
              actions: detail.actions ?? [],
              events: eventData.events ?? [],
            };
          } catch {
            return {
              run,
              actions: [],
              events: [],
            };
          }
        }),
      );

      setFailedItems(
        detailRows
          .map(({ run, events }) => buildFailureSummary(run, events))
          .filter((item): item is InboxItem => Boolean(item)),
      );
      setPolicyItems(
        detailRows
          .map(({ run, events }) => buildPolicySummary(run, events))
          .filter((item): item is InboxItem => Boolean(item)),
      );
      setApprovalItems(
        detailRows
          .map(({ run, actions }) => buildApprovalSummary(run, actions))
          .filter((item): item is InboxItem => Boolean(item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load inbox.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void loadInbox();
  }, [loadInbox]);

  const briefing = useMemo(() => {
    if (!userId) {
      return "Sign in to review failed runs, policy alerts, and approval-needed actions.";
    }
    const totalAttention =
      failedItems.length + policyItems.length + approvalItems.length;
    if (totalAttention === 0) {
      return "No urgent execution items are currently waiting for operator attention.";
    }
    return `${totalAttention} attention item${totalAttention === 1 ? "" : "s"} across ${runs.length} recent run${runs.length === 1 ? "" : "s"}: ${failedItems.length} failed, ${policyItems.length} policy, ${approvalItems.length} approval-needed.`;
  }, [
    approvalItems.length,
    failedItems.length,
    policyItems.length,
    runs.length,
    userId,
  ]);

  function renderItem(item: InboxItem) {
    return (
      <button
        key={`${item.kind}-${item.run.id}`}
        type="button"
        className="list__row inbox-list__item"
        onClick={() => router.push(buildRunsHref({ runId: item.run.id }))}
      >
        <div className="list__title">{item.title}</div>
        <div className="list__meta">
          {item.run.status ?? "unknown"} · {item.run.state ?? "unknown"} ·{" "}
          {item.statusLabel}
        </div>
        <div className="panel__muted">{item.summary}</div>
        {item.latestEvent?.timestamp ? (
          <div className="list__meta">
            Latest event: {formatEventTime(item.latestEvent.timestamp)}
          </div>
        ) : null}
      </button>
    );
  }

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
            title="Inbox"
            subtitle="Attention queue for blocked, failed, and drift-sensitive execution."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/runs")}
            backLabel="Open runs"
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => loadInbox()}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh"}
              </button>
            }
          />

          <ControlPlaneBriefing
            label="Attention"
            title="Inbox briefing"
            subtitle="The inbox is the control-plane triage layer. It should answer what needs attention now, not just what happened."
            summary={briefing}
            metrics={[
              { label: "Failed", value: failedItems.length, tone: failedItems.length > 0 ? "warning" : "default" },
              { label: "Policy", value: policyItems.length },
              { label: "Approval", value: approvalItems.length },
            ]}
            error={error}
          />

          <section className="agent-workspace inbox-workspace">
            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Failed runs</h3>
                <span className="panel__badge panel__badge--warning">
                  {failedItems.length}
                </span>
              </div>
              {failedItems.length === 0 ? (
                <div className="panel__muted">No failed runs in the recent window.</div>
              ) : (
                <div className="list">{failedItems.map(renderItem)}</div>
              )}
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Policy alerts</h3>
                <span className="panel__badge panel__badge--secondary">
                  {policyItems.length}
                </span>
              </div>
              {policyItems.length === 0 ? (
                <div className="panel__muted">No policy alerts in the recent window.</div>
              ) : (
                <div className="list">{policyItems.map(renderItem)}</div>
              )}
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Needs approval</h3>
                <span className="panel__badge panel__badge--secondary">
                  {approvalItems.length}
                </span>
              </div>
              {approvalItems.length === 0 ? (
                <div className="panel__muted">
                  No proposed actions currently waiting for operator review.
                </div>
              ) : (
                <div className="list">{approvalItems.map(renderItem)}</div>
              )}
            </section>
          </section>
        </div>
      </main>
    </div>
  );
}
