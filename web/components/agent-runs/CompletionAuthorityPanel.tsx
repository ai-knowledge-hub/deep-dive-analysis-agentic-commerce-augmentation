"use client";

import React from "react";

import {
  clearRegistryWriteToken,
  getRegistryWriteToken,
  setRegistryWriteToken,
} from "../../lib/api/core";
import type { AgentRunCompletion } from "../../lib/completionTypes";

export type CompletionOverview = {
  total: number;
  verified: number;
  governed: number;
  legacy: number;
  current: number;
  stale: number;
  repairEligible: number;
  unavailable: number;
  totalCursorLag: number;
  incompleteRuns: number;
  blockerCategories: {
    declaredBlockers: number;
    missingRequirements: number;
    missingResults: number;
    partialResults: number;
    failedTasks: number;
    canceledTasks: number;
    receiptBlockers: number;
  };
};

type Props = {
  completion: AgentRunCompletion | null;
  overview: CompletionOverview;
  loading: boolean;
  unavailable: boolean;
  repairBusy: boolean;
  repairNotice: { type: "info" | "error"; text: string } | null;
  onRefresh: () => void;
  onRepair: () => void;
};

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

function compactDigest(value?: string | null): string {
  return value ? value.slice(0, 12) : "—";
}

function blockerLabel(value: unknown): string {
  if (typeof value === "string") return readable(value);
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const label = record.message ?? record.code ?? record.requirement_id ?? record.id;
    if (typeof label === "string") return readable(label);
  }
  return "Unresolved completion requirement";
}

function completionLabel(completion: AgentRunCompletion): string {
  if (!completion.completion_authority_required) return "Legacy · not governed";
  if (completion.projection.freshness !== "current") {
    return `${readable(completion.projection.state)} · not authoritative`;
  }
  return completion.authoritative_decision?.status === "complete"
    ? "Complete"
    : "Incomplete";
}

function completionTone(completion: AgentRunCompletion): string {
  if (!completion.completion_authority_required) return "panel__badge--secondary";
  if (completion.projection.freshness !== "current") return "panel__badge--warning";
  return completion.authoritative_decision?.status === "complete"
    ? "panel__badge--success"
    : "panel__badge--severity-medium";
}

export function CompletionAuthorityPanel({
  completion,
  overview,
  loading,
  unavailable,
  repairBusy,
  repairNotice,
  onRefresh,
  onRepair,
}: Props) {
  const [confirmingRepair, setConfirmingRepair] = React.useState(false);
  const [credential, setCredential] = React.useState("");
  const [credentialSaved, setCredentialSaved] = React.useState(false);

  React.useEffect(() => {
    setConfirmingRepair(false);
  }, [completion?.workflow_id]);

  React.useEffect(() => {
    setCredentialSaved(Boolean(getRegistryWriteToken()));
  }, []);

  const decision = completion?.authoritative_decision ?? null;
  const missing = decision?.partial_failures;
  const blockers = [
    ...(decision?.blockers ?? []).map(blockerLabel),
    ...(decision?.missing_requirements ?? []).map(readable),
    ...(decision?.receipt_blockers ?? []).map((item) => `Unverified receipt: ${item}`),
  ];

  function saveCredential() {
    if (!credential.trim()) return;
    setRegistryWriteToken(credential);
    setCredential("");
    setCredentialSaved(Boolean(getRegistryWriteToken()));
  }

  function clearCredential() {
    clearRegistryWriteToken();
    setCredential("");
    setCredentialSaved(false);
    setConfirmingRepair(false);
  }

  return (
    <section className="completion-authority control-section" aria-labelledby="completion-title">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Completion authority</span>
          <h3 className="control-section__title" id="completion-title">
            Verified outcome
          </h3>
          <div className="control-section__summary">
            Completion comes from the verified decision ledger, never the run status.
          </div>
        </div>
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={onRefresh}
          disabled={loading || repairBusy}
        >
          {loading ? "Refreshing" : "Refresh completion"}
        </button>
      </div>

      <div className="completion-overview" aria-label="Completion operations summary">
        <div><strong>{overview.governed}</strong><span>Governed</span></div>
        <div><strong>{overview.legacy}</strong><span>Legacy</span></div>
        <div><strong>{overview.current}</strong><span>Current</span></div>
        <div><strong>{overview.stale}</strong><span>Stale</span></div>
        <div><strong>{overview.repairEligible}</strong><span>Repair ready</span></div>
        <div><strong>{overview.totalCursorLag}</strong><span>Cursor lag</span></div>
        <div><strong>{overview.incompleteRuns}</strong><span>Incomplete</span></div>
      </div>
      <p className="completion-overview__coverage">
        Verified {overview.verified} of {overview.total} loaded runs
        {overview.unavailable ? ` · ${overview.unavailable} unavailable` : ""}.
      </p>
      <div className="completion-blocker-metrics" aria-label="Incomplete runs by blocker category">
        <span>Declared blockers <strong>{overview.blockerCategories.declaredBlockers}</strong></span>
        <span>Missing requirements <strong>{overview.blockerCategories.missingRequirements}</strong></span>
        <span>Missing results <strong>{overview.blockerCategories.missingResults}</strong></span>
        <span>Partial results <strong>{overview.blockerCategories.partialResults}</strong></span>
        <span>Failed tasks <strong>{overview.blockerCategories.failedTasks}</strong></span>
        <span>Canceled tasks <strong>{overview.blockerCategories.canceledTasks}</strong></span>
        <span>Receipt blockers <strong>{overview.blockerCategories.receiptBlockers}</strong></span>
      </div>

      {loading && !completion ? (
        <div className="completion-empty" role="status">Loading authoritative completion…</div>
      ) : unavailable ? (
        <div className="panel__notice panel__notice--warning" role="alert">
          Completion authority is unavailable. No completion claim is shown; refresh to retry.
        </div>
      ) : !completion ? (
        <div className="completion-empty">Select a run to inspect its completion authority.</div>
      ) : (
        <>
          <div className="completion-verdict">
            <div>
              <span className={`panel__badge ${completionTone(completion)}`}>
                {completionLabel(completion)}
              </span>
              <p>
                {completion.completion_authority_required
                  ? completion.projection.freshness === "current"
                    ? `Decision ${compactDigest(decision?.decision_digest)} is aligned with the live projection.`
                    : `Projection is ${readable(completion.projection.state)}. Treat any earlier completion as stale.`
                  : "This run predates completion governance. Its runtime status is not authoritative completion evidence."}
              </p>
            </div>
            <dl className="completion-cursors">
              <div><dt>Authority</dt><dd>{completion.projection.authoritative_event_sequence ?? "—"}</dd></div>
              <div><dt>Decision</dt><dd>{completion.projection.decision_event_sequence ?? "—"}</dd></div>
              <div><dt>Projection</dt><dd>{completion.projection.projected_event_sequence ?? "—"}</dd></div>
            </dl>
          </div>

          {decision ? (
            <div className="completion-columns">
              <div>
                <h4>Decision evidence</h4>
                <div className="control-chip-row">
                  <span className="control-chip">Results: {completion.accepted_results.length}</span>
                  <span className="control-chip">Evidence: {completion.evidence.length}</span>
                  <span className="control-chip">Receipts blocked: {decision.receipt_blockers.length}</span>
                </div>
                <details className="panel__details">
                  <summary className="panel__details-summary">Accepted results and evidence</summary>
                  <div className="completion-artifacts">
                    {completion.accepted_results.map((result) => (
                      <div key={result.result_id}>
                        <strong>{result.task_id}</strong>
                        <span>{readable(result.outcome)} · {readable(result.validation_status)} · {compactDigest(result.result_digest)}</span>
                      </div>
                    ))}
                    {completion.evidence.map((item) => (
                      <div key={item.evidence_id}>
                        <strong>{item.evidence_id}</strong>
                        <span>{readable(item.availability)} · receipt {readable(item.receipt_status)} · {compactDigest(item.evidence_digest)}</span>
                      </div>
                    ))}
                    {!completion.accepted_results.length && !completion.evidence.length ? (
                      <p className="panel__muted">No accepted result or evidence attestations.</p>
                    ) : null}
                  </div>
                </details>
              </div>
              <div>
                <h4>Completion blockers</h4>
                {blockers.length ? (
                  <ul className="completion-blockers">
                    {blockers.map((blocker, index) => <li key={`${blocker}-${index}`}>{blocker}</li>)}
                  </ul>
                ) : (
                  <p className="panel__muted">No declared decision blockers.</p>
                )}
                {missing && (
                  <div className="completion-partials">
                    <span>Missing results ({missing.missing_result_task_ids.length}): {missing.missing_result_task_ids.join(", ") || "none"}</span>
                    <span>Partial ({missing.partial_task_ids.length}): {missing.partial_task_ids.join(", ") || "none"}</span>
                    <span>Failed ({missing.failed_task_ids.length}): {missing.failed_task_ids.join(", ") || "none"}</span>
                    <span>Canceled ({missing.canceled_task_ids.length}): {missing.canceled_task_ids.join(", ") || "none"}</span>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {completion.repair.last_outcome ? (
            <p className="completion-last-repair">
              Last repair: {readable(String(completion.repair.last_outcome.outcome ?? "recorded"))}
              {completion.repair.last_outcome.repaired_at
                ? ` · ${String(completion.repair.last_outcome.repaired_at)}`
                : ""}
            </p>
          ) : null}

          {completion.repair.eligible ? (
            <div className="completion-repair">
              <div>
                <strong>Projection repair available</strong>
                <p>Replay immutable lifecycle authority into the operational projection.</p>
              </div>
              {!credentialSaved ? (
                <div className="completion-credential">
                  <label className="field">
                    <span className="field__label">Operator access key</span>
                    <input
                      className="panel__input"
                      type="password"
                      value={credential}
                      onChange={(event) => setCredential(event.target.value)}
                      autoComplete="off"
                      placeholder="Bearer access key"
                    />
                  </label>
                  <button type="button" className="button button--ghost button--sm" onClick={saveCredential} disabled={!credential.trim()}>
                    Use for this tab
                  </button>
                </div>
              ) : confirmingRepair ? (
                <div className="completion-confirm" role="group" aria-label="Confirm projection repair">
                  <span>Confirm repair of this verified projection?</span>
                  <button type="button" className="button button--primary button--sm" onClick={onRepair} disabled={repairBusy}>
                    {repairBusy ? "Repairing" : "Confirm repair"}
                  </button>
                  <button type="button" className="button button--ghost button--sm" onClick={() => setConfirmingRepair(false)} disabled={repairBusy}>Cancel</button>
                </div>
              ) : (
                <div className="panel__actions">
                  <button type="button" className="button button--ghost button--sm" onClick={() => setConfirmingRepair(true)}>
                    Repair projection
                  </button>
                  <button type="button" className="button button--ghost button--sm" onClick={clearCredential}>Clear access key</button>
                </div>
              )}
            </div>
          ) : null}
        </>
      )}
      {repairNotice ? (
        <div className={`panel__notice panel__notice--${repairNotice.type === "error" ? "warning" : "info"}`} role={repairNotice.type === "error" ? "alert" : "status"}>
          {repairNotice.text}
        </div>
      ) : null}
    </section>
  );
}
