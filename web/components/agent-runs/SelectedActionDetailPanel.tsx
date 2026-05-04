"use client";

import React from "react";
import type {
  AgentAction,
  AgentRegistryOwnershipPreflight,
  AgentRuntimeCapabilitySpec,
} from "../../lib/types";

const CAPABILITY_EXPLAIN: Record<
  string,
  { summary: string; sideEffects: string[] }
> = {
  freeze_retrieval_protocol: {
    summary: "Freezes retrieval snapshots for stable, fair variant comparison.",
    sideEffects: ["Writes retrieval snapshots", "Pins snapshot version"],
  },
  run_control_baseline: {
    summary: "Runs control on frozen snapshots to establish baseline gate.",
    sideEffects: ["Creates run row", "Creates baseline metric row"],
  },
  seed_hypotheses: {
    summary: "Builds hypotheses from baseline gaps and winner-signal deltas.",
    sideEffects: ["Creates hypothesis rows"],
  },
  generate_variants: {
    summary: "Generates and persists candidate variants from loop/cold-start evidence.",
    sideEffects: ["Creates variant rows", "Stores generation provenance"],
  },
  run_variant: {
    summary: "Executes candidate variant on frozen snapshots.",
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
    summary: "Recomputes posterior and decision outputs from latest evidence.",
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

  return (
    <section className="agent-action-detail">
      <div className="panel__header">
        <h4>Selected action details</h4>
        <span className="panel__badge panel__badge--secondary">
          {selectedAction.capability_name}
        </span>
      </div>
      <p className="panel__muted">
        {selectedCapabilitySpec?.summary ??
          CAPABILITY_EXPLAIN[selectedAction.capability_name]?.summary ??
          "Capability summary not yet documented."}
      </p>
      <div className="agent-ops-summary">
        <span className="panel__badge panel__badge--secondary">
          Skill: {selectedAction.skill_id ?? "unmapped"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Tool: {selectedAction.tool_id ?? "legacy"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Effect: {selectedAction.effect_class ?? "unknown"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Registry: {selectedAction.registry_version ?? "unpinned"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Receipt fingerprint:{" "}
          {selectedAction.registry_fingerprint
            ? selectedAction.registry_fingerprint.slice(0, 12)
            : "unpinned"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Tool version: {selectedAction.tool_version ?? "unpinned"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Skill version: {selectedAction.skill_version ?? "unpinned"}
        </span>
      </div>

      <p className="panel__subheading">What it changes</p>
      <ul className="panel__list panel__list--compact">
        {sideEffects.map((effect, index) => (
          <li key={`${effect}-${index}`}>{effect}</li>
        ))}
      </ul>

      <p className="panel__subheading">Registry review checklist</p>
      {selectedCapabilitySpec?.review_checklist?.length ? (
        <ul className="panel__list panel__list--compact">
          {selectedCapabilitySpec.review_checklist.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="panel__muted">No registry checklist captured for this capability yet.</p>
      )}

      <p className="panel__subheading">Registry ownership</p>
      <div className="agent-ops-summary">
        <span className="panel__badge panel__badge--secondary">
          Owner: {selectedCapabilitySpec?.owner_principal_id ?? "unassigned"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Steward: {selectedCapabilitySpec?.steward_team ?? "unassigned"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Source: {selectedCapabilitySpec?.ownership_source ?? "static_code"}
        </span>
      </div>
      {selectedCapabilitySpec ? (
        <div className="form-grid">
          <label>
            Owner principal
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
              <strong>Preflight: {ownershipPreflight.risk_level ?? "unknown"} risk</strong>
              <p>
                {ownershipPreflight.summary ??
                  "Review this registry ownership change before applying it."}
              </p>
              {ownershipPreflight.warnings?.length ? (
                <ul className="panel__list panel__list--compact">
                  {ownershipPreflight.warnings.map((warning, index) => (
                    <li key={`${warning}-${index}`}>{warning}</li>
                  ))}
                </ul>
              ) : null}
              {ownershipPreflight.rollback_guidance ? (
                <p className="panel__muted">
                  Rollback: {ownershipPreflight.rollback_guidance}
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
              {ownershipBusy ? "Checking ownership" : "Preflight ownership"}
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

      <p className="panel__subheading">Rollback guidance</p>
      <p className="panel__muted">
        {selectedAction.rollback_guidance || "No rollback guidance captured for this action yet."}
      </p>

      <p className="panel__subheading">Compensating actions</p>
      {selectedAction.compensating_actions?.length ? (
        <ul className="panel__list panel__list--compact">
          {selectedAction.compensating_actions.map((item, index) => (
            <li key={`${item.capability_name ?? item.label ?? "compensating"}-${index}`}>
              {item.label ?? item.capability_name ?? "Review compensating action"}
              {item.rationale ? `: ${item.rationale}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="panel__muted">No compensating action recommendation captured.</p>
      )}

      <p className="panel__subheading">Rationale and confidence</p>
      <p className="panel__muted">{selectedAction.rationale || "No rationale captured."}</p>
      <p className="panel__muted">
        Confidence:{" "}
        {typeof selectedAction.confidence === "number"
          ? selectedAction.confidence.toFixed(2)
          : "—"}
      </p>

      <p className="panel__subheading">Linked artifacts</p>
      <div className="panel__actions">
        {selectedAction.variant_id ? (
          <button type="button" className="button button--ghost button--sm" onClick={onOpenExperimentArtifact}>
            Variant: {selectedAction.variant_id.slice(0, 8)}
          </button>
        ) : null}
        {selectedAction.validation_job_id ? (
          <button type="button" className="button button--ghost button--sm" onClick={onOpenValidationArtifact}>
            Validation job: {selectedAction.validation_job_id.slice(0, 8)}
          </button>
        ) : null}
        {metricId ? (
          <button type="button" className="button button--ghost button--sm" onClick={onOpenExperimentArtifact}>
            Metric: {metricId.slice(0, 8)}
          </button>
        ) : null}
      </div>

      <p className="panel__subheading">Artifact diff preview</p>
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
        Diff compares output payload keys, so operators can audit what changed before approving
        downstream actions.
      </p>
      <div className="panel__actions">
        <button type="button" className="button button--ghost button--sm" onClick={onOpenDetailedDiff}>
          Open detailed diff
        </button>
      </div>
    </section>
  );
}
