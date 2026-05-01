"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAppUser } from "../../lib/auth";

import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { Sidebar } from "../../components/layout/Sidebar";
import {
  controlAgentRun,
  decideAgentAction,
  getAgentRun,
  getAgentRunEvents,
  listAgentRuns,
} from "../../lib/api";
import { buildRunsHref } from "../../lib/routes";
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

type CommandItem = {
  kind: "command";
  run: AgentRun;
  event: AgentRunEvent;
  priority: Priority;
  risk: RiskLevel;
  title: string;
  summary: string;
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

function getRiskForEffect(effectClass?: string | null): RiskLevel {
  const key = normalize(effectClass);
  if (key === "write_high_risk") return "high";
  if (key === "external_side_effect") return "medium";
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

function buildCommandItems(detail: InterventionDetail): CommandItem[] {
  return detail.events
    .filter((event) => {
      const eventType = String(event.event_type || "");
      return (
        eventType.startsWith("operator_command_") ||
        eventType === "action_retry_proposed" ||
        eventType === "action_recovery_proposed"
      );
    })
    .map((event) => {
      const eventType = String(event.event_type || "");
      const command = eventType.replace(/^operator_command_/, "");
      const risk = maxRisk(
        getRiskForCapability(event.capability_name),
        getRiskForEffect(event.effect_class),
      );
      const isRetryProposal = eventType === "action_retry_proposed" || command === "retry";
      const isRecoveryProposal = eventType === "action_recovery_proposed";
      const priority: Priority =
        risk === "high" || event.status === "failed"
          ? "high"
          : isRetryProposal
            ? "medium"
            : "low";
      return {
        kind: "command" as const,
        run: detail.run,
        event,
        priority,
        risk,
        title: isRetryProposal
          ? `${formatRunLabel(detail.run)} has a retry proposal`
          : isRecoveryProposal
            ? `${formatRunLabel(detail.run)} has a recovery proposal`
            : `${formatRunLabel(detail.run)} command: ${command || eventType}`,
        summary:
          event.note ||
          (isRetryProposal
            ? "A chat-issued retry created a proposed recovery action."
            : isRecoveryProposal
              ? "A chat-issued change-plan command created a proposed recovery action."
            : "A chat-issued command changed or inspected runtime state."),
      };
    })
    .filter(
      (item) =>
        item.risk !== "low" ||
        item.event.event_type === "action_retry_proposed" ||
        item.event.event_type === "action_recovery_proposed",
    );
}

function InterventionsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAppUser();
  const userId = user?.id ?? null;
  const runIdParam = searchParams.get("run_id")?.trim() || "";

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [retries, setRetries] = useState<RetryItem[]>([]);
  const [pauses, setPauses] = useState<PauseItem[]>([]);
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [commands, setCommands] = useState<CommandItem[]>([]);
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
      setCommands(
        sortByPriorityAndRisk(
          detailRows.flatMap((detail) => buildCommandItems(detail)),
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

  const visibleApprovals = useMemo(
    () => (runIdParam ? approvals.filter((item) => item.run.id === runIdParam) : approvals),
    [approvals, runIdParam],
  );

  const visibleRetries = useMemo(
    () => (runIdParam ? retries.filter((item) => item.run.id === runIdParam) : retries),
    [retries, runIdParam],
  );

  const visiblePauses = useMemo(
    () => (runIdParam ? pauses.filter((item) => item.run.id === runIdParam) : pauses),
    [pauses, runIdParam],
  );

  const visibleEscalations = useMemo(
    () => (runIdParam ? escalations.filter((item) => item.run.id === runIdParam) : escalations),
    [escalations, runIdParam],
  );

  const visibleCommands = useMemo(
    () => (runIdParam ? commands.filter((item) => item.run.id === runIdParam) : commands),
    [commands, runIdParam],
  );

  const briefing = useMemo(() => {
    if (!userId) {
      return "Sign in to review approvals, retries, pauses, and escalation-worthy runs.";
    }
    const total =
      visibleApprovals.length +
      visibleRetries.length +
      visiblePauses.length +
      visibleEscalations.length +
      visibleCommands.length;
    if (total === 0) {
      if (runIdParam) {
        return `Run ${runIdParam.slice(0, 8)} does not currently need operator intervention.`;
      }
      return "No intervention-worthy items are waiting right now. The execution fabric is currently running without operator action.";
    }
    const prefix = runIdParam ? `Run ${runIdParam.slice(0, 8)} has ` : "";
    return `${prefix}${total} intervention item${total === 1 ? "" : "s"}: ${visibleEscalations.length} escalations, ${visibleApprovals.length} approvals, ${visibleCommands.length} command-originated item${visibleCommands.length === 1 ? "" : "s"}, ${visibleRetries.length} retry or resume action${visibleRetries.length === 1 ? "" : "s"}, and ${visiblePauses.length} active run pause decision${visiblePauses.length === 1 ? "" : "s"}.`;
  }, [
    runIdParam,
    userId,
    visibleApprovals.length,
    visibleCommands.length,
    visibleEscalations.length,
    visiblePauses.length,
    visibleRetries.length,
  ]);

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
    router.push(buildRunsHref({ runId }));
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
            title="Interventions"
            subtitle="Decision queue for approvals, retries, pauses, and manual escalation."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push(buildRunsHref({ runId: runIdParam || null }))}
            backLabel={runIdParam ? "Back to selected run" : "Open runs"}
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

          <ControlPlaneBriefing
            label="Decision"
            title="Intervention briefing"
            subtitle="Use interventions when the runtime needs an explicit human decision, not just observation."
            summary={briefing}
            metrics={[
              { label: "Escalations", value: escalations.length, tone: escalations.length > 0 ? "warning" : "default" },
              { label: "Approvals", value: approvals.length },
              { label: "Commands", value: commands.length, tone: commands.length > 0 ? "warning" : "default" },
              { label: "Retries", value: retries.length },
              { label: "Pauses", value: pauses.length },
            ]}
            status={statusMessage}
            error={error}
          />

          {runIdParam ? (
            <section className="panel__notice panel__notice--info">
              <strong>Run-scoped view:</strong> showing intervention items for run{" "}
              <span className="panel__badge panel__badge--secondary">{runIdParam.slice(0, 8)}</span>.
              <div className="panel__actions">
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => router.push(buildRunsHref({ runId: runIdParam }))}
                >
                  Return to run
                </button>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => router.push("/interventions")}
                >
                  Clear run scope
                </button>
              </div>
            </section>
          ) : null}

          <section className="agent-workspace inbox-workspace">
            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Escalations</h3>
                <span className="panel__badge panel__badge--severity-high">{visibleEscalations.length}</span>
              </div>
              {visibleEscalations.length === 0 ? (
                <div className="panel__muted">No runs currently require escalation.</div>
              ) : (
                <div className="list">
                  {visibleEscalations.map((item) => (
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
                <h3>Command-originated work</h3>
                <span className="panel__badge panel__badge--warning">{visibleCommands.length}</span>
              </div>
              {visibleCommands.length === 0 ? (
                <div className="panel__muted">No high-risk command receipts or retry proposals need intervention.</div>
              ) : (
                <div className="list">
                  {visibleCommands.map((item) => (
                    <div key={`command-${item.event.id}`} className="list__row">
                      <div className="list__title">{item.title}</div>
                      {renderMeta(item.priority, item.risk, item.run)}
                      <div className="panel__muted">{item.summary}</div>
                      <div className="agent-ops-summary">
                        <span className="panel__badge panel__badge--secondary">
                          Event: {item.event.event_type}
                        </span>
                        <span className="panel__badge panel__badge--secondary">
                          Status: {item.event.status}
                        </span>
                        <span className="panel__badge panel__badge--secondary">
                          Effect: {item.event.effect_class ?? item.risk}
                        </span>
                      </div>
                      {item.event.timestamp ? (
                        <div className="list__meta">
                          Command signal: {formatEventTime(item.event.timestamp)}
                        </div>
                      ) : null}
                      <div className="detail__actions">
                        <button
                          type="button"
                          className="button button--ghost button--sm"
                          onClick={() => openRun(item.run.id)}
                        >
                          Inspect run
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
                <span className="panel__badge panel__badge--warning">{visibleApprovals.length}</span>
              </div>
              {visibleApprovals.length === 0 ? (
                <div className="panel__muted">No proposed actions are waiting for approval.</div>
              ) : (
                <div className="list">
                  {visibleApprovals.map((item) => {
                    const approveKey = `decision:${item.action.id}:approve`;
                    const rejectKey = `decision:${item.action.id}:reject`;
                    return (
                      <div key={`approval-${item.action.id}`} className="list__row">
                        <div className="list__title">
                          {formatRunLabel(item.run)}: approve {item.action.capability_name}
                        </div>
                        {renderMeta(item.priority, item.risk, item.run)}
                        <div className="panel__muted">{item.summary}</div>
                        <div className="agent-ops-summary">
                          <span className="panel__badge panel__badge--secondary">
                            Skill: {item.action.skill_id ?? "unmapped"}
                          </span>
                          <span className="panel__badge panel__badge--secondary">
                            Tool: {item.action.tool_id ?? "legacy"}
                          </span>
                          <span className="panel__badge panel__badge--secondary">
                            Effect: {item.action.effect_class ?? item.risk}
                          </span>
                        </div>
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
                <span className="panel__badge panel__badge--secondary">{visibleRetries.length}</span>
              </div>
              {visibleRetries.length === 0 ? (
                <div className="panel__muted">No runs are ready for an operator-driven restart or next step.</div>
              ) : (
                <div className="list">
                  {visibleRetries.map((item) => {
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
                <span className="panel__badge panel__badge--secondary">{visiblePauses.length}</span>
              </div>
              {visiblePauses.length === 0 ? (
                <div className="panel__muted">No active runs currently need a pause decision.</div>
              ) : (
                <div className="list">
                  {visiblePauses.map((item) => {
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

export default function InterventionsPage() {
  return (
    <Suspense fallback={null}>
      <InterventionsPageContent />
    </Suspense>
  );
}
