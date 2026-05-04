import React from "react";
import { CompensatingProposalControl } from "../agent/CompensatingProposalControl";
import { compensatingProposalKey } from "../agent/compensatingProposal";
import type { AgentCompensatingAction, AgentRun, AgentRunCommandPreflight } from "../../lib/types";
import { formatEventTime, formatRunLabel } from "./interventionLogic";
import type {
  ApprovalItem,
  CommandItem,
  EscalationItem,
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
    <div className="list__meta">
      <span className={`panel__badge ${badgeClassForPriority(priority)}`}>
        {describePriority(priority)}
      </span>{" "}
      <span className="panel__badge panel__badge--secondary">{describeRisk(risk)}</span>{" "}
      <span>{run.status ?? "unknown"}</span> · <span>{run.state ?? "unknown"}</span>
    </div>
  );
}

export function EscalationsSection({ items, onOpenRun }: EscalationsProps) {
  return (
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <h3>Escalations</h3>
        <span className="panel__badge panel__badge--severity-high">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">No runs currently require escalation.</div>
      ) : (
        <div className="list">
          {items.map((item) => (
            <div key={`escalation-${item.run.id}`} className="list__row">
              <div className="list__title">{item.title}</div>
              <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
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
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <h3>Command-originated work</h3>
        <span className="panel__badge panel__badge--warning">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">
          No high-risk command receipts or retry proposals need intervention.
        </div>
      ) : (
        <div className="list">
          {items.map((item) => {
            const compensating = item.compensatingActions?.[0] ?? null;
            const compensatingKey = compensatingProposalKey(item.event.id, compensating);
            const preflight = compensatingKey ? compensatingPreflights[compensatingKey] : null;
            const needsConfirm =
              compensatingKey && pendingCompensatingKey === compensatingKey;
            return (
              <div key={`command-${item.event.id}`} className="list__row">
                <div className="list__title">{item.title}</div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{item.summary}</div>
                {item.rollbackGuidance ? (
                  <div className="list__meta">Rollback: {item.rollbackGuidance}</div>
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
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <h3>Approvals</h3>
        <span className="panel__badge panel__badge--warning">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">No proposed actions are waiting for approval.</div>
      ) : (
        <div className="list">
          {items.map((item) => {
            const approveKey = `decision:${item.action.id}:approve`;
            const rejectKey = `decision:${item.action.id}:reject`;
            return (
              <div key={`approval-${item.action.id}`} className="list__row">
                <div className="list__title">
                  {formatRunLabel(item.run)}: approve {item.action.capability_name}
                </div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
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
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <h3>Retries and resumes</h3>
        <span className="panel__badge panel__badge--secondary">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">
          No runs are ready for an operator-driven restart or next step.
        </div>
      ) : (
        <div className="list">
          {items.map((item) => {
            const controlKey = `control:${item.run.id}:${item.control}`;
            return (
              <div key={`retry-${item.run.id}`} className="list__row">
                <div className="list__title">{item.title}</div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{item.summary}</div>
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
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <h3>Pauses</h3>
        <span className="panel__badge panel__badge--secondary">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="panel__muted">No active runs currently need a pause decision.</div>
      ) : (
        <div className="list">
          {items.map((item) => {
            const pauseKey = `control:${item.run.id}:pause`;
            const cancelKey = `control:${item.run.id}:cancel`;
            return (
              <div key={`pause-${item.run.id}`} className="list__row">
                <div className="list__title">{formatRunLabel(item.run)} is executing</div>
                <InterventionMeta priority={item.priority} risk={item.risk} run={item.run} />
                <div className="panel__muted">{item.summary}</div>
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
