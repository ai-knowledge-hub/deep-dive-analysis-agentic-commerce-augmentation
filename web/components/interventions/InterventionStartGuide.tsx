"use client";

import React, { useMemo } from "react";
import { softenOperatorText } from "../../lib/operatorDisplayLanguage";
import { formatApprovalSummary } from "./interventionDisplay";
import { sortByPriorityAndRisk } from "./interventionLogic";
import type {
  ApprovalItem,
  CommandItem,
  EscalationItem,
  PauseItem,
  Priority,
  RetryItem,
  RiskLevel,
} from "./interventionTypes";

type Guide =
  | {
      title: string;
      summary: string;
      chip: string;
      cta: string;
      tone: "attention" | "default";
      action: "approve";
      actionId: string;
    }
  | {
      title: string;
      summary: string;
      chip: string;
      cta: string;
      tone: "attention" | "default";
      action: "open" | "control";
      runId: string;
      control?: "start" | "pause" | "step";
    }
  | {
      title: string;
      summary: string;
      chip: string;
      cta: string;
      tone: "default";
      action: "runs";
    };

type Props = {
  escalations: EscalationItem[];
  commands: CommandItem[];
  approvals: ApprovalItem[];
  retries: RetryItem[];
  pauses: PauseItem[];
  busyKey: string | null;
  onApprove: (actionId: string) => void;
  onOpenRun: (runId: string) => void;
  onControlRun: (runId: string, action: "start" | "pause" | "step") => void;
  onOpenRuns: () => void;
};

type Candidate = Guide & {
  priority: Priority;
  risk: RiskLevel;
  run: ApprovalItem["run"];
};

function buildGuide({
  escalations,
  commands,
  approvals,
  retries,
  pauses,
}: Pick<Props, "escalations" | "commands" | "approvals" | "retries" | "pauses">): Guide {
  const candidates: Candidate[] = [
    ...escalations.map((item) => ({
      title: "Start with escalation",
      summary: softenOperatorText(`${item.title}. ${item.summary}`),
      chip: "Escalation",
      cta: "Open run",
      tone: "attention",
      action: "open",
      runId: item.run.id,
      priority: item.priority,
      risk: item.risk,
      run: item.run,
    }) satisfies Candidate),
    ...commands.map((item) => ({
      title: "Start with recovery work",
      summary: softenOperatorText(`${item.title}. ${item.summary}`),
      chip: "Recovery",
      cta: "Open run",
      tone: "attention",
      action: "open",
      runId: item.run.id,
      priority: item.priority,
      risk: item.risk,
      run: item.run,
    }) satisfies Candidate),
    ...approvals.map((item) => ({
      title: "Start with approval",
      summary: formatApprovalSummary(item),
      chip: "Approval",
      cta: "Approve selected action",
      tone: "attention",
      action: "approve",
      actionId: item.action.id,
      priority: item.priority,
      risk: item.risk,
      run: item.run,
    }) satisfies Candidate),
    ...retries.map((item) => ({
      title: "Start with resume",
      summary: softenOperatorText(item.summary),
      chip: "Resume",
      cta: item.control === "start" ? "Resume selected run" : "Step selected run",
      tone: "attention",
      action: "control",
      runId: item.run.id,
      control: item.control,
      priority: item.priority,
      risk: item.risk,
      run: item.run,
    }) satisfies Candidate),
    ...pauses.map((item) => ({
      title: "Start with pause decision",
      summary: softenOperatorText(item.summary),
      chip: "Pause",
      cta: "Pause selected run",
      tone: "attention",
      action: "control",
      runId: item.run.id,
      control: "pause",
      priority: item.priority,
      risk: item.risk,
      run: item.run,
    }) satisfies Candidate),
  ];

  const candidate = sortByPriorityAndRisk(candidates)[0];
  if (candidate) return candidate;

  return {
    title: "No decision needed",
    summary:
      "No intervention items are waiting. Return to Runs when you want to supervise execution.",
    chip: "Clear",
    cta: "Open runs",
    tone: "default",
    action: "runs",
  };
}

export function InterventionStartGuide({
  escalations,
  commands,
  approvals,
  retries,
  pauses,
  busyKey,
  onApprove,
  onOpenRun,
  onControlRun,
  onOpenRuns,
}: Props) {
  const guide = useMemo(
    () => buildGuide({ escalations, commands, approvals, retries, pauses }),
    [approvals, commands, escalations, pauses, retries],
  );
  const disabled =
    guide.action === "approve"
      ? busyKey === `decision:${guide.actionId}:approve` ||
        busyKey === `decision:${guide.actionId}:reject`
      : guide.action === "control" && guide.control
        ? busyKey === `control:${guide.runId}:${guide.control}`
        : false;

  return (
    <section className="control-surface control-grid__full agent-start-guide">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Start here</span>
          <h3 className="control-section__title">{guide.title}</h3>
          <div className="control-section__summary">
            Interventions keeps the highest-priority operator decision above the queue.
          </div>
        </div>
        <span
          className={`control-chip ${
            guide.tone === "attention" ? "control-chip--attention" : ""
          }`}
        >
          {guide.chip}
        </span>
      </div>
      <div className="panel__notice panel__notice--info">{guide.summary}</div>
      <div className="panel__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={disabled}
          onClick={() => {
            if (guide.action === "approve") {
              onApprove(guide.actionId);
            } else if (guide.action === "control" && guide.control) {
              onControlRun(guide.runId, guide.control);
            } else if (guide.action === "open") {
              onOpenRun(guide.runId);
            } else {
              onOpenRuns();
            }
          }}
        >
          {guide.cta}
        </button>
      </div>
    </section>
  );
}
