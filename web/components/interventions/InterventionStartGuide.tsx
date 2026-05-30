"use client";

import React, { useMemo } from "react";
import { softenOperatorText } from "../../lib/operatorDisplayLanguage";
import type {
  ApprovalItem,
  CommandItem,
  EscalationItem,
  PauseItem,
  RetryItem,
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

function buildGuide({
  escalations,
  commands,
  approvals,
  retries,
  pauses,
}: Pick<Props, "escalations" | "commands" | "approvals" | "retries" | "pauses">): Guide {
  const approvalRunIds = new Set(approvals.map((item) => item.run.id));
  const escalation = escalations.find((item) => !approvalRunIds.has(item.run.id));
  if (escalation) {
    return {
      title: "Start with escalation",
      summary: softenOperatorText(`${escalation.title}. ${escalation.summary}`),
      chip: "Escalation",
      cta: "Open run",
      tone: "attention",
      action: "open",
      runId: escalation.run.id,
    };
  }

  const command = commands[0];
  if (command) {
    return {
      title: "Start with recovery work",
      summary: softenOperatorText(`${command.title}. ${command.summary}`),
      chip: "Recovery",
      cta: "Open run",
      tone: "attention",
      action: "open",
      runId: command.run.id,
    };
  }

  const approval = approvals[0];
  if (approval) {
    return {
      title: "Start with approval",
      summary: softenOperatorText(approval.summary),
      chip: "Approval",
      cta: "Approve selected action",
      tone: "attention",
      action: "approve",
      actionId: approval.action.id,
    };
  }

  const retry = retries[0];
  if (retry) {
    return {
      title: "Start with resume",
      summary: softenOperatorText(retry.summary),
      chip: "Resume",
      cta: retry.control === "start" ? "Resume selected run" : "Step selected run",
      tone: "attention",
      action: "control",
      runId: retry.run.id,
      control: retry.control,
    };
  }

  const pause = pauses[0];
  if (pause) {
    return {
      title: "Start with pause decision",
      summary: softenOperatorText(pause.summary),
      chip: "Pause",
      cta: "Pause selected run",
      tone: "attention",
      action: "control",
      runId: pause.run.id,
      control: "pause",
    };
  }

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
