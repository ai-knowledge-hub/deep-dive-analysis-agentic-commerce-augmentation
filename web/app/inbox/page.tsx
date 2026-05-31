"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppUser } from "../../lib/auth";

import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import {
  getAgentRun,
  getAgentRunEvents,
  listAgentRuns,
} from "../../lib/api";
import {
  formatOperatorActionName,
  softenOperatorText,
} from "../../lib/operatorDisplayLanguage";
import { buildInterventionsHref, buildRunsHref } from "../../lib/routes";
import type { AgentAction, AgentRun, AgentRunEvent } from "../../lib/types";

type InboxItem = {
  run: AgentRun;
  title: string;
  summary: string;
  statusLabel: string;
  kind: "failed" | "policy" | "approval" | "watching";
  urgency: "critical" | "review" | "watching";
  latestEvent?: AgentRunEvent | null;
  proposedCount?: number;
};

type InboxGroup = {
  id: string;
  title: string;
  summary: string;
  badgeTone: "warning" | "secondary";
  emptyLabel: string;
  items: InboxItem[];
};

type InboxNextAction = {
  item: InboxItem | null;
  label: string;
  summary: string;
  cta: string;
  href: string;
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
    urgency: "review",
    title: `${formatRunLabel(run)} needs approval`,
    summary: first?.rationale
      ? `Next proposed action is ${formatOperatorActionName(first.capability_name)}. ${first.rationale}`
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
    urgency: "review",
    title: `${formatRunLabel(run)} triggered a policy alert`,
    summary:
      latest.note ||
      `Policy event recorded for ${formatOperatorActionName(latest.capability_name ?? "unknown capability")}.`,
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
    urgency: "critical",
    title: `${formatRunLabel(run)} failed`,
    summary:
      failureEvent?.note ||
      run.error ||
      `Run is in failed state at ${run.state ?? "unknown"} stage.`,
    statusLabel: run.state || "failed",
    latestEvent: failureEvent,
  };
}

function buildWatchingSummary(run: AgentRun): InboxItem | null {
  const status = String(run.status || "").toLowerCase();
  if (!["running", "active", "executing", "paused"].includes(status)) return null;
  return {
    run,
    kind: "watching",
    urgency: "watching",
    title: `${formatRunLabel(run)} is ${status}`,
    summary:
      status === "paused"
        ? "Run is paused and may need a start/resume decision if work should continue."
        : `Run is currently ${status}; inspect the run if progress looks stale or opaque.`,
    statusLabel: run.state || status,
  };
}

function buildInboxNextAction(
  criticalItems: InboxItem[],
  reviewItems: InboxItem[],
  watchingItems: InboxItem[],
): InboxNextAction {
  const critical = criticalItems[0] ?? null;
  if (critical) {
    return {
      item: critical,
      label: "Start with failed work",
      summary: `${critical.title}: ${critical.summary}`,
      cta: "Review intervention",
      href: buildInterventionsHref({ runId: critical.run.id }),
    };
  }

  const review = reviewItems[0] ?? null;
  if (review) {
    return {
      item: review,
      label: review.kind === "approval" ? "Review the pending approval" : "Review the alert",
      summary: `${review.title}: ${review.summary}`,
      cta: review.kind === "approval" ? "Review approval" : "Review alert",
      href: buildInterventionsHref({ runId: review.run.id }),
    };
  }

  const watching = watchingItems[0] ?? null;
  if (watching) {
    return {
      item: watching,
      label: "Continue supervision",
      summary: `${watching.title}: ${watching.summary}`,
      cta: "Open watched run",
      href: buildRunsHref({ runId: watching.run.id }),
    };
  }

  return {
    item: null,
    label: "No action needed",
    summary: "No urgent work is waiting. Check Insights for recent outcomes or Runs when you are ready to supervise new work.",
    cta: "Review insights",
    href: "/learnings",
  };
}

export default function InboxPage() {
  const router = useRouter();
  const { user } = useAppUser();
  const userId = user?.id ?? null;

  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [criticalItems, setCriticalItems] = useState<InboxItem[]>([]);
  const [reviewItems, setReviewItems] = useState<InboxItem[]>([]);
  const [watchingItems, setWatchingItems] = useState<InboxItem[]>([]);
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

      const failedRunItems = nextRuns
        .map((run) => buildFailureSummary(run, []))
        .filter((item): item is InboxItem => Boolean(item));
      const watchingRunItems = nextRuns
        .map(buildWatchingSummary)
        .filter((item): item is InboxItem => Boolean(item));
      const approvalCandidates = nextRuns
        .filter((run) => Boolean(run.requires_approval))
        .slice(0, 8);
      const eventCandidates = nextRuns
        .filter((run) => {
          const status = String(run.status || "").toLowerCase();
          return (
            Boolean(run.requires_approval) ||
            ["failed", "running", "active", "executing", "paused"].includes(status)
          );
        })
        .slice(0, 8);

      const [detailRows, eventRows] = await Promise.all([
        Promise.all(
          approvalCandidates.map(async (run) => {
            try {
              const detail = await getAgentRun(run.id, { limit: 30 }, userId);
              return { run, actions: detail.actions ?? [] };
            } catch {
              return { run, actions: [] };
            }
          }),
        ),
        Promise.all(
          eventCandidates.map(async (run) => {
            try {
              const eventData = await getAgentRunEvents(
                run.id,
                { limit: 30, event_type: "all" },
                userId,
              );
              return { run, events: eventData.events ?? [] };
            } catch {
              return { run, events: [] };
            }
          }),
        ),
      ]);

      const failedEventItems = eventRows
        .map(({ run, events }) => buildFailureSummary(run, events))
        .filter((item): item is InboxItem => Boolean(item));
      const failedByRunId = new Map(
        [...failedRunItems, ...failedEventItems].map((item) => [item.run.id, item]),
      );

      setCriticalItems([...failedByRunId.values()]);
      setReviewItems(
        [
          ...eventRows
            .map(({ run, events }) => buildPolicySummary(run, events))
            .filter((item): item is InboxItem => Boolean(item)),
          ...detailRows
            .map(({ run, actions }) => buildApprovalSummary(run, actions))
            .filter((item): item is InboxItem => Boolean(item)),
        ].sort((a, b) => (a.kind === "policy" && b.kind !== "policy" ? -1 : 0)),
      );
      setWatchingItems(watchingRunItems.slice(0, 6));
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
    const totalAttention = criticalItems.length + reviewItems.length;
    if (totalAttention === 0) {
      return "No urgent execution items are currently waiting for operator attention.";
    }
    return `${totalAttention} attention item${totalAttention === 1 ? "" : "s"} across ${runs.length} recent run${runs.length === 1 ? "" : "s"}: ${criticalItems.length} critical, ${reviewItems.length} review-needed.`;
  }, [criticalItems.length, reviewItems.length, runs.length, userId]);

  const groups: InboxGroup[] = [
    {
      id: "critical",
      title: "Critical",
      summary: "Failed execution or blocked work that should be inspected first.",
      badgeTone: "warning",
      emptyLabel: "No critical execution items in the recent window.",
      items: criticalItems,
    },
    {
      id: "review",
      title: "Review",
      summary: "Policy alerts and proposed actions waiting for operator judgement.",
      badgeTone: "secondary",
      emptyLabel: "No policy or approval items currently need review.",
      items: reviewItems,
    },
    {
      id: "watching",
      title: "Watching",
      summary: "Active or paused runs that are not urgent but may need supervision.",
      badgeTone: "secondary",
      emptyLabel: "No active or paused runs in the recent window.",
      items: watchingItems,
    },
  ];

  const nextAction = useMemo(
    () => buildInboxNextAction(criticalItems, reviewItems, watchingItems),
    [criticalItems, reviewItems, watchingItems],
  );

  function renderItem(item: InboxItem) {
    return (
      <button
        key={`${item.kind}-${item.run.id}`}
        type="button"
        className="control-list__row inbox-list__item"
        onClick={() => router.push(buildRunsHref({ runId: item.run.id }))}
      >
        <div className="control-list__title">{item.title}</div>
        <div className="control-list__meta">
          {item.run.status ?? "unknown"} · {item.run.state ?? "unknown"} ·{" "}
          {item.statusLabel}
        </div>
        <div className="panel__muted">{softenOperatorText(item.summary)}</div>
        {item.latestEvent?.timestamp ? (
          <div className="control-list__meta">
            Latest event: {formatEventTime(item.latestEvent.timestamp)}
          </div>
        ) : null}
      </button>
    );
  }

  function renderGroup(group: InboxGroup) {
    return (
      <section key={group.id} className="control-surface">
        <div className="control-section__header">
          <div>
            <span className="control-section__eyebrow">Triage</span>
            <h3 className="control-section__title">{group.title}</h3>
            <div className="control-section__summary">{group.summary}</div>
          </div>
          <span
            className={`control-chip ${
              group.badgeTone === "warning" ? "control-chip--attention" : ""
            }`}
          >
            {group.items.length}
          </span>
        </div>
        {group.items.length === 0 ? (
          <div className="panel__muted">{group.emptyLabel}</div>
        ) : (
          <div className="control-list">{group.items.map(renderItem)}</div>
        )}
      </section>
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
              { label: "Critical", value: criticalItems.length, tone: criticalItems.length > 0 ? "warning" : "default" },
              { label: "Review", value: reviewItems.length },
              { label: "Watching", value: watchingItems.length },
            ]}
            error={error}
          />

          <section className="control-surface control-grid__full">
            <div className="control-section__header">
              <div>
                <span className="control-section__eyebrow">Start here</span>
                <h3 className="control-section__title">{nextAction.label}</h3>
                <div className="control-section__summary">
                  The inbox picks one clear first move from the highest-priority queue.
                </div>
              </div>
              <span
                className={`control-chip ${
                  nextAction.item?.urgency === "critical" ? "control-chip--attention" : ""
                }`}
              >
                {loading ? "Loading" : nextAction.item?.urgency ?? "Clear"}
              </span>
            </div>
            <div className="panel__notice panel__notice--info">
              {softenOperatorText(nextAction.summary)}
            </div>
            <div className="panel__actions">
              <button
                type="button"
                className="button button--primary"
                onClick={() => router.push(nextAction.href)}
                disabled={loading}
              >
                {nextAction.cta}
              </button>
            </div>
          </section>

          <section className="control-grid control-grid--compact control-grid--full">
            {groups.map(renderGroup)}
          </section>
        </div>
      </main>
    </div>
  );
}
