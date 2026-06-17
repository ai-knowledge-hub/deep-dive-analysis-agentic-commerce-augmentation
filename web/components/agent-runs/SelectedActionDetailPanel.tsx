"use client";

import React from "react";
import type {
  AgentAction,
  AgentRegistryOwnershipPreflight,
  AgentRuntimeCapabilitySpec,
} from "../../lib/types";
import {
  formatOperatorActionName,
  formatOperatorIdentifier,
  softenOperatorText,
} from "../../lib/operatorDisplayLanguage";

const CAPABILITY_EXPLAIN: Record<
  string,
  { summary: string; sideEffects: string[] }
> = {
  freeze_retrieval_protocol: {
    summary: "Saves a stable evidence set for fair variant comparison.",
    sideEffects: ["Writes saved evidence set", "Pins evidence version"],
  },
  run_control_baseline: {
    summary: "Runs control on saved evidence to establish baseline gate.",
    sideEffects: ["Creates run row", "Creates baseline metric row"],
  },
  seed_hypotheses: {
    summary: "Builds test ideas from baseline gaps and winner-signal deltas.",
    sideEffects: ["Creates test idea rows"],
  },
  generate_variants: {
    summary: "Generates and persists candidate variants from loop/cold-start evidence.",
    sideEffects: ["Creates variant rows", "Stores generation provenance"],
  },
  run_variant: {
    summary: "Executes candidate variant on the saved evidence set.",
    sideEffects: ["Creates run row", "Creates metric row with decision fields"],
  },
  request_synthetic_validation: {
    summary: "Requests synthetic validation jobs and optionally auto-runs in-app.",
    sideEffects: ["Creates validation job", "May create validation result"],
  },
  review_validation_readiness: {
    summary: "Evaluates readiness gates for lab/prod promotion tiers.",
    sideEffects: ["Reads validation/metrics state", "Returns explicit gate statuses"],
  },
  update_posterior_and_decisions: {
    summary: "Updates confidence and decision outputs from latest evidence.",
    sideEffects: ["Creates decision-refresh metric row"],
  },
  recommend_next_action: {
    summary: "Produces constrained next-step recommendation.",
    sideEffects: ["Creates recommendation history row"],
  },
  promote_variant_lab: {
    summary: "Promotes variant to lab tier under policy checks.",
    sideEffects: ["Creates analytics event", "Creates decision event"],
  },
  promote_variant_prod: {
    summary: "Promotes variant to prod tier when observed gates pass.",
    sideEffects: ["Creates analytics event", "Creates decision event"],
  },
  publish_copy_revision: {
    summary: "Publishes revision to product description after prod promotion.",
    sideEffects: [
      "Updates product description",
      "Marks revision as published",
      "Creates audit events",
    ],
  },
};

type ActionDiffSummary = {
  previousAction: AgentAction | null;
  previousSameCapability: AgentAction | null;
  vsPreviousAction: { added: string[]; changed: string[]; removed: string[] };
  vsPreviousCapability: { added: string[]; changed: string[]; removed: string[] };
};

type OwnershipForm = {
  owner_principal_id: string;
  steward_team: string;
};

type DiscoveryReadinessSummary = {
  status: string;
  score: number | null;
  candidateCount: number | null;
  readyCandidates: number | null;
  warningCandidates: number | null;
  blockedCandidates: number | null;
  liveSourceCount: number | null;
  localSourceCount: number | null;
  protocolCount: number | null;
  issueCount: number | null;
  issueMessage: string | null;
};

type Props = {
  selectedAction: AgentAction | null;
  selectedCapabilitySpec: AgentRuntimeCapabilitySpec | null;
  ownershipForm: OwnershipForm;
  ownershipPreflight: AgentRegistryOwnershipPreflight | null;
  ownershipBusy: boolean;
  ownershipNotice: string | null;
  actionDiffs: ActionDiffSummary | null;
  shortKeyList: (keys: string[], max?: number) => string;
  onOwnershipFormChange: (patch: Partial<OwnershipForm>) => void;
  onClearOwnershipPreflight: () => void;
  onSubmitRegistryOwnership: (dryRun: boolean) => void;
  onOpenExperimentArtifact: () => void;
  onOpenValidationArtifact: () => void;
  onOpenDetailedDiff: () => void;
};

function metricIdForAction(action: AgentAction): string | null {
  const outputs = (action.outputs ?? {}) as Record<string, unknown>;
  return typeof outputs.metric_id === "string" ? outputs.metric_id : null;
}

function discoverySourceCountsForAction(action: AgentAction): Array<[string, number]> {
  const outputs = (action.outputs ?? {}) as Record<string, unknown>;
  const summary = outputs.summary;
  const sourceCounts =
    summary && typeof summary === "object"
      ? (summary as Record<string, unknown>).source_counts
      : null;
  if (!sourceCounts || typeof sourceCounts !== "object") return [];
  return Object.entries(sourceCounts as Record<string, unknown>)
    .map(([source, count]) => [source, Number(count)] as [string, number])
    .filter(([, count]) => Number.isFinite(count) && count > 0)
    .sort(([left], [right]) => left.localeCompare(right));
}

function discoveryReadinessForAction(
  action: AgentAction,
): DiscoveryReadinessSummary | null {
  const outputs = (action.outputs ?? {}) as Record<string, unknown>;
  const summary = outputs.summary;
  const readiness =
    summary && typeof summary === "object"
      ? (summary as Record<string, unknown>).readiness_summary
      : null;
  if (!readiness || typeof readiness !== "object") return null;
  const data = readiness as Record<string, unknown>;
  const status = typeof data.status === "string" ? data.status : "";
  if (!status) return null;
  return {
    status,
    score: numberOrNull(data.score),
    candidateCount: numberOrNull(data.candidate_count),
    readyCandidates: numberOrNull(data.ready_candidates),
    warningCandidates: numberOrNull(data.warning_candidates),
    blockedCandidates: numberOrNull(data.blocked_candidates),
    liveSourceCount: numberOrNull(data.live_source_count),
    localSourceCount: numberOrNull(data.local_source_count),
    protocolCount: null,
    issueCount: null,
    issueMessage: readinessIssueMessage(data),
  };
}

function protocolReadinessForAction(action: AgentAction): DiscoveryReadinessSummary | null {
  const outputs = (action.outputs ?? {}) as Record<string, unknown>;
  const readiness = Array.isArray(outputs.protocol_readiness)
    ? outputs.protocol_readiness
    : [];
  if (!readiness.length) return null;
  const readyCount = readiness.filter(
    (item) => item && typeof item === "object" && (item as Record<string, unknown>).ready === true,
  ).length;
  const issueCount = readiness.reduce((total, item) => {
    const raw = item && typeof item === "object" ? (item as Record<string, unknown>).issue_count : 0;
    return total + (numberOrNull(raw) ?? 0);
  }, 0);
  return {
    status: issueCount === 0 ? "ready" : "needs_review",
    score: Math.round((100 * readyCount) / readiness.length),
    candidateCount: null,
    readyCandidates: null,
    warningCandidates: null,
    blockedCandidates: null,
    liveSourceCount: null,
    localSourceCount: null,
    protocolCount: readiness.length,
    issueCount,
    issueMessage: protocolIssueMessage(readiness),
  };
}

function readinessIssueMessage(data: Record<string, unknown>): string | null {
  for (const key of ["top_blockers", "top_warnings"]) {
    const list = data[key];
    if (!Array.isArray(list)) continue;
    const first = list.find((item) => item && typeof item === "object") as
      | Record<string, unknown>
      | undefined;
    const message = typeof first?.message === "string" ? first.message : "";
    if (message) return message;
  }
  return null;
}

function protocolIssueMessage(readiness: unknown[]): string | null {
  for (const item of readiness) {
    const issues =
      item && typeof item === "object"
        ? (item as Record<string, unknown>).issues
        : null;
    if (!Array.isArray(issues)) continue;
    const first = issues.find((issue) => issue && typeof issue === "object") as
      | Record<string, unknown>
      | undefined;
    const message = typeof first?.message === "string" ? first.message : "";
    if (message) return message;
  }
  return null;
}

function numberOrNull(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function discoverySourceLabel(source: string): string {
  const labels: Record<string, string> = {
    acp_local_metadata: "ACP local metadata",
    acp_product_feed: "ACP product feed",
    ucp_catalog_search: "UCP Catalog Search",
    ucp_local_metadata: "UCP local metadata",
  };
  return labels[source] ?? source.replaceAll("_", " ");
}

function readinessStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    blocked: "Blocked",
    needs_review: "Needs review",
    no_candidates: "No candidates",
    ready: "Ready",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function SelectedActionDetailPanel({
  selectedAction,
  selectedCapabilitySpec,
  ownershipForm,
  ownershipPreflight,
  ownershipBusy,
  ownershipNotice,
  actionDiffs,
  shortKeyList,
  onOwnershipFormChange,
  onClearOwnershipPreflight,
  onSubmitRegistryOwnership,
  onOpenExperimentArtifact,
  onOpenValidationArtifact,
  onOpenDetailedDiff,
}: Props) {
  if (!selectedAction) return null;

  const sideEffects = selectedAction.side_effects?.length
    ? selectedAction.side_effects
    : selectedCapabilitySpec?.side_effects?.length
      ? selectedCapabilitySpec.side_effects
      : CAPABILITY_EXPLAIN[selectedAction.capability_name]?.sideEffects ?? [
          "No side-effect metadata yet.",
        ];
  const metricId = metricIdForAction(selectedAction);
  const discoverySourceCounts = discoverySourceCountsForAction(selectedAction);
  const discoveryReadiness =
    discoveryReadinessForAction(selectedAction) ?? protocolReadinessForAction(selectedAction);
  const actionLabel = formatOperatorActionName(selectedAction.capability_name);

  return (
    <section className="agent-action-detail control-section">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Action detail</span>
          <h4 className="control-section__title">Selected action details</h4>
        </div>
        <span className="control-chip">Action: {actionLabel}</span>
      </div>
      <p className="panel__muted">
        {softenOperatorText(
          selectedCapabilitySpec?.summary ??
            CAPABILITY_EXPLAIN[selectedAction.capability_name]?.summary ??
            "Capability summary not yet documented.",
        )}
      </p>
      <p className="panel__subheading">What it changes</p>
      <ul className="panel__list panel__list--compact">
        {sideEffects.map((effect, index) => (
          <li key={`${effect}-${index}`}>{softenOperatorText(effect)}</li>
        ))}
      </ul>

      <details className="agent-action-detail__advanced">
        <summary>Show governance and linked work</summary>
      <div className="control-chip-row">
        <span className="control-chip">
          Skill: {formatOperatorIdentifier(selectedAction.skill_id ?? "unmapped")}
        </span>
        <span className="control-chip">
          Tool: {formatOperatorIdentifier(selectedAction.tool_id ?? "legacy")}
        </span>
        <span className="control-chip">
          Effect: {formatOperatorIdentifier(selectedAction.effect_class ?? "unknown")}
        </span>
        <span className="control-chip">
          Tool contract: {selectedAction.registry_version ?? "unpinned"}
        </span>
        <span className="control-chip">
          Release:{" "}
          {selectedAction.registry_fingerprint
            ? selectedAction.registry_fingerprint.slice(0, 12)
            : "unpinned"}
        </span>
        <span className="control-chip">
          Tool version: {selectedAction.tool_version ?? "unpinned"}
        </span>
        <span className="control-chip">
          Skill version: {selectedAction.skill_version ?? "unpinned"}
        </span>
      </div>

      {discoverySourceCounts.length ? (
        <>
          <p className="panel__subheading">Discovery provenance</p>
          <div className="control-chip-row">
            {discoverySourceCounts.map(([source, count]) => (
              <span className="control-chip" key={source}>
                {discoverySourceLabel(source)}: {count}
              </span>
            ))}
          </div>
        </>
      ) : null}

      {discoveryReadiness ? (
        <>
          <p className="panel__subheading">Protocol readiness</p>
          <div className="control-chip-row">
            <span className="control-chip">
              Status: {readinessStatusLabel(discoveryReadiness.status)}
            </span>
            {discoveryReadiness.score !== null ? (
              <span className="control-chip">
                Score: {discoveryReadiness.score}/100
              </span>
            ) : null}
            {discoveryReadiness.candidateCount !== null ? (
              <span className="control-chip">
                Candidates: {discoveryReadiness.candidateCount}
              </span>
            ) : null}
            {discoveryReadiness.protocolCount !== null ? (
              <span className="control-chip">
                Protocols: {discoveryReadiness.protocolCount}
              </span>
            ) : null}
            {discoveryReadiness.issueCount !== null ? (
              <span className="control-chip">Issues: {discoveryReadiness.issueCount}</span>
            ) : null}
            {discoveryReadiness.readyCandidates !== null ? (
              <span className="control-chip">
                Ready: {discoveryReadiness.readyCandidates ?? 0}
              </span>
            ) : null}
            {discoveryReadiness.warningCandidates !== null ? (
              <span className="control-chip">
                Review: {discoveryReadiness.warningCandidates ?? 0}
              </span>
            ) : null}
            {discoveryReadiness.blockedCandidates !== null ? (
              <span className="control-chip">
                Blocked: {discoveryReadiness.blockedCandidates ?? 0}
              </span>
            ) : null}
            {discoveryReadiness.liveSourceCount !== null ||
            discoveryReadiness.localSourceCount !== null ? (
              <span className="control-chip">
                Evidence: {discoveryReadiness.liveSourceCount ?? 0} live /{" "}
                {discoveryReadiness.localSourceCount ?? 0} local
              </span>
            ) : null}
          </div>
          {discoveryReadiness.issueMessage ? (
            <p className="panel__muted">Why: {discoveryReadiness.issueMessage}</p>
          ) : null}
        </>
      ) : null}

      <p className="panel__subheading">Tool contract review</p>
      {selectedCapabilitySpec?.review_checklist?.length ? (
        <ul className="panel__list panel__list--compact">
          {selectedCapabilitySpec.review_checklist.map((item, index) => (
            <li key={`${item}-${index}`}>{softenOperatorText(item)}</li>
          ))}
        </ul>
      ) : (
        <p className="panel__muted">No tool-contract checklist captured for this capability yet.</p>
      )}

      <p className="panel__subheading">Tool ownership</p>
      <div className="control-chip-row">
        <span className="control-chip">
          Owner: {selectedCapabilitySpec?.owner_principal_id ?? "unassigned"}
        </span>
        <span className="control-chip">
          Steward: {selectedCapabilitySpec?.steward_team ?? "unassigned"}
        </span>
        <span className="control-chip">
          Source: {selectedCapabilitySpec?.ownership_source ?? "static_code"}
        </span>
      </div>
      {selectedCapabilitySpec ? (
        <div className="form-grid">
          <label>
            Owner identity
            <input
              value={ownershipForm.owner_principal_id}
              onChange={(event) =>
                onOwnershipFormChange({ owner_principal_id: event.target.value })
              }
              onInput={onClearOwnershipPreflight}
            />
          </label>
          <label>
            Steward team
            <input
              value={ownershipForm.steward_team}
              onChange={(event) => onOwnershipFormChange({ steward_team: event.target.value })}
              onInput={onClearOwnershipPreflight}
            />
          </label>
          {ownershipPreflight ? (
            <div className="panel__notice panel__notice--info">
              <strong>Safety check: {ownershipPreflight.risk_level ?? "unknown"} risk</strong>
              <p>
                {softenOperatorText(
                  ownershipPreflight.summary ??
                    "Review this tool ownership change before applying it.",
                )}
              </p>
              {ownershipPreflight.warnings?.length ? (
                <ul className="panel__list panel__list--compact">
                  {ownershipPreflight.warnings.map((warning, index) => (
                    <li key={`${warning}-${index}`}>{softenOperatorText(warning)}</li>
                  ))}
                </ul>
              ) : null}
              {ownershipPreflight.rollback_guidance ? (
                <p className="panel__muted">
                  Recovery path: {softenOperatorText(ownershipPreflight.rollback_guidance)}
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="panel__actions">
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={() => onSubmitRegistryOwnership(true)}
              disabled={
                ownershipBusy ||
                !ownershipForm.owner_principal_id.trim() ||
                !ownershipForm.steward_team.trim()
              }
            >
              {ownershipBusy ? "Checking ownership" : "Preview ownership change"}
            </button>
            <button
              type="button"
              className="button button--primary button--sm"
              onClick={() => onSubmitRegistryOwnership(false)}
              disabled={
                ownershipBusy ||
                !ownershipPreflight?.requires_confirmation ||
                !ownershipPreflight?.allowed ||
                !ownershipForm.owner_principal_id.trim() ||
                !ownershipForm.steward_team.trim()
              }
            >
              {ownershipBusy ? "Saving ownership" : "Apply ownership"}
            </button>
          </div>
        </div>
      ) : null}
      {ownershipNotice ? (
        <div className="panel__notice panel__notice--info">{ownershipNotice}</div>
      ) : null}

      <p className="panel__subheading">Recovery guidance</p>
      <p className="panel__muted">
        {softenOperatorText(
          selectedAction.rollback_guidance ||
            "No recovery guidance captured for this action yet.",
        )}
      </p>

      <p className="panel__subheading">Recovery actions</p>
      {selectedAction.compensating_actions?.length ? (
        <ul className="panel__list panel__list--compact">
          {selectedAction.compensating_actions.map((item, index) => (
            <li key={`${item.capability_name ?? item.label ?? "recovery"}-${index}`}>
              {item.label
                ? softenOperatorText(item.label)
                : formatOperatorActionName(item.capability_name ?? "Review recovery action")}
              {item.rationale ? `: ${softenOperatorText(item.rationale)}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="panel__muted">No recovery action recommendation captured.</p>
      )}

      <p className="panel__subheading">Rationale and confidence</p>
      <p className="panel__muted">{selectedAction.rationale || "No rationale captured."}</p>
      <p className="panel__muted">
        Confidence:{" "}
        {typeof selectedAction.confidence === "number"
          ? selectedAction.confidence.toFixed(2)
          : "—"}
      </p>

      <p className="panel__subheading">Linked work</p>
      <div className="panel__actions">
        {selectedAction.variant_id ? (
          <button type="button" className="button button--ghost button--sm" onClick={onOpenExperimentArtifact}>
            Open variant
          </button>
        ) : null}
        {selectedAction.validation_job_id ? (
          <button type="button" className="button button--ghost button--sm" onClick={onOpenValidationArtifact}>
            Open validation result
          </button>
        ) : null}
        {metricId ? (
          <button type="button" className="button button--ghost button--sm" onClick={onOpenExperimentArtifact}>
            Open metric
          </button>
        ) : null}
      </div>

      <p className="panel__subheading">Change preview</p>
      <div className="agent-diff-grid">
        <div className="agent-diff-card">
          <div className="agent-diff-card__title">
            vs previous action
            {actionDiffs?.previousAction ? ` #${actionDiffs.previousAction.sequence}` : ""}
          </div>
          <div className="agent-diff-card__meta">
            Added: {shortKeyList(actionDiffs?.vsPreviousAction.added ?? [])}
          </div>
          <div className="agent-diff-card__meta">
            Changed: {shortKeyList(actionDiffs?.vsPreviousAction.changed ?? [])}
          </div>
          <div className="agent-diff-card__meta">
            Removed: {shortKeyList(actionDiffs?.vsPreviousAction.removed ?? [])}
          </div>
        </div>
        <div className="agent-diff-card">
          <div className="agent-diff-card__title">
            vs previous same capability
            {actionDiffs?.previousSameCapability
              ? ` #${actionDiffs.previousSameCapability.sequence}`
              : ""}
          </div>
          <div className="agent-diff-card__meta">
            Added: {shortKeyList(actionDiffs?.vsPreviousCapability.added ?? [])}
          </div>
          <div className="agent-diff-card__meta">
            Changed: {shortKeyList(actionDiffs?.vsPreviousCapability.changed ?? [])}
          </div>
          <div className="agent-diff-card__meta">
            Removed: {shortKeyList(actionDiffs?.vsPreviousCapability.removed ?? [])}
          </div>
        </div>
      </div>
      <p className="panel__muted">
        Diff compares changed result fields so operators can audit what changed before approving
        downstream actions.
      </p>
      <div className="panel__actions">
        <button type="button" className="button button--ghost button--sm" onClick={onOpenDetailedDiff}>
          Open change details
        </button>
      </div>
      </details>
    </section>
  );
}
