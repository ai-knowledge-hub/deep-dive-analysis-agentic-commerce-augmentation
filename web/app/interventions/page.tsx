"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";

import { DetailHeader } from "../../components/layout/DetailHeader";
import { Sidebar } from "../../components/layout/Sidebar";
import {
  controlAgentRun,
  decideAgentAction,
  getAgentRun,
  getAgentRunEvents,
  listAgentRuns,
} from "../../lib/api";
import type { AgentAction, AgentRun, AgentRunEvent } from "../../lib/types";

type Priority = "critical" | "high" | "medium" | "low";
type RiskLevel = "high" | "medium" | "low";

type InterventionDetail = {
  run: AgentRun;
  actions: AgentAction[];
  events: AgentRunEvent[];
  latestPolicyEvent: AgentRunEvent | null;
  latestFailureEvent: AgentRunEvent | null;
  proposedActions: AgentAction[];
  approvedActions: AgentAction[];
};

type ApprovalItem = {
  kind: "approval";
  run: AgentRun;
  action: AgentAction;
  priority: Priority;
  risk: RiskLevel;
  summary: string;
  reason: string;
};

type RetryItem = {
  kind: "retry";
  run: AgentRun;
  control: "start" | "step";
  priority: Priority;
  risk: RiskLevel;
  title: string;
  summary: string;
};

type PauseItem = {
  kind: "pause";
  run: AgentRun;
  priority: Priority;
  risk: RiskLevel;
  summary: string;
};

type EscalationItem = {
  kind: "escalation";
  run: AgentRun;
  priority: Priority;
  risk: RiskLevel;
  title: string;
  summary: string;
  latestEvent?: AgentRunEvent | null;
};

const HIGH_RISK_CAPABILITIES = new Set([
  "promote_variant_prod",
  "publish_copy_revision",
]);

const MEDIUM_RISK_CAPABILITIES = new Set([
  "promote_variant_lab",
  "request_synthetic_validation",
  "run_variant",
]);

const ACTIVE_RUN_STATUSES = new Set(["running", "executing", "in_progress", "started"]);
const TERMINAL_RUN_STATUSES = new Set(["completed", "canceled", "cancelled", "failed"]);

function normalize(value: string | null | undefined): string {
  return String(value || "").trim().toLowerCase();
}

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

function getRiskForCapability(capabilityName?: string | null): RiskLevel {
  const key = String(capabilityName || "");
  if (HIGH_RISK_CAPABILITIES.has(key)) return "high";
  if (MEDIUM_RISK_CAPABILITIES.has(key)) return "medium";
  return "low";
}

function maxRisk(left: RiskLevel, right: RiskLevel): RiskLevel {
  const order: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2 };
  return order[left] >= order[right] ? left : right;
}

function badgeClassForPriority(priority: Priority): string {
  if (priority === "critical") return "panel__badge--severity-high";
  if (priority === "high") return "panel__badge--warning";
  if (priority === "medium") return "panel__badge--severity-medium";
  return "panel__badge--severity-low";
}

function describePriority(priority: Priority): string {
  if (priority === "critical") return "Critical";
  if (priority === "high") return "High urgency";
  if (priority === "medium") return "Medium urgency";
  return "Low urgency";
}

function describeRisk(risk: RiskLevel): string {
  if (risk === "high") return "High risk";
  if (risk === "medium") return "Medium risk";
  return "Low risk";
}

function comparePriority(left: Priority, right: Priority): number {
  const order: Record<Priority, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
  };
  return order[left] - order[right];
}

function compareRisk(left: RiskLevel, right: RiskLevel): number {
  const order: Record<RiskLevel, number> = {
    high: 0,
    medium: 1,
    low: 2,
  };
  return order[left] - order[right];
}

function sortByPriorityAndRisk<T extends { priority: Priority; risk: RiskLevel; run: AgentRun }>(
  items: T[],
): T[] {
  return [...items].sort((a, b) => {
    const priorityDiff = comparePriority(a.priority, b.priority);
    if (priorityDiff !== 0) return priorityDiff;
    const riskDiff = compareRisk(a.risk, b.risk);
    if (riskDiff !== 0) return riskDiff;
    return (b.run.updated_at || "").localeCompare(a.run.updated_at || "");
  });
}

function buildDetails(run: AgentRun, actions: AgentAction[], events: AgentRunEvent[]): InterventionDetail {
  const proposedActions = actions.filter((item) => normalize(item.status) === "proposed");
  const approvedActions = actions.filter((item) => normalize(item.status) === "approved");
  const latestPolicyEvent = [...events]
    .reverse()
    .find((item) => Boolean(item.is_policy_event)) ?? null;
  const latestFailureEvent = [...events]
    .reverse()
    .find((item) => normalize(item.status) === "failed") ?? null;

  return {
    run,
    actions,
    events,
    proposedActions,
    approvedActions,
    latestPolicyEvent,
    latestFailureEvent,
  };
}

function buildApprovalItems(detail: InterventionDetail): ApprovalItem[] {
  const runStatus = normalize(detail.run.status);
  return detail.proposedActions.map((action) => {
    const risk = getRiskForCapability(action.capability_name);
    const priority: Priority =
      runStatus === "failed" || detail.latestPolicyEvent
        ? "critical"
        : risk === "high"
          ? "high"
          : "medium";

    return {
      kind: "approval",
      run: detail.run,
      action,
      priority,
      risk,
      summary: action.rationale
        ? `${action.capability_name} is waiting for approval. ${action.rationale}`
        : `${action.capability_name} is waiting for operator approval before execution.`,
      reason:
        detail.latestPolicyEvent?.note ||
        detail.latestFailureEvent?.note ||
        (risk === "high"
          ? "This action has a higher side-effect profile and should be reviewed carefully."
          : "Approve when the run context and execution goal still look correct."),
    };
  });
}

function buildRetryItem(detail: InterventionDetail): RetryItem | null {
  const runStatus = normalize(detail.run.status);
  if (TERMINAL_RUN_STATUSES.has(runStatus)) {
    return null;
  }
  if (detail.approvedActions.length === 0) {
    return null;
  }

  const control = runStatus === "planned" || runStatus === "paused" ? "start" : "step";
  const risk = detail.approvedActions.reduce<RiskLevel>((current, action) => {
    return maxRisk(current, getRiskForCapability(action.capability_name));
  }, "low");
  const priority: Priority = detail.latestPolicyEvent ? "high" : "medium";

  return {
    kind: "retry",
    run: detail.run,
    control,
    priority,
    risk,
    title:
      control === "start"
        ? `${formatRunLabel(detail.run)} is ready to resume`
        : `${formatRunLabel(detail.run)} is ready for the next execution step`,
    summary:
      control === "start"
        ? `${detail.approvedActions.length} approved action${detail.approvedActions.length === 1 ? "" : "s"} are queued. Resume the run when you are comfortable with the current approvals.`
        : `${detail.approvedActions.length} approved action${detail.approvedActions.length === 1 ? "" : "s"} are queued. Step the run forward to continue execution deliberately.`,
  };
}

function buildPauseItem(detail: InterventionDetail): PauseItem | null {
  const runStatus = normalize(detail.run.status);
  if (!ACTIVE_RUN_STATUSES.has(runStatus)) {
    return null;
  }
  const risk = detail.latestPolicyEvent ? "high" : "medium";
  const priority: Priority = detail.latestPolicyEvent ? "critical" : "high";
  return {
    kind: "pause",
    run: detail.run,
    priority,
    risk,
    summary:
      detail.latestPolicyEvent?.note ||
      "Run is currently executing. Pause if you need to inspect outputs, budget use, or policy fit before continuing.",
  };
}

function buildEscalationItem(detail: InterventionDetail): EscalationItem | null {
  const runStatus = normalize(detail.run.status);
  if (runStatus !== "failed" && !detail.latestPolicyEvent) {
    return null;
  }
  const riskFromActions = detail.proposedActions.reduce<RiskLevel>((current, action) => {
    return maxRisk(current, getRiskForCapability(action.capability_name));
  }, "low");
  const risk = detail.latestPolicyEvent ? maxRisk(riskFromActions, "high") : riskFromActions;
  const latestEvent = detail.latestPolicyEvent || detail.latestFailureEvent;
  return {
    kind: "escalation",
    run: detail.run,
    priority: runStatus === "failed" ? "critical" : "high",
    risk,
    title:
      runStatus === "failed"
        ? `${formatRunLabel(detail.run)} needs manual recovery`
        : `${formatRunLabel(detail.run)} needs policy review`,
    summary:
      latestEvent?.note ||
      detail.run.error ||
      "Operator review is needed before this run should continue.",
    latestEvent,
  };
}

export default function InterventionsPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [retries, setRetries] = useState<RetryItem[]>([]);
  const [pauses, setPauses] = useState<PauseItem[]>([]);
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const loadInterventions = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await listAgentRuns({ limit: 16 }, userId);
      const nextRuns = response.runs ?? [];
      const detailRows = await Promise.all(
        nextRuns.map(async (run) => {
          try {
            const [detail, eventData] = await Promise.all([
              getAgentRun(run.id, { limit: 50 }, userId),
              getAgentRunEvents(run.id, { limit: 50, event_type: "all" }, userId),
            ]);
            return buildDetails(run, detail.actions ?? [], eventData.events ?? []);
          } catch {
            return buildDetails(run, [], []);
          }
        }),
      );

      setApprovals(
        sortByPriorityAndRisk(
          detailRows.flatMap((detail) => buildApprovalItems(detail)),
        ),
      );
      setRetries(
        sortByPriorityAndRisk(
          detailRows
            .map((detail) => buildRetryItem(detail))
            .filter((item): item is RetryItem => Boolean(item)),
        ),
      );
      setPauses(
        sortByPriorityAndRisk(
          detailRows
            .map((detail) => buildPauseItem(detail))
            .filter((item): item is PauseItem => Boolean(item)),
        ),
      );
      setEscalations(
        sortByPriorityAndRisk(
          detailRows
            .map((detail) => buildEscalationItem(detail))
            .filter((item): item is EscalationItem => Boolean(item)),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load interventions.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void loadInterventions();
  }, [loadInterventions]);

  const briefing = useMemo(() => {
    if (!userId) {
      return "Sign in to review approvals, retries, pauses, and escalation-worthy runs.";
    }
    const total = approvals.length + retries.length + pauses.length + escalations.length;
    if (total === 0) {
      return "No intervention-worthy items are waiting right now. The execution fabric is currently running without operator action.";
    }
    return `${total} intervention item${total === 1 ? "" : "s"}: ${escalations.length} escalations, ${approvals.length} approvals, ${retries.length} retry or resume action${retries.length === 1 ? "" : "s"}, and ${pauses.length} active run pause decision${pauses.length === 1 ? "" : "s"}.`;
  }, [approvals.length, escalations.length, pauses.length, retries.length, userId]);

  const handleDecision = useCallback(
    async (actionId: string, decision: "approve" | "reject") => {
      if (!userId) return;
      setBusyKey(`decision:${actionId}:${decision}`);
      setError(null);
      setStatusMessage(null);
      try {
        await decideAgentAction(actionId, { decision }, userId);
        setStatusMessage(
          decision === "approve"
            ? "Action approved. The queue has been refreshed."
            : "Action rejected. The queue has been refreshed.",
        );
        await loadInterventions();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to update action.");
      } finally {
        setBusyKey(null);
      }
    },
    [loadInterventions, userId],
  );

  const handleRunControl = useCallback(
    async (runId: string, action: "start" | "pause" | "cancel" | "step") => {
      if (!userId) return;
      setBusyKey(`control:${runId}:${action}`);
      setError(null);
      setStatusMessage(null);
      try {
        const response = await controlAgentRun(runId, action, userId);
        setStatusMessage(
          response.message ||
            (action === "pause"
              ? "Run paused and the queue has been refreshed."
              : action === "cancel"
                ? "Run canceled and the queue has been refreshed."
                : action === "start"
                  ? "Run resumed and the queue has been refreshed."
                  : "Run stepped forward and the queue has been refreshed."),
        );
        await loadInterventions();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to control run.");
      } finally {
        setBusyKey(null);
      }
    },
    [loadInterventions, userId],
  );

  function renderMeta(priority: Priority, risk: RiskLevel, run: AgentRun) {
    return (
      <div className="list__meta">
        <span className={`panel__badge ${badgeClassForPriority(priority)}`}>
          {describePriority(priority)}
        </span>{" "}
        <span className="panel__badge panel__badge--secondary">{describeRisk(risk)}</span>{" "}
        <span>{run.status ?? "unknown"}</span> · <span>{run.state ?? "unknown"}</span>
      </div>
    );
  }

  function openRun(runId: string) {
    router.push(`/runs?run_id=${runId}`);
  }

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
        onOpenHistory={() => {}}
        showHistoryButton={false}
      />

      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Interventions"
            subtitle="Decision queue for approvals, retries, pauses, and manual escalation."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/runs")}
            backLabel="Open runs"
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => loadInterventions()}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh"}
              </button>
            }
          />

          <section className="panel__card panel__card--secondary panel__card--full-row">
            <div className="panel__header">
              <div className="panel__meta panel__meta--stack">
                <h3>Operator briefing</h3>
                <div className="panel__subtitle">
                  Use interventions when the runtime needs an explicit human decision, not just observation.
                </div>
              </div>
            </div>
            <div className="panel__notice panel__notice--info">{briefing}</div>
            {statusMessage ? <div className="panel__notice panel__notice--info">{statusMessage}</div> : null}
            {error ? <div className="panel__notice panel__notice--error">{error}</div> : null}
          </section>

          <section className="agent-workspace inbox-workspace">
            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Escalations</h3>
                <span className="panel__badge panel__badge--severity-high">{escalations.length}</span>
              </div>
              {escalations.length === 0 ? (
                <div className="panel__muted">No runs currently require escalation.</div>
              ) : (
                <div className="list">
                  {escalations.map((item) => (
                    <div key={`escalation-${item.run.id}`} className="list__row">
                      <div className="list__title">{item.title}</div>
                      {renderMeta(item.priority, item.risk, item.run)}
                      <div className="panel__muted">{item.summary}</div>
                      {item.latestEvent?.timestamp ? (
                        <div className="list__meta">
                          Latest signal: {formatEventTime(item.latestEvent.timestamp)}
                        </div>
                      ) : null}
                      <div className="detail__actions">
                        <button
                          type="button"
                          className="button button--ghost button--sm"
                          onClick={() => openRun(item.run.id)}
                        >
                          Open run
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Approvals</h3>
                <span className="panel__badge panel__badge--warning">{approvals.length}</span>
              </div>
              {approvals.length === 0 ? (
                <div className="panel__muted">No proposed actions are waiting for approval.</div>
              ) : (
                <div className="list">
                  {approvals.map((item) => {
                    const approveKey = `decision:${item.action.id}:approve`;
                    const rejectKey = `decision:${item.action.id}:reject`;
                    return (
                      <div key={`approval-${item.action.id}`} className="list__row">
                        <div className="list__title">
                          {formatRunLabel(item.run)}: approve {item.action.capability_name}
                        </div>
                        {renderMeta(item.priority, item.risk, item.run)}
                        <div className="panel__muted">{item.summary}</div>
                        <div className="list__meta">{item.reason}</div>
                        <div className="detail__actions">
                          <button
                            type="button"
                            className="button button--primary button--sm"
                            onClick={() => void handleDecision(item.action.id, "approve")}
                            disabled={busyKey === approveKey || busyKey === rejectKey}
                          >
                            {busyKey === approveKey ? "Approving..." : "Approve"}
                          </button>
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => void handleDecision(item.action.id, "reject")}
                            disabled={busyKey === approveKey || busyKey === rejectKey}
                          >
                            {busyKey === rejectKey ? "Rejecting..." : "Reject"}
                          </button>
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => openRun(item.run.id)}
                          >
                            Inspect run
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Retries and resumes</h3>
                <span className="panel__badge panel__badge--secondary">{retries.length}</span>
              </div>
              {retries.length === 0 ? (
                <div className="panel__muted">No runs are ready for an operator-driven restart or next step.</div>
              ) : (
                <div className="list">
                  {retries.map((item) => {
                    const controlKey = `control:${item.run.id}:${item.control}`;
                    return (
                      <div key={`retry-${item.run.id}`} className="list__row">
                        <div className="list__title">{item.title}</div>
                        {renderMeta(item.priority, item.risk, item.run)}
                        <div className="panel__muted">{item.summary}</div>
                        <div className="detail__actions">
                          <button
                            type="button"
                            className="button button--primary button--sm"
                            onClick={() => void handleRunControl(item.run.id, item.control)}
                            disabled={busyKey === controlKey}
                          >
                            {busyKey === controlKey
                              ? item.control === "start"
                                ? "Resuming..."
                                : "Stepping..."
                              : item.control === "start"
                                ? "Resume run"
                                : "Step run"}
                          </button>
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => openRun(item.run.id)}
                          >
                            Inspect run
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Pauses</h3>
                <span className="panel__badge panel__badge--secondary">{pauses.length}</span>
              </div>
              {pauses.length === 0 ? (
                <div className="panel__muted">No active runs currently need a pause decision.</div>
              ) : (
                <div className="list">
                  {pauses.map((item) => {
                    const pauseKey = `control:${item.run.id}:pause`;
                    const cancelKey = `control:${item.run.id}:cancel`;
                    return (
                      <div key={`pause-${item.run.id}`} className="list__row">
                        <div className="list__title">{formatRunLabel(item.run)} is executing</div>
                        {renderMeta(item.priority, item.risk, item.run)}
                        <div className="panel__muted">{item.summary}</div>
                        <div className="detail__actions">
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => void handleRunControl(item.run.id, "pause")}
                            disabled={busyKey === pauseKey || busyKey === cancelKey}
                          >
                            {busyKey === pauseKey ? "Pausing..." : "Pause run"}
                          </button>
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => void handleRunControl(item.run.id, "cancel")}
                            disabled={busyKey === pauseKey || busyKey === cancelKey}
                          >
                            {busyKey === cancelKey ? "Canceling..." : "Cancel run"}
                          </button>
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => openRun(item.run.id)}
                          >
                            Inspect run
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </section>
        </div>
      </main>
    </div>
  );
}
