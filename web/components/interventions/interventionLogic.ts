import type { AgentCompensatingAction, AgentRun, AgentRunEvent } from "../../lib/types";
import type {
  ApprovalItem,
  CommandItem,
  EscalationItem,
  InterventionDetail,
  PauseItem,
  Priority,
  RetryItem,
  RiskLevel,
} from "./interventionTypes";

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

export function normalize(value: string | null | undefined): string {
  return String(value || "").trim().toLowerCase();
}

export function formatRunLabel(run: AgentRun): string {
  if (run.experiment_id) {
    return `Experiment ${run.experiment_id.slice(0, 8)}`;
  }
  return `Run ${run.id.slice(0, 8)}`;
}

export function formatEventTime(value?: string | null): string {
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

function eventRollbackGuidance(event: AgentRunEvent): string | null {
  const value = event.anchors?.rollback_guidance;
  return typeof value === "string" && value.trim() ? value : null;
}

function eventCompensatingActions(event: AgentRunEvent): AgentCompensatingAction[] {
  const value = event.anchors?.compensating_actions;
  return Array.isArray(value) ? (value as AgentCompensatingAction[]) : [];
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

export function sortByPriorityAndRisk<T extends { priority: Priority; risk: RiskLevel; run: AgentRun }>(
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

export function buildDetails(
  run: AgentRun,
  actions: InterventionDetail["actions"],
  events: AgentRunEvent[],
): InterventionDetail {
  const proposedActions = actions.filter((item) => normalize(item.status) === "proposed");
  const approvedActions = actions.filter((item) => normalize(item.status) === "approved");
  const latestPolicyEvent =
    [...events].reverse().find((item) => Boolean(item.is_policy_event)) ?? null;
  const latestFailureEvent =
    [...events].reverse().find((item) => normalize(item.status) === "failed") ?? null;

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

export function buildApprovalItems(detail: InterventionDetail): ApprovalItem[] {
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

export function buildRetryItem(detail: InterventionDetail): RetryItem | null {
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

export function buildPauseItem(detail: InterventionDetail): PauseItem | null {
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

export function buildEscalationItem(detail: InterventionDetail): EscalationItem | null {
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

export function buildCommandItems(detail: InterventionDetail): CommandItem[] {
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
        rollbackGuidance: eventRollbackGuidance(event),
        compensatingActions: eventCompensatingActions(event),
      };
    })
    .filter(
      (item) =>
        item.risk !== "low" ||
        item.event.event_type === "action_retry_proposed" ||
        item.event.event_type === "action_recovery_proposed",
    );
}
