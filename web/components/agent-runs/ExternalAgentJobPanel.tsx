"use client";

import React from "react";
import { formatOperatorIdentifier } from "../../lib/operatorDisplayLanguage";
import type { ExternalAgentJobOperatorDetail } from "../../lib/types";

type Props = {
  externalAgentJob: ExternalAgentJobOperatorDetail | null;
  verificationBusy: boolean;
  loading: boolean;
  onVerifyReceipt: () => void;
};

export function ExternalAgentJobPanel({
  externalAgentJob,
  verificationBusy,
  loading,
  onVerifyReceipt,
}: Props) {
  const protocolSummary = latestProtocolSummary(externalAgentJob);
  const protocolIssue = protocolSummaryIssue(protocolSummary);
  return (
    <section className="control-section">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">External agent</span>
          <h4 className="control-section__title">Job supervision</h4>
        </div>
        <span className={`control-chip ${receiptChipClass(externalAgentJob)}`}>
          {externalAgentJob?.verification?.valid
            ? "Handoff verified"
            : externalAgentJob?.latest_receipt
              ? "Handoff needs check"
              : "No handoff"}
        </span>
      </div>
      <p className="panel__muted">
        This run was submitted by an external agent. Operator controls act on the linked run while
        the agent handoff remains scoped to the submitting identity.
      </p>
      {externalAgentJob ? (
        <>
          <div className="panel__meta-strip panel__meta-strip--flat">
            <div>
              <strong>Job</strong>: {externalAgentJob.job.id.slice(0, 8)}
            </div>
            <div>
              <strong>Agent</strong>: {externalAgentJob.job.principal_id ?? "unknown"}
            </div>
            <div>
              <strong>Profile</strong>: {externalAgentJob.job.agent_profile_id ?? "none"}
            </div>
            <div>
              <strong>Retry key</strong>: {externalAgentJob.job.idempotency_key ?? "missing"}
            </div>
            <div>
              <strong>Job status</strong>: {externalAgentJob.job.status ?? "unknown"}
            </div>
            <div>
              <strong>Requested action</strong>:{" "}
              {formatOperatorIdentifier(externalAgentJob.job.requested_tool_id ?? "workflow")}
            </div>
            <div>
              <strong>Skill</strong>:{" "}
              {formatOperatorIdentifier(
                externalAgentJob.job.requested_skill_id ?? "auto-selected",
              )}
            </div>
            <div>
              <strong>Handoff records</strong>: {externalAgentJob.receipts.length}
            </div>
          </div>
          {externalAgentJob.latest_receipt ? (
            <div className="panel__notice">
              Latest handoff:{" "}
              {formatOperatorIdentifier(
                String(externalAgentJob.latest_receipt.receipt_type ?? "external job"),
              )}{" "}
              ·{" "}
              {String(externalAgentJob.latest_receipt.status ?? "unknown")} ·{" "}
              {String(externalAgentJob.latest_receipt.receipt_context_hash ?? "").slice(0, 12)}
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={onVerifyReceipt}
                disabled={verificationBusy || loading}
              >
                {verificationBusy ? "Verifying" : "Verify handoff"}
              </button>
            </div>
          ) : (
            <div className="panel__notice panel__notice--warning">
              No handoff record is available yet. Ask the external agent to refresh the job when an
              auditable checkpoint is needed.
            </div>
          )}
          {externalAgentJob.verification?.blockers?.length ? (
            <ul className="panel__list panel__list--compact">
              {externalAgentJob.verification.blockers.map((blocker) => (
                <li key={blocker} className="agent-guardrail-reason">
                  {formatHandoffText(blocker)}
                </li>
              ))}
            </ul>
          ) : null}
          {protocolSummary ? (
            <>
              <p className="panel__subheading">Protocol activity</p>
              <div className="control-chip-row">
                <span className="control-chip">
                  Status: {readinessStatusLabel(protocolSummary.readiness_status)}
                </span>
                {typeof protocolSummary.readiness_score === "number" ? (
                  <span className="control-chip">
                    Score: {protocolSummary.readiness_score}/100
                  </span>
                ) : null}
                {typeof protocolSummary.candidate_count === "number" ? (
                  <span className="control-chip">
                    Candidates: {protocolSummary.candidate_count}
                  </span>
                ) : null}
                {typeof protocolSummary.protocol_count === "number" ? (
                  <span className="control-chip">
                    Protocols: {protocolSummary.protocol_count}
                  </span>
                ) : null}
                {typeof protocolSummary.issue_count === "number" ? (
                  <span className="control-chip">
                    Issues: {protocolSummary.issue_count}
                  </span>
                ) : null}
                {typeof protocolSummary.live_source_count === "number" ||
                typeof protocolSummary.local_source_count === "number" ? (
                  <span className="control-chip">
                    Evidence: {protocolSummary.live_source_count ?? 0} live /{" "}
                    {protocolSummary.local_source_count ?? 0} local
                  </span>
                ) : null}
              </div>
              {protocolIssue ? (
                <p className="panel__muted">Why: {protocolIssue}</p>
              ) : null}
            </>
          ) : null}
        </>
      ) : (
        <div className="panel__notice panel__notice--warning">
          No external agent handoff is linked to this run yet.
        </div>
      )}
    </section>
  );
}

function receiptChipClass(externalAgentJob: ExternalAgentJobOperatorDetail | null) {
  if (externalAgentJob?.verification?.valid) return "control-chip--success";
  if (externalAgentJob?.latest_receipt) return "control-chip--attention";
  return "";
}

function formatHandoffText(value: string): string {
  return value
    .replace(/\breceipt signature\b/gi, "handoff verification")
    .replace(/\breceipt\b/gi, "handoff record");
}

function latestProtocolSummary(externalAgentJob: ExternalAgentJobOperatorDetail | null) {
  const summaries = (externalAgentJob?.activity_items ?? [])
    .map((item) => item.domain_summary)
    .filter((summary) => String(summary?.domain ?? "").startsWith("protocol_"));
  return summaries.at(-1) ?? null;
}

function readinessStatusLabel(status?: string | null): string {
  const labels: Record<string, string> = {
    blocked: "Blocked",
    needs_review: "Needs review",
    no_candidates: "No candidates",
    ready: "Ready",
  };
  return status ? labels[status] ?? status.replaceAll("_", " ") : "Unknown";
}

function protocolSummaryIssue(summary: ReturnType<typeof latestProtocolSummary>): string | null {
  const lists = [summary?.top_issues, summary?.top_blockers, summary?.top_warnings];
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    const first = list.find((item) => item && typeof item === "object") as
      | Record<string, unknown>
      | undefined;
    const message = typeof first?.message === "string" ? first.message : "";
    if (message) return message;
  }
  return null;
}
