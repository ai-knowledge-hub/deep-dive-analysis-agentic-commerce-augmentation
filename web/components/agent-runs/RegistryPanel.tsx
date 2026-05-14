"use client";

import React from "react";
import type {
  AgentRegistryAuditEvent,
  AgentRegistryApprovalReceiptVerifyResponse,
  AgentRegistryHarnessProfilePreflight,
  AgentRegistryProfileDefaultPreflight,
  AgentRegistryPinBackfillResponse,
  AgentRegistryRelease,
  AgentRegistryReleaseDetail,
  AgentRun,
  AgentRuntimeCapabilitySpec,
  AgentRuntimeRegistryResponse,
  AgentRuntimeSkillSpec,
  AgentRuntimeToolSpec,
} from "../../lib/types";
import {
  updateAgentRuntimeRegistryHarnessProfile,
  updateAgentRuntimeRegistryProfileDefault,
} from "../../lib/api";

type RegistryAuditDiffRow = { label: string; value: string };

type AllowedRuntimeTool = {
  capability: AgentRuntimeCapabilitySpec;
  tool: AgentRuntimeToolSpec | null;
};

function formatRegistryValue(value?: string | null) {
  return String(value || "not set").replaceAll("_", " ");
}

function formatListInput(value?: string[]) {
  return (value ?? []).join("\n");
}

function parseListInput(value: string) {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
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
  userId?: string | null;
  onLoadRegistryReleaseDetail: (registryFingerprint: string) => void;
  onVerifyRegistryApprovalReceipt: (event: AgentRegistryAuditEvent) => void;
  onRunRegistryBackfill: (dryRun: boolean) => void;
  onRegistryChanged: () => void;
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
  userId,
  onLoadRegistryReleaseDetail,
  onVerifyRegistryApprovalReceipt,
  onRunRegistryBackfill,
  onRegistryChanged,
}: Props) {
  const activeHarness =
    runtimeRegistry?.harness_profiles?.find(
      (profile) => profile.id === selectedRun.harness_id,
    ) ?? null;
  const activeAgentProfile =
    runtimeRegistry?.agent_profile_defaults?.find(
      (profile) =>
        profile.id === selectedRun.agent_profile_id ||
        (!selectedRun.agent_profile_id && profile.id === selectedRun.principal_type),
    ) ?? null;
  const [harnessEditorOpen, setHarnessEditorOpen] = React.useState(false);
  const [harnessName, setHarnessName] = React.useState("");
  const [harnessDescription, setHarnessDescription] = React.useState("");
  const [harnessDefaultRunMode, setHarnessDefaultRunMode] = React.useState("");
  const [harnessDefaultPolicyId, setHarnessDefaultPolicyId] = React.useState("");
  const [harnessAllowedRunModes, setHarnessAllowedRunModes] = React.useState("");
  const [harnessAllowedPolicyIds, setHarnessAllowedPolicyIds] = React.useState("");
  const [harnessPlannerMode, setHarnessPlannerMode] = React.useState("");
  const [harnessRetryStrategy, setHarnessRetryStrategy] = React.useState("");
  const [harnessFallbackOrder, setHarnessFallbackOrder] = React.useState("");
  const [harnessApprovalStrategy, setHarnessApprovalStrategy] = React.useState("");
  const [harnessMemoryPolicy, setHarnessMemoryPolicy] = React.useState("");
  const [harnessStoppingConditions, setHarnessStoppingConditions] = React.useState("");
  const [harnessPreflight, setHarnessPreflight] =
    React.useState<AgentRegistryHarnessProfilePreflight | null>(null);
  const [harnessEditBusy, setHarnessEditBusy] = React.useState(false);
  const [harnessEditNotice, setHarnessEditNotice] = React.useState<{
    type: "info" | "error";
    text: string;
  } | null>(null);
  const [profileEditorOpen, setProfileEditorOpen] = React.useState(false);
  const [profileName, setProfileName] = React.useState("");
  const [profileHarnessId, setProfileHarnessId] = React.useState("");
  const [profilePolicyId, setProfilePolicyId] = React.useState("");
  const [profileRiskTier, setProfileRiskTier] = React.useState("");
  const [profileChannelType, setProfileChannelType] = React.useState("");
  const [profilePreflight, setProfilePreflight] =
    React.useState<AgentRegistryProfileDefaultPreflight | null>(null);
  const [profileEditBusy, setProfileEditBusy] = React.useState(false);
  const [profileEditNotice, setProfileEditNotice] = React.useState<{
    type: "info" | "error";
    text: string;
  } | null>(null);

  React.useEffect(() => {
    setHarnessName(activeHarness?.name ?? "");
    setHarnessDescription(activeHarness?.description ?? "");
    setHarnessDefaultRunMode(activeHarness?.default_run_mode ?? "");
    setHarnessDefaultPolicyId(activeHarness?.default_policy_profile_id ?? "");
    setHarnessAllowedRunModes(formatListInput(activeHarness?.allowed_run_modes));
    setHarnessAllowedPolicyIds(formatListInput(activeHarness?.allowed_policy_profile_ids));
    setHarnessPlannerMode(activeHarness?.planner_mode ?? "");
    setHarnessRetryStrategy(activeHarness?.retry_strategy ?? "");
    setHarnessFallbackOrder(formatListInput(activeHarness?.fallback_order));
    setHarnessApprovalStrategy(activeHarness?.approval_strategy ?? "");
    setHarnessMemoryPolicy(activeHarness?.memory_policy ?? "");
    setHarnessStoppingConditions(formatListInput(activeHarness?.stopping_conditions));
    setHarnessPreflight(null);
    setHarnessEditNotice(null);
  }, [
    activeHarness?.allowed_policy_profile_ids,
    activeHarness?.allowed_run_modes,
    activeHarness?.approval_strategy,
    activeHarness?.default_policy_profile_id,
    activeHarness?.default_run_mode,
    activeHarness?.description,
    activeHarness?.fallback_order,
    activeHarness?.memory_policy,
    activeHarness?.name,
    activeHarness?.planner_mode,
    activeHarness?.retry_strategy,
    activeHarness?.stopping_conditions,
  ]);

  React.useEffect(() => {
    setProfileName(activeAgentProfile?.name ?? "");
    setProfileHarnessId(activeAgentProfile?.default_harness_id ?? "");
    setProfilePolicyId(activeAgentProfile?.default_policy_profile_id ?? "");
    setProfileRiskTier(activeAgentProfile?.risk_tier ?? "");
    setProfileChannelType(activeAgentProfile?.channel_type ?? "");
    setProfilePreflight(null);
    setProfileEditNotice(null);
  }, [
    activeAgentProfile?.channel_type,
    activeAgentProfile?.default_harness_id,
    activeAgentProfile?.default_policy_profile_id,
    activeAgentProfile?.name,
    activeAgentProfile?.risk_tier,
  ]);

  async function updateHarnessProfile(dryRun: boolean) {
    if (!activeHarness || !userId) return;
    setHarnessEditBusy(true);
    setHarnessEditNotice(null);
    try {
      const response = await updateAgentRuntimeRegistryHarnessProfile(
        activeHarness.id,
        {
          name: harnessName,
          description: harnessDescription,
          default_run_mode: harnessDefaultRunMode,
          default_policy_profile_id: harnessDefaultPolicyId,
          allowed_run_modes: parseListInput(harnessAllowedRunModes),
          allowed_policy_profile_ids: parseListInput(harnessAllowedPolicyIds),
          planner_mode: harnessPlannerMode,
          retry_strategy: harnessRetryStrategy,
          fallback_order: parseListInput(harnessFallbackOrder),
          approval_strategy: harnessApprovalStrategy,
          memory_policy: harnessMemoryPolicy,
          stopping_conditions: parseListInput(harnessStoppingConditions),
          dry_run: dryRun,
          preflight_confirmed: !dryRun,
        },
        userId,
      );
      setHarnessPreflight(response.preflight ?? null);
      if (dryRun) {
        setHarnessEditNotice({
          type: response.preflight?.allowed ? "info" : "error",
          text: response.preflight?.summary ?? "Harness profile preview complete.",
        });
        return;
      }
      setHarnessEditNotice({
        type: "info",
        text: `Harness profile saved. Registry ${String(
          response.registry_fingerprint ?? "",
        ).slice(0, 12)} is now active.`,
      });
      setHarnessEditorOpen(false);
      onRegistryChanged();
    } catch (err) {
      setHarnessEditNotice({
        type: "error",
        text: err instanceof Error ? err.message : "Unable to update harness profile.",
      });
    } finally {
      setHarnessEditBusy(false);
    }
  }

  async function updateProfileDefault(dryRun: boolean) {
    if (!activeAgentProfile || !userId) return;
    setProfileEditBusy(true);
    setProfileEditNotice(null);
    try {
      const response = await updateAgentRuntimeRegistryProfileDefault(
        activeAgentProfile.id,
        {
          name: profileName,
          default_harness_id: profileHarnessId,
          default_policy_profile_id: profilePolicyId,
          risk_tier: profileRiskTier,
          channel_type: profileChannelType,
          dry_run: dryRun,
          preflight_confirmed: !dryRun,
        },
        userId,
      );
      setProfilePreflight(response.preflight ?? null);
      if (dryRun) {
        setProfileEditNotice({
          type: response.preflight?.allowed ? "info" : "error",
          text: response.preflight?.summary ?? "Agent profile default preview complete.",
        });
        return;
      }
      setProfileEditNotice({
        type: "info",
        text: `Agent profile default saved. Registry ${String(
          response.registry_fingerprint ?? "",
        ).slice(0, 12)} is now active.`,
      });
      setProfileEditorOpen(false);
      onRegistryChanged();
    } catch (err) {
      setProfileEditNotice({
        type: "error",
        text: err instanceof Error ? err.message : "Unable to update profile default.",
      });
    } finally {
      setProfileEditBusy(false);
    }
  }

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
            <div className="panel__actions">
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => setHarnessEditorOpen((open) => !open)}
              >
                {harnessEditorOpen ? "Close editor" : "Edit harness posture"}
              </button>
            </div>
            {harnessEditorOpen ? (
              <div className="registry-panel__subsection">
                <div className="panel__eyebrow">Guarded edit</div>
                <label className="field">
                  <span className="field__label">Name</span>
                  <input
                    className="panel__input"
                    value={harnessName}
                    onChange={(event) => setHarnessName(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Description</span>
                  <textarea
                    className="panel__textarea"
                    value={harnessDescription}
                    onChange={(event) => setHarnessDescription(event.target.value)}
                    rows={3}
                  />
                </label>
                <div className="insight-grid insight-grid--two">
                  <label className="field">
                    <span className="field__label">Default run mode</span>
                    <select
                      className="panel__input"
                      value={harnessDefaultRunMode}
                      onChange={(event) => setHarnessDefaultRunMode(event.target.value)}
                    >
                      {harnessDefaultRunMode &&
                      !["plan_only", "auto_execute_safe"].includes(harnessDefaultRunMode) ? (
                        <option value={harnessDefaultRunMode}>{harnessDefaultRunMode}</option>
                      ) : null}
                      <option value="plan_only">plan_only</option>
                      <option value="auto_execute_safe">auto_execute_safe</option>
                    </select>
                  </label>
                  <label className="field">
                    <span className="field__label">Default policy</span>
                    <select
                      className="panel__input"
                      value={harnessDefaultPolicyId}
                      onChange={(event) => setHarnessDefaultPolicyId(event.target.value)}
                    >
                      {harnessDefaultPolicyId &&
                      !(runtimeRegistry?.policy_profiles ?? []).some(
                        (profile) => profile.id === harnessDefaultPolicyId,
                      ) ? (
                        <option value={harnessDefaultPolicyId}>{harnessDefaultPolicyId}</option>
                      ) : null}
                      {(runtimeRegistry?.policy_profiles ?? []).map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="insight-grid insight-grid--two">
                  <label className="field">
                    <span className="field__label">Allowed run modes</span>
                    <textarea
                      className="panel__textarea"
                      value={harnessAllowedRunModes}
                      onChange={(event) => setHarnessAllowedRunModes(event.target.value)}
                      rows={3}
                      placeholder="One run mode per line"
                    />
                  </label>
                  <label className="field">
                    <span className="field__label">Allowed policies</span>
                    <textarea
                      className="panel__textarea"
                      value={harnessAllowedPolicyIds}
                      onChange={(event) => setHarnessAllowedPolicyIds(event.target.value)}
                      rows={3}
                      placeholder="One policy profile id per line"
                    />
                  </label>
                </div>
                <label className="field">
                  <span className="field__label">Planner mode</span>
                  <input
                    className="panel__input"
                    value={harnessPlannerMode}
                    onChange={(event) => setHarnessPlannerMode(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Retry strategy</span>
                  <input
                    className="panel__input"
                    value={harnessRetryStrategy}
                    onChange={(event) => setHarnessRetryStrategy(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Fallback order</span>
                  <textarea
                    className="panel__textarea"
                    value={harnessFallbackOrder}
                    onChange={(event) => setHarnessFallbackOrder(event.target.value)}
                    rows={3}
                    placeholder="One fallback per line"
                  />
                </label>
                <div className="insight-grid insight-grid--two">
                  <label className="field">
                    <span className="field__label">Approval strategy</span>
                    <input
                      className="panel__input"
                      value={harnessApprovalStrategy}
                      onChange={(event) => setHarnessApprovalStrategy(event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span className="field__label">Memory policy</span>
                    <input
                      className="panel__input"
                      value={harnessMemoryPolicy}
                      onChange={(event) => setHarnessMemoryPolicy(event.target.value)}
                    />
                  </label>
                </div>
                <label className="field">
                  <span className="field__label">Stopping conditions</span>
                  <textarea
                    className="panel__textarea"
                    value={harnessStoppingConditions}
                    onChange={(event) => setHarnessStoppingConditions(event.target.value)}
                    rows={3}
                    placeholder="One stopping condition per line"
                  />
                </label>
                <p className="panel__muted">
                  Confirmed apply is protected by registry-write authorization; preview
                  should be used first to catch policy/run-mode mismatches.
                </p>
                <div className="panel__actions">
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => updateHarnessProfile(true)}
                    disabled={harnessEditBusy || !userId}
                  >
                    {harnessEditBusy ? "Checking" : "Preview change"}
                  </button>
                  <button
                    type="button"
                    className="button button--primary button--sm"
                    onClick={() => updateHarnessProfile(false)}
                    disabled={harnessEditBusy || !userId || !harnessPreflight?.allowed}
                  >
                    Apply confirmed change
                  </button>
                </div>
                {harnessPreflight ? (
                  <div
                    className={`panel__notice ${
                      harnessPreflight.allowed ? "panel__notice--info" : "panel__notice--error"
                    }`}
                  >
                    <div className="table__strong">
                      {harnessPreflight.changed_fields?.length ?? 0} fields will change
                    </div>
                    <p className="panel__muted">
                      {harnessPreflight.summary} Rollback:{" "}
                      {harnessPreflight.rollback_guidance}
                    </p>
                    {harnessPreflight.blockers?.length ? (
                      <ul className="panel__list panel__list--compact">
                        {harnessPreflight.blockers.map((blocker) => (
                          <li key={blocker} className="agent-guardrail-reason">
                            {blocker}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
                {harnessEditNotice ? (
                  <div
                    className={`panel__notice ${
                      harnessEditNotice.type === "error"
                        ? "panel__notice--error"
                        : "panel__notice--info"
                    }`}
                  >
                    {harnessEditNotice.text}
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        ) : (
          <p className="panel__muted">
            Harness metadata is not available in the active registry payload yet.
          </p>
        )}
      </section>

      <section className="control-section">
        <div className="control-section__header">
          <div>
            <span className="control-section__eyebrow">Profile default</span>
            <h4 className="control-section__title">Agent profile mapping</h4>
          </div>
          <span className="control-chip">
            {activeAgentProfile?.id ?? selectedRun.agent_profile_id ?? "human"}
          </span>
        </div>
        {activeAgentProfile ? (
          <>
            <div className="panel__meta-strip panel__meta-strip--flat">
              <div>
                <strong>Harness</strong>: {formatRegistryValue(activeAgentProfile.default_harness_id)}
              </div>
              <div>
                <strong>Policy</strong>: {formatRegistryValue(activeAgentProfile.default_policy_profile_id)}
              </div>
              <div>
                <strong>Risk</strong>: {formatRegistryValue(activeAgentProfile.risk_tier)}
              </div>
              <div>
                <strong>Channel</strong>: {formatRegistryValue(activeAgentProfile.channel_type)}
              </div>
              <div>
                <strong>Source</strong>: {formatRegistryValue(activeAgentProfile.source)}
              </div>
            </div>
            <div className="panel__actions">
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => setProfileEditorOpen((open) => !open)}
              >
                {profileEditorOpen ? "Close profile editor" : "Edit profile default"}
              </button>
            </div>
            {profileEditorOpen ? (
              <div className="registry-panel__subsection">
                <div className="panel__eyebrow">Guarded edit</div>
                <label className="field">
                  <span className="field__label">Name</span>
                  <input
                    className="panel__input"
                    value={profileName}
                    onChange={(event) => setProfileName(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Default harness</span>
                  <select
                    className="panel__input"
                    value={profileHarnessId}
                    onChange={(event) => setProfileHarnessId(event.target.value)}
                  >
                    {(runtimeRegistry?.harness_profiles ?? []).map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Default policy</span>
                  <select
                    className="panel__input"
                    value={profilePolicyId}
                    onChange={(event) => setProfilePolicyId(event.target.value)}
                  >
                    {(runtimeRegistry?.policy_profiles ?? []).map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="field__label">Risk tier</span>
                  <input
                    className="panel__input"
                    value={profileRiskTier}
                    onChange={(event) => setProfileRiskTier(event.target.value)}
                    placeholder="bounded_low_risk"
                  />
                </label>
                <label className="field">
                  <span className="field__label">Channel type</span>
                  <input
                    className="panel__input"
                    value={profileChannelType}
                    onChange={(event) => setProfileChannelType(event.target.value)}
                    placeholder="external_job_api"
                  />
                </label>
                <div className="panel__actions">
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => updateProfileDefault(true)}
                    disabled={profileEditBusy || !userId}
                  >
                    {profileEditBusy ? "Checking" : "Preview profile change"}
                  </button>
                  <button
                    type="button"
                    className="button button--primary button--sm"
                    onClick={() => updateProfileDefault(false)}
                    disabled={profileEditBusy || !userId || !profilePreflight?.allowed}
                  >
                    Apply confirmed default
                  </button>
                </div>
                {profilePreflight ? (
                  <div
                    className={`panel__notice ${
                      profilePreflight.allowed ? "panel__notice--info" : "panel__notice--error"
                    }`}
                  >
                    <div className="table__strong">
                      {profilePreflight.changed_fields?.length ?? 0} fields will change
                    </div>
                    <p className="panel__muted">{profilePreflight.summary}</p>
                    {profilePreflight.blockers?.length ? (
                      <ul className="panel__list panel__list--compact">
                        {profilePreflight.blockers.map((blocker) => (
                          <li key={blocker} className="agent-guardrail-reason">
                            {blocker}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
                {profileEditNotice ? (
                  <div
                    className={`panel__notice ${
                      profileEditNotice.type === "error"
                        ? "panel__notice--error"
                        : "panel__notice--info"
                    }`}
                  >
                    {profileEditNotice.text}
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        ) : (
          <p className="panel__muted">
            No persisted default mapping is available for this run’s agent profile yet.
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
