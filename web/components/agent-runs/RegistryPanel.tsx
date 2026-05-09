"use client";

import React from "react";
import type {
  AgentRegistryAuditEvent,
  AgentRegistryApprovalReceiptVerifyResponse,
  AgentRegistryPinBackfillResponse,
  AgentRegistryRelease,
  AgentRegistryReleaseDetail,
  AgentRun,
  AgentRuntimeCapabilitySpec,
  AgentRuntimeRegistryResponse,
  AgentRuntimeSkillSpec,
  AgentRuntimeToolSpec,
} from "../../lib/types";

type RegistryAuditDiffRow = { label: string; value: string };

type AllowedRuntimeTool = {
  capability: AgentRuntimeCapabilitySpec;
  tool: AgentRuntimeToolSpec | null;
};

function formatRegistryValue(value?: string | null) {
  return String(value || "not set").replaceAll("_", " ");
}

type Props = {
  selectedRun: AgentRun;
  runtimeRegistry: AgentRuntimeRegistryResponse | null;
  activeRuntimeSkills: AgentRuntimeSkillSpec[];
  allowedRuntimeTools: AllowedRuntimeTool[];
  registryReleases: AgentRegistryRelease[];
  registryReleaseBusy: string | null;
  selectedRegistryRelease: AgentRegistryReleaseDetail | null;
  registryAuditEvents: AgentRegistryAuditEvent[];
  registryReceiptVerification: {
    eventId: string;
    result: AgentRegistryApprovalReceiptVerifyResponse["verification"];
  } | null;
  registryReceiptVerificationBusy: string | null;
  registryBackfillPreview: AgentRegistryPinBackfillResponse | null;
  registryBackfillBusy: boolean;
  registryBackfillNotice: string | null;
  formatDateCompact: (value?: string | null) => string;
  summarizeRegistryAuditDiff: (event: AgentRegistryAuditEvent) => string;
  registryAuditDiffRows: (event: AgentRegistryAuditEvent) => RegistryAuditDiffRow[];
  approvalReceiptForEvent: (event: AgentRegistryAuditEvent) => Record<string, unknown> | null;
  onLoadRegistryReleaseDetail: (registryFingerprint: string) => void;
  onVerifyRegistryApprovalReceipt: (event: AgentRegistryAuditEvent) => void;
  onRunRegistryBackfill: (dryRun: boolean) => void;
};

function ReceiptVerificationNotice({
  verification,
}: {
  verification: Props["registryReceiptVerification"];
}) {
  if (!verification) return null;
  return (
    <div
      className={`panel__notice ${
        verification.result.valid ? "panel__notice--info" : "panel__notice--error"
      }`}
    >
      {verification.result.valid
        ? "Receipt verified against signature and registry audit trail."
        : `Receipt verification failed: ${verification.result.blockers.join(" ")}`}
    </div>
  );
}

export function RegistryPanel({
  selectedRun,
  runtimeRegistry,
  activeRuntimeSkills,
  allowedRuntimeTools,
  registryReleases,
  registryReleaseBusy,
  selectedRegistryRelease,
  registryAuditEvents,
  registryReceiptVerification,
  registryReceiptVerificationBusy,
  registryBackfillPreview,
  registryBackfillBusy,
  registryBackfillNotice,
  formatDateCompact,
  summarizeRegistryAuditDiff,
  registryAuditDiffRows,
  approvalReceiptForEvent,
  onLoadRegistryReleaseDetail,
  onVerifyRegistryApprovalReceipt,
  onRunRegistryBackfill,
}: Props) {
  const activeHarness =
    runtimeRegistry?.harness_profiles?.find(
      (profile) => profile.id === selectedRun.harness_id,
    ) ?? null;
  return (
    <section className="control-section registry-panel">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Contract</span>
          <h4 className="control-section__title">Skills and tools</h4>
        </div>
        <span className="control-chip">
          {runtimeRegistry?.registry_version ?? "Loading registry"}
        </span>
      </div>
      <p className="panel__muted">
        This is the agent-facing execution contract for the selected run: skills describe
        reusable workflows, tools are the policy-governed capabilities the runtime can
        execute.
      </p>
      <div className="control-chip-row">
        <span className="control-chip">
          Principal: {selectedRun.principal_type ?? "human"}
        </span>
        <span className="control-chip">
          Policy: {selectedRun.policy_profile_id ?? "human_approval_required"}
        </span>
        <span className="control-chip">
          Harness: {activeHarness?.name ?? selectedRun.harness_id ?? "operator supervised"}
        </span>
        <span className="control-chip">
          Trace: {selectedRun.trace_id ? String(selectedRun.trace_id).slice(0, 14) : "pending"}
        </span>
        <span className="control-chip">
          Run registry: {selectedRun.registry_version ?? runtimeRegistry?.registry_version ?? "unpinned"}
        </span>
        <span className="control-chip">
          Fingerprint:{" "}
          {selectedRun.registry_fingerprint
            ? selectedRun.registry_fingerprint.slice(0, 12)
            : runtimeRegistry?.registry_fingerprint
              ? runtimeRegistry.registry_fingerprint.slice(0, 12)
              : "pending"}
        </span>
        <span className="control-chip">
          Registry source: {runtimeRegistry?.registry_source ?? "pending"}
        </span>
        <span className="control-chip">
          Release status: {runtimeRegistry?.registry_status ?? "pending"}
        </span>
      </div>
      <div className="control-chip-row registry-panel__skills">
        {activeRuntimeSkills.slice(0, 4).map((skill) => (
          <span key={skill.id} className="control-chip">
            {skill.name} · {skill.risk_class}
          </span>
        ))}
        {runtimeRegistry && activeRuntimeSkills.length === 0 ? (
          <span className="control-chip control-chip--attention">
            No matching skills for allowed tools
          </span>
        ) : null}
      </div>

      <section className="control-section">
        <div className="control-section__header">
          <div>
            <span className="control-section__eyebrow">Harness</span>
            <h4 className="control-section__title">Execution posture</h4>
          </div>
          <span className="control-chip">
            {activeHarness?.id ?? selectedRun.harness_id ?? "default"}
          </span>
        </div>
        {activeHarness ? (
          <>
            <p className="panel__muted">{activeHarness.description}</p>
            <div className="panel__meta-strip panel__meta-strip--flat">
              <div>
                <strong>Planner</strong>: {formatRegistryValue(activeHarness.planner_mode)}
              </div>
              <div>
                <strong>Retry</strong>: {formatRegistryValue(activeHarness.retry_strategy)}
              </div>
              <div>
                <strong>Approval</strong>: {formatRegistryValue(activeHarness.approval_strategy)}
              </div>
              <div>
                <strong>Memory</strong>: {formatRegistryValue(activeHarness.memory_policy)}
              </div>
              <div>
                <strong>Fallback</strong>:{" "}
                {(activeHarness.fallback_order ?? []).map(formatRegistryValue).join(" -> ") ||
                  "not set"}
              </div>
              <div>
                <strong>Stops</strong>:{" "}
                {(activeHarness.stopping_conditions ?? [])
                  .map(formatRegistryValue)
                  .join(" · ") || "not set"}
              </div>
            </div>
          </>
        ) : (
          <p className="panel__muted">
            Harness metadata is not available in the active registry payload yet.
          </p>
        )}
      </section>

      <section className="control-section">
        <div className="control-section__header">
          <h4 className="control-section__title">Registry releases</h4>
          <span className="control-chip">
            {registryReleases.length} tracked
          </span>
        </div>
        {registryReleases.length > 0 ? (
          <div className="run-event-list">
            {registryReleases.slice(0, 3).map((release) => (
              <div key={release.id} className="run-event-list__item">
                <div>
                  <div className="table__strong">
                    {release.registry_version} · {release.status}
                  </div>
                  <div className="table__muted">
                    {release.registry_fingerprint.slice(0, 12)} · {release.source} ·{" "}
                    {formatDateCompact(release.created_at)}
                  </div>
                </div>
                <div className="table__muted">
                  {release.counts.skills} skills · {release.counts.tools} tools ·{" "}
                  {release.counts.capabilities} capabilities
                </div>
                <button
                  type="button"
                  className="button button--ghost button--sm"
                  onClick={() => onLoadRegistryReleaseDetail(release.registry_fingerprint)}
                  disabled={registryReleaseBusy === release.registry_fingerprint}
                >
                  {registryReleaseBusy === release.registry_fingerprint ? "Loading" : "View details"}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="panel__muted">
            No registry releases have been persisted in this environment yet.
          </p>
        )}

        {selectedRegistryRelease ? (
          <div className="panel__notice panel__notice--info">
            <div className="panel__eyebrow">Release detail</div>
            <div className="table__strong">
              {selectedRegistryRelease.registry_fingerprint.slice(0, 12)} ·{" "}
              {selectedRegistryRelease.status}
            </div>
            <p className="panel__muted">
              Payload contains {selectedRegistryRelease.payload.skills?.length ?? 0} skills,{" "}
              {selectedRegistryRelease.payload.tools?.length ?? 0} tools, and{" "}
              {selectedRegistryRelease.payload.policy_profiles?.length ?? 0} policy profiles.
            </p>
            <div className="agent-ops-summary">
              {(selectedRegistryRelease.payload.capabilities ?? []).slice(0, 4).map((capability) => (
                <span key={capability.name} className="panel__badge panel__badge--secondary">
                  {capability.name} · {capability.effect_class}
                </span>
              ))}
            </div>
            <p className="panel__muted">
              {selectedRegistryRelease.audit_events.length} audit events are tied to this release.
            </p>
            {selectedRegistryRelease.audit_events.length > 0 ? (
              <div className="registry-panel__subsection">
                <div className="panel__eyebrow">Release diff</div>
                <div className="run-event-list">
                  {selectedRegistryRelease.audit_events.slice(0, 4).map((event) => (
                    <div key={event.id} className="run-event-list__item">
                      <div>
                        <div className="table__strong">
                          {event.event_type.replaceAll("_", " ")}
                        </div>
                        <div className="table__muted">
                          {event.previous_registry_fingerprint
                            ? `${event.previous_registry_fingerprint.slice(0, 12)} -> `
                            : ""}
                          {event.registry_fingerprint.slice(0, 12)} ·{" "}
                          {formatDateCompact(event.created_at)}
                        </div>
                      </div>
                      <div className="agent-ops-summary">
                        {registryAuditDiffRows(event).map((row) => (
                          <span
                            key={`${event.id}-${row.label}`}
                            className="panel__badge panel__badge--secondary"
                          >
                            {row.label}: {row.value}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {selectedRegistryRelease.audit_events.some((event) => Boolean(approvalReceiptForEvent(event))) ? (
              <div className="run-event-list">
                {selectedRegistryRelease.audit_events
                  .filter((event) => Boolean(approvalReceiptForEvent(event)))
                  .slice(0, 3)
                  .map((event) => (
                    <div key={event.id} className="run-event-list__item">
                      <div>
                        <div className="table__strong">Signed ownership receipt</div>
                        <div className="table__muted">
                          {event.id.slice(0, 12)} · {event.registry_fingerprint.slice(0, 12)}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="button button--ghost button--sm"
                        onClick={() => onVerifyRegistryApprovalReceipt(event)}
                        disabled={registryReceiptVerificationBusy === event.id}
                      >
                        {registryReceiptVerificationBusy === event.id ? "Verifying" : "Verify receipt"}
                      </button>
                    </div>
                  ))}
              </div>
            ) : null}
            <ReceiptVerificationNotice verification={registryReceiptVerification} />
          </div>
        ) : null}

        <div className="panel__actions">
          <button
            type="button"
            className="button button--ghost button--sm"
            onClick={() => onRunRegistryBackfill(true)}
            disabled={registryBackfillBusy}
          >
            Preview missing pins
          </button>
          {registryBackfillPreview &&
          registryBackfillPreview.runs.matched + registryBackfillPreview.actions.matched > 0 ? (
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={() => onRunRegistryBackfill(false)}
              disabled={registryBackfillBusy}
            >
              Apply backfill
            </button>
          ) : null}
        </div>
        {registryBackfillPreview ? (
          <p className="panel__muted">
            Missing pins: {registryBackfillPreview.runs.matched} runs ·{" "}
            {registryBackfillPreview.actions.matched} actions. Updated:{" "}
            {registryBackfillPreview.runs.updated} runs ·{" "}
            {registryBackfillPreview.actions.updated} actions.
          </p>
        ) : null}
        {registryBackfillNotice ? (
          <div className="panel__notice panel__notice--info">{registryBackfillNotice}</div>
        ) : null}
      </section>

      <section className="control-section">
        <div className="control-section__header">
          <h4 className="control-section__title">Registry release trail</h4>
          <span className="control-chip">
            {registryAuditEvents.length} recent changes
          </span>
        </div>
        {registryAuditEvents.length > 0 ? (
          <div className="run-event-list">
            {registryAuditEvents.slice(0, 3).map((event) => (
              <div key={event.id} className="run-event-list__item">
                <div>
                  <div className="table__strong">{event.event_type.replaceAll("_", " ")}</div>
                  <div className="table__muted">
                    {event.previous_registry_fingerprint
                      ? `${event.previous_registry_fingerprint.slice(0, 12)} -> `
                      : ""}
                    {event.registry_fingerprint.slice(0, 12)} · {formatDateCompact(event.created_at)}
                  </div>
                </div>
                <div className="table__muted">{summarizeRegistryAuditDiff(event)}</div>
                {approvalReceiptForEvent(event) ? (
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => onVerifyRegistryApprovalReceipt(event)}
                    disabled={registryReceiptVerificationBusy === event.id}
                  >
                    {registryReceiptVerificationBusy === event.id ? "Verifying" : "Verify receipt"}
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="panel__muted">
            No registry transitions recorded yet. The current release is the first observed contract
            for this environment.
          </p>
        )}
        {!selectedRegistryRelease ? (
          <ReceiptVerificationNotice verification={registryReceiptVerification} />
        ) : null}
      </section>

      <div className="table">
        <div className="table__header">
          <div className="table__cell">Tool</div>
          <div className="table__cell">Capability</div>
          <div className="table__cell">Effect</div>
          <div className="table__cell">Side effects</div>
        </div>
        {allowedRuntimeTools.slice(0, 8).map(({ capability, tool }) => (
          <div key={capability.name} className="table__row">
            <div className="table__cell" data-label="Tool">
              <div className="table__strong">{capability.tool_id}</div>
              <div className="table__muted">
                {tool?.default_version ?? capability.default_version ?? "v1"}
              </div>
            </div>
            <div className="table__cell" data-label="Capability">
              {capability.name}
            </div>
            <div className="table__cell" data-label="Effect">
              {tool?.effect_class ?? capability.effect_class ?? "unknown"}
            </div>
            <div className="table__cell table__muted" data-label="Side effects">
              {(tool?.side_effects ?? capability.side_effects ?? []).slice(0, 3).join(", ") ||
                "none declared"}
            </div>
          </div>
        ))}
        {runtimeRegistry && allowedRuntimeTools.length === 0 ? (
          <div className="panel__muted">No registry tools match this run’s allowed capabilities.</div>
        ) : null}
      </div>
    </section>
  );
}
