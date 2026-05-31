import React from "react";
import { CompensatingProposalControl } from "../agent/CompensatingProposalControl";
import { compensatingProposalKey } from "../agent/compensatingProposal";
import {
  formatOperatorIdentifier,
  softenOperatorText,
} from "../../lib/operatorDisplayLanguage";
import type { AgentCompensatingAction, AgentRun, AgentRunCommandPreflight } from "../../lib/types";
import { formatActionLabel, formatApprovalSummary } from "./interventionDisplay";
import { formatEventTime, formatRunLabel } from "./interventionLogic";
import type {
  ApprovalItem,
  CommandItem,
  EscalationItem,
  HarnessAwareIntervention,
  PauseItem,
  Priority,
  RetryItem,
  RiskLevel,
} from "./interventionTypes";

type EscalationsProps = {
  items: EscalationItem[];
  onOpenRun: (runId: string) => void;
};

type CommandsProps = {
  items: CommandItem[];
  busyKey: string | null;
  pendingCompensatingKey: string | null;
  compensatingPreflights: Record<string, AgentRunCommandPreflight>;
  onCreateCompensatingAction: (
    item: CommandItem,
    recommendation: AgentCompensatingAction,
  ) => void | Promise<void>;
  onOpenRun: (runId: string) => void;
};

type ApprovalsProps = {
  items: ApprovalItem[];
  busyKey: string | null;
  onDecision: (actionId: string, decision: "approve" | "reject") => void | Promise<void>;
  onOpenRun: (runId: string) => void;
};

type RetriesProps = {
  items: RetryItem[];
  busyKey: string | null;
  onRunControl: (runId: string, action: "start" | "step") => void | Promise<void>;
  onOpenRun: (runId: string) => void;
};

type PausesProps = {
  items: PauseItem[];
  busyKey: string | null;
  onRunControl: (runId: string, action: "pause" | "cancel") => void | Promise<void>;
  onOpenRun: (runId: string) => void;
};

function badgeClassForPriority(priority: Priority): string {
  if (priority === "critical" || priority === "high") {
    return "control-chip control-chip--attention";
  }
  return "control-chip";
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

function formatHarnessValue(value?: string | null): string {
  return softenOperatorText(String(value || "not set").replaceAll("_", " "));
}

function fallbackOrder(item: HarnessAwareIntervention): string {
  return (
    item.harness?.fallback_order?.map(formatHarnessValue).join(" -> ") ||
    "recovery workflow or operator review"
  );
}

function HarnessPosture({
  item,
  focus,
}: {
  item: HarnessAwareIntervention & { run: AgentRun };
  focus: "approval" | "retry" | "fallback" | "stop";
}) {
  const harnessName = softenOperatorText(
    item.harness?.name ?? item.run.harness_id ?? "operator supervised",
  );
  const focusEntry =
    focus === "approval"
      ? { label: "Approval", value: formatHarnessValue(item.harness?.approval_strategy) }
      : focus === "retry"
        ? { label: "Retry", value: formatHarnessValue(item.harness?.retry_strategy) }
        : focus === "stop"
          ? {
              label: "Stops",
              value:
                item.harness?.stopping_conditions?.map(formatHarnessValue).join(" · ") ||
                "operator review",
            }
          : { label: "Fallback", value: fallbackOrder(item) };

  return (
    <div className="panel__meta-strip panel__meta-strip--flat">
      <div>
        <strong>Execution posture</strong>: {harnessName}
      </div>
      <div>
        <strong>{focusEntry.label}</strong>: {focusEntry.value}
      </div>
      <div>
        <strong>Mode</strong>: {formatHarnessValue(item.run.run_mode)}
      </div>
      <div>
        <strong>Safety rules</strong>: {formatHarnessValue(item.run.policy_profile_id)}
      </div>
    </div>
  );
}

function InterventionMeta({
  priority,
  risk,
  run,
}: {
  priority: Priority;
  risk: RiskLevel;
  run: AgentRun;
}) {
  return (
    <div className="intervention-meta">
      <span className={badgeClassForPriority(priority)}>
        {describePriority(priority)}
      </span>
      <span className="control-chip">{describeRisk(risk)}</span>
      <span>{run.status ?? "unknown"}</span> ·{" "}
      <span>{formatOperatorIdentifier(run.state)}</span>
    </div>
  );
}

function ApprovalOutcomeSummary({ item }: { item: ApprovalItem }) {
  const actionName = formatActionLabel(item.action.capability_name);
  return (
    <div className="panel__notice panel__notice--info">
      <div>
        <strong>Approve:</strong> the run can continue with {actionName}.
      </div>
      <div>
        <strong>Reject:</strong> the run stays waiting and needs a safer next action.
      </div>
    </div>
  );
}

function ResumeOutcomeSummary({ item }: { item: RetryItem }) {
  const primaryLabel = item.control === "start" ? "Resume" : "Step";
  const primaryText =
    item.control === "start"
      ? "the run continues with the approved work."
      : "the run moves forward by one supervised step.";
  return (
    <div className="panel__notice panel__notice--info">
      <div>
        <strong>{primaryLabel}:</strong> {primaryText}
      </div>
      <div>
        <strong>Inspect:</strong> review the run before moving it forward.
      </div>
    </div>
  );
}

function PauseOutcomeSummary() {
  return (
    <div className="panel__notice panel__notice--info">
      <div>
        <strong>Pause:</strong> the run stops before more work continues.
      </div>
      <div>
        <strong>Cancel:</strong> the run ends and future work needs a new run.
      </div>
    </div>
  );
}

export function EscalationsSection({ items, onOpenRun }: EscalationsProps) {
  return (
    <section className="control-surface intervention-section">
      <div className="control-section__header">
        <h3>Escalations</h3>
        <span className="control-chip control-chip--attention">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">No runs currently require escalation.</div>
      ) : (
        <div className="intervention-list">
          {items.map((item) => (
            <div key={`escalation-${item.run.id}`} className="intervention-item">
              <div className="list__title">{item.title}</div>
              <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
              <div className="panel__muted">{softenOperatorText(item.summary)}</div>
              <HarnessPosture item={item} focus="fallback" />
              {item.latestEvent?.timestamp ? (
                <div className="list__meta">
                  Latest signal: {formatEventTime(item.latestEvent.timestamp)}
                </div>
              ) : null}
              <div className="detail__actions">
                <button
                  type="button"
                  className="button button--ghost button--sm"
                  onClick={() => onOpenRun(item.run.id)}
                >
                  Open run
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function CommandWorkSection({
  items,
  busyKey,
  pendingCompensatingKey,
  compensatingPreflights,
  onCreateCompensatingAction,
  onOpenRun,
}: CommandsProps) {
  return (
    <section className="control-surface intervention-section">
      <div className="control-section__header">
        <h3>Recovery work</h3>
        <span className="control-chip control-chip--attention">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">
          No high-risk recovery proposals need intervention.
        </div>
      ) : (
        <div className="intervention-list">
          {items.map((item) => {
            const compensating = item.compensatingActions?.[0] ?? null;
            const compensatingKey = compensatingProposalKey(item.event.id, compensating);
            const preflight = compensatingKey ? compensatingPreflights[compensatingKey] : null;
            const needsConfirm =
              compensatingKey && pendingCompensatingKey === compensatingKey;
            return (
              <div key={`command-${item.event.id}`} className="intervention-item">
                <div className="list__title">{item.title}</div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{softenOperatorText(item.summary)}</div>
                <HarnessPosture item={item} focus="fallback" />
                {item.rollbackGuidance ? (
                  <div className="list__meta">
                    Recovery path: {softenOperatorText(item.rollbackGuidance)}
                  </div>
                ) : null}
                <CompensatingProposalControl
                  recommendation={compensating}
                  event={item.event}
                  risk={item.risk}
                  preflight={preflight}
                  needsConfirmation={Boolean(needsConfirm)}
                  busy={Boolean(compensatingKey && busyKey === compensatingKey)}
                  onCreate={() => {
                    if (compensating) {
                      void onCreateCompensatingAction(item, compensating);
                    }
                  }}
                  onInspectRun={() => onOpenRun(item.run.id)}
                />
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function ApprovalsSection({ items, busyKey, onDecision, onOpenRun }: ApprovalsProps) {
  return (
    <section className="control-surface intervention-section">
      <div className="control-section__header">
        <h3>Approvals</h3>
        <span className="control-chip control-chip--attention">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">No proposed actions are waiting for approval.</div>
      ) : (
        <div className="intervention-list">
          {items.map((item) => {
            const approveKey = `decision:${item.action.id}:approve`;
            const rejectKey = `decision:${item.action.id}:reject`;
            return (
              <div key={`approval-${item.action.id}`} className="intervention-item">
                <div className="list__title">
                  {formatRunLabel(item.run)}: approve{" "}
                  {formatActionLabel(item.action.capability_name)}
                </div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{formatApprovalSummary(item)}</div>
                <HarnessPosture item={item} focus="approval" />
                <div className="list__meta">{item.reason}</div>
                <ApprovalOutcomeSummary item={item} />
                <div className="detail__actions">
                  <button
                    type="button"
                    className="button button--primary button--sm"
                    onClick={() => void onDecision(item.action.id, "approve")}
                    disabled={busyKey === approveKey || busyKey === rejectKey}
                  >
                    {busyKey === approveKey ? "Approving..." : "Approve"}
                  </button>
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => void onDecision(item.action.id, "reject")}
                    disabled={busyKey === approveKey || busyKey === rejectKey}
                  >
                    {busyKey === rejectKey ? "Rejecting..." : "Reject"}
                  </button>
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => onOpenRun(item.run.id)}
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
  );
}

export function RetriesSection({ items, busyKey, onRunControl, onOpenRun }: RetriesProps) {
  return (
    <section className="control-surface intervention-section">
      <div className="control-section__header">
        <h3>Retries and resumes</h3>
        <span className="control-chip">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">
          No runs are ready for an operator-driven restart or next step.
        </div>
      ) : (
        <div className="intervention-list">
          {items.map((item) => {
            const controlKey = `control:${item.run.id}:${item.control}`;
            return (
              <div key={`retry-${item.run.id}`} className="intervention-item">
                <div className="list__title">{item.title}</div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{softenOperatorText(item.summary)}</div>
                <HarnessPosture item={item} focus="retry" />
                <ResumeOutcomeSummary item={item} />
                <div className="detail__actions">
                  <button
                    type="button"
                    className="button button--primary button--sm"
                    onClick={() => void onRunControl(item.run.id, item.control)}
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
                    onClick={() => onOpenRun(item.run.id)}
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
  );
}

export function PausesSection({ items, busyKey, onRunControl, onOpenRun }: PausesProps) {
  return (
    <section className="control-surface intervention-section">
      <div className="control-section__header">
        <h3>Pauses</h3>
        <span className="control-chip">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">No active runs currently need a pause decision.</div>
      ) : (
        <div className="intervention-list">
          {items.map((item) => {
            const pauseKey = `control:${item.run.id}:pause`;
            const cancelKey = `control:${item.run.id}:cancel`;
            return (
              <div key={`pause-${item.run.id}`} className="intervention-item">
                <div className="list__title">{formatRunLabel(item.run)} is executing</div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{softenOperatorText(item.summary)}</div>
                <HarnessPosture item={item} focus="stop" />
                <PauseOutcomeSummary />
                <div className="detail__actions">
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => void onRunControl(item.run.id, "pause")}
                    disabled={busyKey === pauseKey || busyKey === cancelKey}
                  >
                    {busyKey === pauseKey ? "Pausing..." : "Pause run"}
                  </button>
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => void onRunControl(item.run.id, "cancel")}
                    disabled={busyKey === pauseKey || busyKey === cancelKey}
                  >
                    {busyKey === cancelKey ? "Canceling..." : "Cancel run"}
                  </button>
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => onOpenRun(item.run.id)}
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
  );
}
