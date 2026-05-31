"use client";

import React from "react";
import type {
  AgentCompensatingAction,
  AgentRunCommandPreflight,
  AgentRunEvent,
} from "../../lib/types";
import { softenOperatorText } from "../../lib/operatorDisplayLanguage";
import { compensatingProposalLabel } from "./compensatingProposal";

type Props = {
  recommendation: AgentCompensatingAction | null;
  event: Pick<AgentRunEvent, "event_type" | "status" | "effect_class" | "timestamp">;
  risk: string;
  preflight?: AgentRunCommandPreflight | null;
  needsConfirmation?: boolean;
  busy?: boolean;
  onCreate: () => void;
  onInspectRun: () => void;
};

function formatEventTime(value?: string | null): string {
  if (!value) return "time unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "time unavailable";
  return parsed.toLocaleString();
}

function formatSignalLabel(eventType?: string | null): string {
  if (eventType === "action_retry_proposed") return "Retry proposal";
  if (eventType === "action_recovery_proposed") return "Recovery proposal";
  if (eventType?.startsWith("operator_command_")) return "Operator command";
  return "Recovery signal";
}

function formatStatusLabel(status?: string | null): string {
  const value = String(status || "unknown").replaceAll("_", " ");
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function CompensatingProposalControl({
  recommendation,
  event,
  risk,
  preflight,
  needsConfirmation = false,
  busy = false,
  onCreate,
  onInspectRun,
}: Props) {
  return (
    <>
      {recommendation ? (
        <div className="list__meta">
          Recovery action: {softenOperatorText(compensatingProposalLabel(recommendation))}
        </div>
      ) : null}
      {preflight ? (
        <div className="panel__notice panel__notice--info">
          <strong>Safety check:</strong> {softenOperatorText(preflight.summary)}{" "}
          <span className="panel__badge panel__badge--secondary">
            Risk: {preflight.risk_level}
          </span>
          {preflight.blockers[0] ? (
            <div>Blocker: {softenOperatorText(preflight.blockers[0])}</div>
          ) : null}
          {preflight.warnings[0] ? (
            <div>Warning: {softenOperatorText(preflight.warnings[0])}</div>
          ) : null}
          <div>Recovery path: {softenOperatorText(preflight.rollback_guidance)}</div>
          {needsConfirmation ? <div>Click again to confirm recovery proposal creation.</div> : null}
        </div>
      ) : null}
      <div className="agent-ops-summary">
        <span className="panel__badge panel__badge--secondary">
          Signal: {formatSignalLabel(event.event_type)}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Status: {formatStatusLabel(event.status)}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Risk: {risk}
        </span>
      </div>
      {event.timestamp ? (
        <div className="list__meta">Command signal: {formatEventTime(event.timestamp)}</div>
      ) : null}
      <div className="detail__actions">
        {recommendation?.capability_name ? (
          <button
            type="button"
            className="button button--primary button--sm"
            onClick={onCreate}
            disabled={busy}
          >
            {busy
              ? "Checking..."
              : needsConfirmation
                ? "Confirm recovery proposal"
                : "Create recovery proposal"}
          </button>
        ) : null}
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={onInspectRun}
        >
          Inspect run
        </button>
      </div>
    </>
  );
}
