"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAppUser } from "../../lib/auth";
import type {
  AgentAction,
  AgentRegistryAuditEvent,
  AgentRegistryApprovalReceiptVerifyResponse,
  AgentRegistryOwnershipUpdateResponse,
  AgentRegistryPinBackfillResponse,
  AgentRegistryRelease,
  AgentRegistryReleaseDetail,
  AgentRun,
  AgentRunCommandType,
  AgentRunEvent,
  AgentRuntimeRegistryResponse,
  Experiment,
  ExternalAgentJobOperatorDetail,
} from "../../lib/types";
import {
  backfillAgentRuntimeRegistryPins,
  controlAgentRun,
  createAgentRun,
  decideAgentAction,
  getAgentRun,
  getAgentRunEvents,
  getAgentRuntimeRegistryRelease,
  getExternalAgentJobForRun,
  issueAgentRunCommand,
  listExperiments,
  listAgentRuns,
  listAgentRuntimeRegistryAudit,
  listAgentRuntimeRegistryReleases,
  listAgentRuntimeRegistry,
  preflightAgentRunCommand,
  updateAgentRuntimeRegistryOwnership,
  verifyAgentRuntimeRegistryApprovalReceipt,
  verifyExternalAgentJobReceiptForRun,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { OperatorConsoleChat } from "../../components/agent/OperatorConsoleChat";
import { ActionDiffDrawer } from "../../components/agent-runs/ActionDiffDrawer";
import {
  AgentTimelinePanel,
  type AgentTimelineEventView,
} from "../../components/agent-runs/AgentTimelinePanel";
import {
  budgetSeverity,
  buildDetailedDiffEntries,
  collectNumericValues,
  formatJsonPreview,
  getStringDiffCandidates,
  keyDiffSummary,
  safeRecord,
  shortKeyList,
  toFiniteNumber,
} from "../../components/agent-runs/actionDiffUtils";
import {
  CreateAgentRunDrawer,
  type CreateAgentRunForm,
} from "../../components/agent-runs/CreateAgentRunDrawer";
import { ExecutionControlsSummary } from "../../components/agent-runs/ExecutionControlsSummary";
import { ExternalAgentJobPanel } from "../../components/agent-runs/ExternalAgentJobPanel";
import { RegistryPanel } from "../../components/agent-runs/RegistryPanel";
import { RunActionsPanel } from "../../components/agent-runs/RunActionsPanel";
import { RunSelectionRail } from "../../components/agent-runs/RunSelectionRail";
import { SelectedActionDetailPanel } from "../../components/agent-runs/SelectedActionDetailPanel";
import {
  approvalReceiptForEvent,
  formatDateCompact,
  registryAuditDiffRows,
  summarizeRegistryAuditDiff,
} from "../../components/agent-runs/registryAudit";
import { sortRunsForOperatorAttention } from "../../components/agent-runs/runAttention";
import {
  TIMELINE_EVENT_TYPES,
  TIMELINE_PRESET_IDS,
  TIMELINE_PRESET_STORAGE_KEY,
  TIMELINE_PRESETS,
  TIMELINE_STATUS_TYPES,
  TIMELINE_WINDOWS,
  type TimelineEventFilter,
  type TimelinePresetId,
  type TimelineStatusFilter,
  type TimelineWindowFilter,
  resolveSinceForWindow,
} from "../../components/agent-runs/timelineFilters";
import { buildExperimentHref, buildValidationHref } from "../../lib/routes";

const RUNS_ROUTE = "/runs";

const DEFAULT_ALLOWED_CAPABILITIES = [
  "freeze_retrieval_protocol",
  "run_control_baseline",
  "seed_hypotheses",
  "generate_variants",
  "run_variant",
  "request_synthetic_validation",
  "review_validation_readiness",
  "update_posterior_and_decisions",
  "recommend_next_action",
  "promote_variant_lab",
  "promote_variant_prod",
  "publish_copy_revision",
];

const AGENT_FLOW_STEPS: { id: string; label: string }[] = [
  { id: "battery_ready", label: "Battery ready" },
  { id: "retrieval_snapshots_ready", label: "Retrieval snapshots ready" },
  { id: "baseline_scored", label: "Baseline scored" },
  { id: "hypotheses_ready", label: "Hypotheses ready" },
  { id: "variants_ready", label: "Variants ready" },
  { id: "experiment_run_completed", label: "Experiment run completed" },
  { id: "validation_completed", label: "Validation completed" },
  { id: "posterior_updated", label: "Posterior updated" },
];

function AgentRunsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAppUser();
  const userId = user?.id ?? null;

  const experimentIdParam = searchParams.get("experiment_id")?.trim() || "";
  const runIdParam = searchParams.get("run_id")?.trim() || "";
  const timelinePresetParam = searchParams.get("timeline_preset")?.trim() || "";
  const timelineEventTypeParam = searchParams.get("timeline_event_type")?.trim() || "";
  const timelineStatusParam = searchParams.get("timeline_status")?.trim() || "";
  const timelineCapabilityParam = searchParams.get("timeline_capability")?.trim() || "";
  const timelineWindowParam = searchParams.get("timeline_window")?.trim() || "";
  const eventIdParam = searchParams.get("event_id")?.trim() || "";
  const initialTimelineFilter = (TIMELINE_EVENT_TYPES.has(timelineEventTypeParam)
    ? timelineEventTypeParam
    : "all") as TimelineEventFilter;
  const initialTimelineStatus = (TIMELINE_STATUS_TYPES.has(timelineStatusParam)
    ? timelineStatusParam
    : "all") as TimelineStatusFilter;
  const initialTimelineWindow = (TIMELINE_WINDOWS.has(timelineWindowParam)
    ? timelineWindowParam
    : "all") as TimelineWindowFilter;
  const initialTimelinePreset = (TIMELINE_PRESET_IDS.has(timelinePresetParam)
    ? timelinePresetParam
    : "all_activity") as TimelinePresetId;
  const hasTimelineQuerySeed = Boolean(
    timelinePresetParam ||
      timelineEventTypeParam ||
      timelineStatusParam ||
      timelineCapabilityParam ||
      timelineWindowParam,
  );

  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(runIdParam || null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [externalAgentJob, setExternalAgentJob] =
    useState<ExternalAgentJobOperatorDetail | null>(null);
  const [externalAgentJobVerificationBusy, setExternalAgentJobVerificationBusy] =
    useState(false);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [runtimeRegistry, setRuntimeRegistry] =
    useState<AgentRuntimeRegistryResponse | null>(null);
  const [registryAuditEvents, setRegistryAuditEvents] = useState<
    AgentRegistryAuditEvent[]
  >([]);
  const [registryReleases, setRegistryReleases] = useState<AgentRegistryRelease[]>([]);
  const [selectedRegistryRelease, setSelectedRegistryRelease] =
    useState<AgentRegistryReleaseDetail | null>(null);
  const [registryReleaseBusy, setRegistryReleaseBusy] = useState<string | null>(null);
  const [registryBackfillPreview, setRegistryBackfillPreview] =
    useState<AgentRegistryPinBackfillResponse | null>(null);
  const [registryBackfillBusy, setRegistryBackfillBusy] = useState(false);
  const [registryBackfillNotice, setRegistryBackfillNotice] = useState<string | null>(null);
  const [registryReceiptVerification, setRegistryReceiptVerification] = useState<{
    eventId: string;
    result: AgentRegistryApprovalReceiptVerifyResponse["verification"];
  } | null>(null);
  const [registryReceiptVerificationBusy, setRegistryReceiptVerificationBusy] =
    useState<string | null>(null);
  const [ownershipForm, setOwnershipForm] = useState({
    owner_principal_id: "",
    steward_team: "",
  });
  const [ownershipBusy, setOwnershipBusy] = useState(false);
  const [ownershipNotice, setOwnershipNotice] = useState<string | null>(null);
  const [ownershipPreflight, setOwnershipPreflight] = useState<
    AgentRegistryOwnershipUpdateResponse["preflight"] | null
  >(null);
  const [runEvents, setRunEvents] = useState<AgentRunEvent[]>([]);
  const [eventsPage, setEventsPage] = useState<{
    before_cursor?: string | null;
    after_cursor?: string | null;
    has_more_before?: boolean;
    has_more_after?: boolean;
  } | null>(null);
  const [loadingOlderEvents, setLoadingOlderEvents] = useState(false);
  const [livePollingActive, setLivePollingActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [diffDrawerOpen, setDiffDrawerOpen] = useState(false);
  const [hideUnchangedDiffLines, setHideUnchangedDiffLines] = useState(true);
  const [timelineFilter, setTimelineFilter] =
    useState<TimelineEventFilter>(initialTimelineFilter);
  const [timelineStatusFilter, setTimelineStatusFilter] =
    useState<TimelineStatusFilter>(initialTimelineStatus);
  const [timelineCapabilityFilter, setTimelineCapabilityFilter] = useState<string>(
    timelineCapabilityParam || "all",
  );
  const [timelineTimeWindow, setTimelineTimeWindow] =
    useState<TimelineWindowFilter>(initialTimelineWindow);
  const [timelinePreset, setTimelinePreset] = useState<TimelinePresetId>(initialTimelinePreset);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(eventIdParam || null);
  const [copyLinkNotice, setCopyLinkNotice] = useState<{
    type: "info" | "error";
    text: string;
  } | null>(null);

  const [createForm, setCreateForm] = useState<CreateAgentRunForm>({
    experiment_id: experimentIdParam || "",
    requires_approval: true,
    run_mode: "plan_only" as "plan_only" | "auto_execute_safe",
    allowed_capabilities: DEFAULT_ALLOWED_CAPABILITIES,
    objective: {
      objective: "weighted_combo_confidence",
      weights: { exp: 0.55, syn: 0.35, obs: 0.1 },
      notes: "Plan autonomy; policy enforced system-side.",
    } as Record<string, unknown>,
    budgets: {
      max_actions: 25,
      max_variant_runs: 2,
      max_cost_usd: 5,
    } as Record<string, unknown>,
    approval_policy: {
      require_approval_for: ["publish", "promote_prod", "budget_increase"],
    } as Record<string, unknown>,
  });

  const timelineSince = useMemo(
    () => resolveSinceForWindow(timelineTimeWindow),
    [timelineTimeWindow],
  );

  const loadRuntimeRegistry = useCallback(async () => {
    if (!userId) return;
    try {
      const response = await listAgentRuntimeRegistry(userId);
      setRuntimeRegistry(response);
      const [auditResponse, releasesResponse] = await Promise.all([
        listAgentRuntimeRegistryAudit({ limit: 5 }, userId),
        listAgentRuntimeRegistryReleases({ limit: 5 }, userId),
      ]);
      setRegistryAuditEvents(auditResponse.events ?? []);
      setRegistryReleases(releasesResponse.releases ?? []);
    } catch {
      setRuntimeRegistry(null);
      setRegistryAuditEvents([]);
      setRegistryReleases([]);
    }
  }, [userId]);

  const loadRuns = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await listAgentRuns(
        { experiment_id: experimentIdParam || null, limit: 50 },
        userId,
      );
      const nextRuns = response.runs ?? [];
      setRuns(nextRuns);
      if (nextRuns.length > 0) {
        if (runIdParam) {
          const match = nextRuns.find((item) => item.id === runIdParam);
          if (match && selectedRunId !== runIdParam) {
            setSelectedRunId(runIdParam);
            return;
          }
        }
        if (!selectedRunId) {
          setSelectedRunId(sortRunsForOperatorAttention(nextRuns)[0].id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent runs.");
    } finally {
      setLoading(false);
    }
  }, [experimentIdParam, runIdParam, selectedRunId, userId]);

  const runRegistryBackfill = useCallback(
    async (dryRun: boolean) => {
      if (!userId) return;
      setRegistryBackfillBusy(true);
      setRegistryBackfillNotice(null);
      try {
        const response = await backfillAgentRuntimeRegistryPins(
          { dry_run: dryRun, limit: 200 },
          userId,
        );
        setRegistryBackfillPreview(response);
        const matched = response.runs.matched + response.actions.matched;
        const updated = response.runs.updated + response.actions.updated;
        setRegistryBackfillNotice(
          dryRun
            ? `Preview found ${matched} records with missing registry pins.`
            : `Backfill updated ${updated} records.`,
        );
        if (!dryRun) {
          await Promise.all([loadRuntimeRegistry(), loadRuns()]);
        }
      } catch (err) {
        setRegistryBackfillNotice(
          err instanceof Error ? err.message : "Registry pin backfill failed.",
        );
      } finally {
        setRegistryBackfillBusy(false);
      }
    },
    [loadRuntimeRegistry, loadRuns, userId],
  );

  const loadRegistryReleaseDetail = useCallback(async (registryFingerprint: string) => {
    if (!userId) return;
    setRegistryReleaseBusy(registryFingerprint);
    setRegistryReceiptVerification(null);
    try {
      const response = await getAgentRuntimeRegistryRelease(
        registryFingerprint,
        {
          audit_limit: 5,
        },
        userId,
      );
      setSelectedRegistryRelease(response.release);
    } catch {
      setSelectedRegistryRelease(null);
    } finally {
      setRegistryReleaseBusy(null);
    }
  }, [userId]);

  const verifyRegistryApprovalReceipt = useCallback(async (event: AgentRegistryAuditEvent) => {
    const approvalReceipt = approvalReceiptForEvent(event);
    if (!approvalReceipt) return;
    setRegistryReceiptVerificationBusy(event.id);
    try {
      const response = await verifyAgentRuntimeRegistryApprovalReceipt({
        approval_receipt: approvalReceipt,
        registry_fingerprint: event.registry_fingerprint,
        audit_event_id: event.id,
        require_audit_event: true,
      });
      setRegistryReceiptVerification({
        eventId: event.id,
        result: response.verification,
      });
    } catch (err) {
      setRegistryReceiptVerification({
        eventId: event.id,
        result: {
          valid: false,
          valid_signature: false,
          valid_payload: false,
          valid_audit_event: false,
          blockers: [
            err instanceof Error ? err.message : "Unable to verify registry approval receipt.",
          ],
        },
      });
    } finally {
      setRegistryReceiptVerificationBusy(null);
    }
  }, []);

  const loadExperiments = useCallback(async () => {
    if (!userId) return;
    try {
      const response = await listExperiments(userId);
      setExperiments(response.experiments ?? []);
    } catch {
      setExperiments([]);
    }
  }, [userId]);

  const loadSelected = useCallback(async () => {
    if (!userId || !selectedRunId) return;
    setLoading(true);
    setError(null);
    try {
      const [response, eventsResponse] = await Promise.all([
        getAgentRun(selectedRunId, { limit: 200 }, userId),
        getAgentRunEvents(
          selectedRunId,
          {
            limit: 200,
            event_type: timelineFilter,
            status: timelineStatusFilter,
            capability_name:
              timelineCapabilityFilter !== "all" ? timelineCapabilityFilter : null,
            since: timelineSince,
          },
          userId,
        ),
      ]);
      setSelectedRun(response.run ?? null);
      setActions(response.actions ?? []);
      setRunEvents(eventsResponse.events ?? []);
      setEventsPage(eventsResponse.page ?? null);
      if (response.run?.principal_type === "external_agent") {
        try {
          const jobResponse = await getExternalAgentJobForRun(response.run.id, userId);
          setExternalAgentJob(jobResponse);
        } catch {
          setExternalAgentJob(null);
        }
      } else {
        setExternalAgentJob(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent run.");
      setExternalAgentJob(null);
    } finally {
      setLoading(false);
    }
  }, [
    selectedRunId,
    timelineCapabilityFilter,
    timelineFilter,
    timelineSince,
    timelineStatusFilter,
    userId,
  ]);

  const loadOlderEvents = useCallback(async () => {
    if (!userId || !selectedRunId || !eventsPage?.before_cursor) return;
    setLoadingOlderEvents(true);
    setError(null);
    try {
      const response = await getAgentRunEvents(
        selectedRunId,
        {
          limit: 200,
          event_type: timelineFilter,
          status: timelineStatusFilter,
          capability_name:
            timelineCapabilityFilter !== "all" ? timelineCapabilityFilter : null,
          since: timelineSince,
          before: eventsPage.before_cursor,
        },
        userId,
      );
      const older = response.events ?? [];
      setRunEvents((current) => [...older, ...current]);
      setEventsPage((current) => ({
        before_cursor: response.page?.before_cursor ?? current?.before_cursor ?? null,
        after_cursor: current?.after_cursor ?? response.page?.after_cursor ?? null,
        has_more_before: Boolean(response.page?.has_more_before),
        has_more_after: current?.has_more_after ?? response.page?.has_more_after ?? false,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load older timeline events.");
    } finally {
      setLoadingOlderEvents(false);
    }
  }, [
    eventsPage?.before_cursor,
    selectedRunId,
    timelineCapabilityFilter,
    timelineFilter,
    timelineSince,
    timelineStatusFilter,
    userId,
  ]);

  const loadNewerEvents = useCallback(async () => {
    if (!userId || !selectedRunId) return;
    try {
      if (!eventsPage?.after_cursor) {
        const bootstrap = await getAgentRunEvents(
          selectedRunId,
          {
            limit: 100,
            event_type: timelineFilter,
            status: timelineStatusFilter,
            capability_name:
              timelineCapabilityFilter !== "all" ? timelineCapabilityFilter : null,
            since: timelineSince,
          },
          userId,
        );
        const incoming = bootstrap.events ?? [];
        setRunEvents((current) => {
          if (current.length === 0) return incoming;
          const seen = new Set(current.map((item) => item.id));
          const merged = [...current];
          incoming.forEach((item) => {
            if (!seen.has(item.id)) merged.push(item);
          });
          return merged;
        });
        setEventsPage(bootstrap.page ?? null);
        return;
      }
      const response = await getAgentRunEvents(
        selectedRunId,
        {
          limit: 100,
          event_type: timelineFilter,
          status: timelineStatusFilter,
          capability_name:
            timelineCapabilityFilter !== "all" ? timelineCapabilityFilter : null,
          since: timelineSince,
          after: eventsPage.after_cursor,
        },
        userId,
      );
      const newer = response.events ?? [];
      if (newer.length === 0) {
        setEventsPage((current) => ({
          ...(current ?? {}),
          has_more_after: Boolean(response.page?.has_more_after),
        }));
        return;
      }
      setRunEvents((current) => {
        const seen = new Set(current.map((item) => item.id));
        const merged = [...current];
        newer.forEach((item) => {
          if (!seen.has(item.id)) merged.push(item);
        });
        return merged;
      });
      setEventsPage((current) => ({
        before_cursor: current?.before_cursor ?? response.page?.before_cursor ?? null,
        after_cursor: response.page?.after_cursor ?? current?.after_cursor ?? null,
        has_more_before: current?.has_more_before ?? response.page?.has_more_before ?? false,
        has_more_after: Boolean(response.page?.has_more_after),
      }));
    } catch {
      // Keep polling resilient; explicit errors still surface through manual refresh actions.
    }
  }, [
    eventsPage?.after_cursor,
    selectedRunId,
    timelineCapabilityFilter,
    timelineFilter,
    timelineSince,
    timelineStatusFilter,
    userId,
  ]);

  const recoverDeepLinkedEvent = useCallback(async () => {
    if (!userId || !selectedRunId || !eventIdParam) return;
    if ((runEvents ?? []).some((item) => item.id === eventIdParam)) return;
    try {
      const response = await getAgentRunEvents(
        selectedRunId,
        {
          limit: 240,
          event_type: timelineFilter,
          status: timelineStatusFilter,
          capability_name:
            timelineCapabilityFilter !== "all" ? timelineCapabilityFilter : null,
          since: timelineSince,
          event_id: eventIdParam,
          around: 240,
        },
        userId,
      );
      const recovered = response.events ?? [];
      if (recovered.length === 0) return;
      setRunEvents(recovered);
      setEventsPage(response.page ?? null);
    } catch {
      // Deep-link recovery is best-effort; keep current list if recovery is unavailable.
    }
  }, [
    eventIdParam,
    runEvents,
    selectedRunId,
    timelineCapabilityFilter,
    timelineFilter,
    timelineSince,
    timelineStatusFilter,
    userId,
  ]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    loadExperiments();
  }, [loadExperiments]);

  useEffect(() => {
    void loadRuntimeRegistry();
  }, [loadRuntimeRegistry]);

  useEffect(() => {
    loadSelected();
  }, [loadSelected]);

  useEffect(() => {
    if (!selectedRunId || !userId) {
      setLivePollingActive(false);
      return;
    }
    let mounted = true;
    const interval = window.setInterval(() => {
      if (document.hidden) {
        if (mounted) setLivePollingActive(false);
        return;
      }
      if (mounted) setLivePollingActive(true);
      void loadNewerEvents();
    }, 5000);
    return () => {
      mounted = false;
      window.clearInterval(interval);
      setLivePollingActive(false);
    };
  }, [loadNewerEvents, selectedRunId, userId]);

  useEffect(() => {
    void recoverDeepLinkedEvent();
  }, [recoverDeepLinkedEvent]);

  useEffect(() => {
    if (!selectedActionId && actions.length > 0) {
      setSelectedActionId(actions[0]?.id ?? null);
      return;
    }
    if (
      selectedActionId &&
      actions.length > 0 &&
      !actions.some((item) => item.id === selectedActionId)
    ) {
      setSelectedActionId(actions[0]?.id ?? null);
    }
  }, [actions, selectedActionId]);

  useEffect(() => {
    if (!eventIdParam) return;
    setSelectedEventId((current) => (current === eventIdParam ? current : eventIdParam));
  }, [eventIdParam]);

  useEffect(() => {
    if (!copyLinkNotice) return;
    const timeout = window.setTimeout(() => setCopyLinkNotice(null), 2200);
    return () => window.clearTimeout(timeout);
  }, [copyLinkNotice]);

  const selectedSummary = useMemo(() => {
    if (!selectedRun) return null;
    return `${selectedRun.status ?? "unknown"} · ${selectedRun.state ?? "unknown"}`;
  }, [selectedRun]);

  const runCounters = useMemo(() => {
    const counters = {
      total: 0,
      running: 0,
      planned: 0,
      failed: 0,
      completed: 0,
      approvals: 0,
    };
    (runs ?? []).forEach((run) => {
      counters.total += 1;
      const status = String(run.status ?? "").toLowerCase();
      if (status === "running") counters.running += 1;
      if (status === "planned") counters.planned += 1;
      if (status === "failed") counters.failed += 1;
      if (status === "completed") counters.completed += 1;
      if (run.requires_approval) counters.approvals += 1;
    });
    return counters;
  }, [runs]);

  const displayRuns = useMemo(() => sortRunsForOperatorAttention(runs ?? []), [runs]);

  const flowSteps = useMemo(() => {
    const currentIndex = AGENT_FLOW_STEPS.findIndex(
      (step) => step.id === (selectedRun?.state ?? null),
    );
    return AGENT_FLOW_STEPS.map((step, index) => {
      let status = "Pending";
      let className = "";
      if (currentIndex >= 0 && index < currentIndex) {
        status = "Done";
        className = "is-done";
      } else if (currentIndex >= 0 && index === currentIndex) {
        status = "Current";
        className = "is-current";
      }
      return { ...step, status, className };
    });
  }, [selectedRun?.state]);

  const selectedAction = useMemo(
    () =>
      (actions ?? []).find((item) => item.id === selectedActionId) ??
      (actions ?? [])[0] ??
      null,
    [actions, selectedActionId],
  );

  const allowedRuntimeTools = useMemo(() => {
    if (!runtimeRegistry || !selectedRun) return [];
    const allowed = new Set(selectedRun.allowed_capabilities ?? []);
    const usedToolIds = new Set((actions ?? []).map((action) => action.tool_id).filter(Boolean));
    return runtimeRegistry.capabilities
      .filter((capability) => allowed.has(capability.name))
      .map((capability) => ({
        capability,
        tool: runtimeRegistry.tools.find((tool) => tool.id === capability.tool_id) ?? null,
      }))
      .filter(({ capability }) => capability.tool_id || usedToolIds.has(capability.tool_id));
  }, [actions, runtimeRegistry, selectedRun]);

  const activeRuntimeSkills = useMemo(() => {
    if (!runtimeRegistry) return [];
    const allowedToolIds = new Set(
      allowedRuntimeTools
        .map(({ capability }) => capability.tool_id)
        .filter((toolId): toolId is string => Boolean(toolId)),
    );
    return runtimeRegistry.skills.filter((skill) =>
      (skill.tool_ids ?? []).some((toolId) => allowedToolIds.has(toolId)),
    );
  }, [allowedRuntimeTools, runtimeRegistry]);

  const selectedCapabilitySpec = useMemo(() => {
    if (!runtimeRegistry || !selectedAction) return null;
    return (
      runtimeRegistry.capabilities.find(
        (capability) => capability.name === selectedAction.capability_name,
      ) ?? null
    );
  }, [runtimeRegistry, selectedAction]);

  useEffect(() => {
    setOwnershipForm({
      owner_principal_id: selectedCapabilitySpec?.owner_principal_id ?? "",
      steward_team: selectedCapabilitySpec?.steward_team ?? "",
    });
    setOwnershipNotice(null);
    setOwnershipPreflight(null);
  }, [
    selectedCapabilitySpec?.owner_principal_id,
    selectedCapabilitySpec?.steward_team,
    selectedCapabilitySpec?.tool_id,
  ]);

  const submitRegistryOwnership = useCallback(async (dryRun: boolean) => {
    if (!userId || !selectedCapabilitySpec?.tool_id) return;
    setOwnershipBusy(true);
    setOwnershipNotice(null);
    try {
      const response = await updateAgentRuntimeRegistryOwnership(
        selectedCapabilitySpec.tool_id,
        {
          ...ownershipForm,
          dry_run: dryRun,
          preflight_confirmed: !dryRun,
        },
        userId,
      );
      if (dryRun) {
        setOwnershipPreflight(response.preflight ?? null);
        setOwnershipNotice(
          response.preflight?.summary ?? "Registry ownership preflight completed.",
        );
        return;
      }
      const receiptId = response.approval_receipt?.receipt_id;
      setOwnershipNotice(
        `Ownership saved${receiptId ? ` with receipt ${receiptId.slice(0, 8)}` : ""}. Active registry ${String(
          response.registry_fingerprint ?? "",
        ).slice(0, 12)} is now ${response.registry_status ?? "updated"}.`,
      );
      setOwnershipPreflight(null);
      await loadRuntimeRegistry();
    } catch (err) {
      setOwnershipNotice(
        err instanceof Error ? err.message : "Unable to update registry ownership.",
      );
    } finally {
      setOwnershipBusy(false);
    }
  }, [loadRuntimeRegistry, ownershipForm, selectedCapabilitySpec?.tool_id, userId]);

  const actionCounters = useMemo(() => {
    const counts = {
      proposed: 0,
      approved: 0,
      executing: 0,
      executed: 0,
      failed: 0,
      rejected: 0,
    };
    (actions ?? []).forEach((action) => {
      const key = String(action.status || "").toLowerCase();
      if (key in counts) {
        counts[key as keyof typeof counts] += 1;
      }
    });
    return counts;
  }, [actions]);

  const timelineEvents = useMemo<AgentTimelineEventView[]>(() => {
    return (runEvents ?? []).map((event) => ({
      id: event.id,
      actionId: event.action_id ?? null,
      sequence: event.sequence,
      capability: event.capability_name ?? "unknown",
      status: String(event.status || "unknown").toLowerCase(),
      when: event.timestamp ?? null,
      note: event.note ?? null,
      toolId: event.tool_id ?? null,
      skillId: event.skill_id ?? null,
      effectClass: event.effect_class ?? null,
      isPolicy: Boolean(event.is_policy_event),
      anchors: event.anchors ?? {},
    }));
  }, [runEvents]);

  useEffect(() => {
    if (!selectedEventId) return;
    const node = document.getElementById(`agent-event-${selectedEventId}`);
    if (!node) return;
    node.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedEventId, timelineEvents.length]);

  const timelineCapabilityOptions = useMemo(() => {
    const all = new Set<string>();
    if (timelineCapabilityFilter && timelineCapabilityFilter !== "all") {
      all.add(timelineCapabilityFilter);
    }
    (actions ?? []).forEach((item) => {
      const name = String(item.capability_name ?? "").trim();
      if (name) all.add(name);
    });
    (runEvents ?? []).forEach((item) => {
      const name = String(item.capability_name ?? "").trim();
      if (name) all.add(name);
    });
    return ["all", ...Array.from(all).sort()];
  }, [actions, runEvents, timelineCapabilityFilter]);

  const copyEventLink = useCallback(
    async (event: AgentTimelineEventView) => {
      setSelectedEventId(event.id);
      if (typeof window === "undefined") return;
      const params = new URLSearchParams(searchParams.toString());
      params.set("event_id", event.id);
      if (selectedRunId) params.set("run_id", selectedRunId);
      const target = `${window.location.origin}${RUNS_ROUTE}${
        params.toString() ? `?${params.toString()}` : ""
      }`;
      try {
        if (!window.navigator.clipboard?.writeText) {
          throw new Error("Clipboard unavailable");
        }
        await window.navigator.clipboard.writeText(target);
        setCopyLinkNotice({
          type: "info",
          text: "Event deep link copied.",
        });
      } catch {
        setCopyLinkNotice({
          type: "error",
          text: "Could not copy link. Copy from browser URL instead.",
        });
      }
    },
    [searchParams, selectedRunId],
  );

  const applyTimelinePreset = useCallback(
    (presetId: Exclude<TimelinePresetId, "custom">) => {
      const preset = TIMELINE_PRESETS.find((item) => item.id === presetId);
      if (!preset) return;
      setTimelinePreset(preset.id);
      setTimelineFilter(preset.eventType);
      setTimelineStatusFilter(preset.status);
      setTimelineCapabilityFilter(preset.capabilityName);
      setTimelineTimeWindow(preset.timeWindow);
    },
    [],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (hasTimelineQuerySeed) return;
    const persisted = window.localStorage.getItem(TIMELINE_PRESET_STORAGE_KEY);
    const preset = TIMELINE_PRESETS.find((item) => item.id === persisted);
    if (preset) {
      applyTimelinePreset(preset.id);
    }
  }, [applyTimelinePreset, hasTimelineQuerySeed]);

  useEffect(() => {
    const matchedPreset = TIMELINE_PRESETS.find(
      (item) =>
        item.eventType === timelineFilter &&
        item.status === timelineStatusFilter &&
        item.capabilityName === timelineCapabilityFilter &&
        item.timeWindow === timelineTimeWindow,
    );
    const nextPreset: TimelinePresetId = matchedPreset ? matchedPreset.id : "custom";
    setTimelinePreset((current) => (current === nextPreset ? current : nextPreset));
  }, [timelineCapabilityFilter, timelineFilter, timelineStatusFilter, timelineTimeWindow]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (timelinePreset === "custom") return;
    window.localStorage.setItem(TIMELINE_PRESET_STORAGE_KEY, timelinePreset);
  }, [timelinePreset]);

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (selectedRunId) {
      params.set("run_id", selectedRunId);
    } else {
      params.delete("run_id");
    }
    if (timelinePreset !== "all_activity") {
      params.set("timeline_preset", timelinePreset);
    } else {
      params.delete("timeline_preset");
    }
    if (timelineFilter !== "all") {
      params.set("timeline_event_type", timelineFilter);
    } else {
      params.delete("timeline_event_type");
    }
    if (timelineStatusFilter !== "all") {
      params.set("timeline_status", timelineStatusFilter);
    } else {
      params.delete("timeline_status");
    }
    if (timelineCapabilityFilter !== "all") {
      params.set("timeline_capability", timelineCapabilityFilter);
    } else {
      params.delete("timeline_capability");
    }
    if (timelineTimeWindow !== "all") {
      params.set("timeline_window", timelineTimeWindow);
    } else {
      params.delete("timeline_window");
    }
    if (selectedEventId) {
      params.set("event_id", selectedEventId);
    } else {
      params.delete("event_id");
    }

    const nextQuery = params.toString();
    const currentQuery = searchParams.toString();
    if (nextQuery === currentQuery) return;
    router.replace(`${RUNS_ROUTE}${nextQuery ? `?${nextQuery}` : ""}`, { scroll: false });
  }, [
    router,
    searchParams,
    selectedEventId,
    selectedRunId,
    timelineCapabilityFilter,
    timelineFilter,
    timelinePreset,
    timelineStatusFilter,
    timelineTimeWindow,
  ]);

  const budgetTelemetry = useMemo(() => {
    const budgets = (selectedRun?.budgets as Record<string, unknown> | undefined) ?? {};
    const maxActions = toFiniteNumber(budgets.max_actions);
    const maxVariantRuns = toFiniteNumber(budgets.max_variant_runs);
    const maxCostUsd = toFiniteNumber(budgets.max_cost_usd);

    const executedActions = (actions ?? []).filter((item) =>
      ["executed", "failed"].includes(String(item.status || "").toLowerCase()),
    ).length;
    const executedVariantRuns = (actions ?? []).filter((item) => {
      const status = String(item.status || "").toLowerCase();
      return status === "executed" && item.capability_name === "run_variant";
    }).length;

    const costKeys = new Set([
      "cost_usd",
      "total_cost_usd",
      "validation_cost_usd",
      "estimated_cost_usd",
    ]);
    const costs = (actions ?? []).flatMap((item) => collectNumericValues(item.outputs, costKeys));
    const totalCostUsd = costs.reduce((sum, value) => sum + value, 0);

    const actionPct = maxActions && maxActions > 0 ? Math.min(100, (executedActions / maxActions) * 100) : null;
    const variantPct =
      maxVariantRuns && maxVariantRuns > 0
        ? Math.min(100, (executedVariantRuns / maxVariantRuns) * 100)
        : null;
    const costPct = maxCostUsd && maxCostUsd > 0 ? Math.min(100, (totalCostUsd / maxCostUsd) * 100) : null;

    return {
      maxActions,
      maxVariantRuns,
      maxCostUsd,
      executedActions,
      executedVariantRuns,
      totalCostUsd,
      actionPct,
      variantPct,
      costPct,
    };
  }, [actions, selectedRun?.budgets]);

  const budgetState = useMemo(() => {
    const actionSeverity = budgetSeverity(
      budgetTelemetry.executedActions,
      budgetTelemetry.maxActions,
      budgetTelemetry.actionPct,
    );
    const variantSeverity = budgetSeverity(
      budgetTelemetry.executedVariantRuns,
      budgetTelemetry.maxVariantRuns,
      budgetTelemetry.variantPct,
    );
    const costSeverity = budgetSeverity(
      budgetTelemetry.totalCostUsd,
      budgetTelemetry.maxCostUsd,
      budgetTelemetry.costPct,
    );
    return {
      actionSeverity,
      variantSeverity,
      costSeverity,
      actionBlocked:
        budgetTelemetry.maxActions != null &&
        budgetTelemetry.executedActions >= budgetTelemetry.maxActions,
      variantBlocked:
        budgetTelemetry.maxVariantRuns != null &&
        budgetTelemetry.executedVariantRuns >= budgetTelemetry.maxVariantRuns,
      costBlocked:
        budgetTelemetry.maxCostUsd != null &&
        budgetTelemetry.totalCostUsd >= budgetTelemetry.maxCostUsd,
    };
  }, [budgetTelemetry]);

  const actionDiffs = useMemo(() => {
    if (!selectedAction) return null;
    const all = actions ?? [];
    const selectedIndex = all.findIndex((item) => item.id === selectedAction.id);
    const previousAction = selectedIndex > 0 ? all[selectedIndex - 1] : null;
    const previousSameCapability = selectedIndex > 0
      ? [...all.slice(0, selectedIndex)]
          .reverse()
          .find((item) => item.capability_name === selectedAction.capability_name) ?? null
      : null;
    const currentOutputs = (selectedAction.outputs ?? {}) as Record<string, unknown>;
    const previousOutputs = ((previousAction?.outputs ?? {}) as Record<string, unknown>) ?? {};
    const previousCapabilityOutputs = ((previousSameCapability?.outputs ?? {}) as Record<string, unknown>) ?? {};

    return {
      previousAction,
      previousSameCapability,
      vsPreviousAction: keyDiffSummary(currentOutputs, previousOutputs),
      vsPreviousCapability: keyDiffSummary(currentOutputs, previousCapabilityOutputs),
    };
  }, [actions, selectedAction]);

  const selectedActionDeepDiff = useMemo(() => {
    if (!selectedAction || !actionDiffs) return null;
    const currentOutputs = safeRecord(selectedAction.outputs);
    const currentInputs = safeRecord(selectedAction.inputs);
    const previousOutputs = safeRecord(actionDiffs.previousAction?.outputs);
    const previousInputs = safeRecord(actionDiffs.previousAction?.inputs);
    const previousCapabilityOutputs = safeRecord(
      actionDiffs.previousSameCapability?.outputs,
    );
    const previousCapabilityInputs = safeRecord(
      actionDiffs.previousSameCapability?.inputs,
    );
    return {
      outputsVsPreviousAction: buildDetailedDiffEntries(
        currentOutputs,
        previousOutputs,
      ),
      outputsVsPreviousCapability: buildDetailedDiffEntries(
        currentOutputs,
        previousCapabilityOutputs,
      ),
      inputsVsPreviousAction: buildDetailedDiffEntries(
        currentInputs,
        previousInputs,
      ),
      inputsVsPreviousCapability: buildDetailedDiffEntries(
        currentInputs,
        previousCapabilityInputs,
      ),
      currentOutputs,
      currentInputs,
      previousOutputs,
      previousInputs,
      previousCapabilityOutputs,
      previousCapabilityInputs,
      copyDiffVsPreviousAction: getStringDiffCandidates(
        currentOutputs,
        previousOutputs,
      ),
      copyDiffVsPreviousCapability: getStringDiffCandidates(
        currentOutputs,
        previousCapabilityOutputs,
      ),
    };
  }, [actionDiffs, selectedAction]);

  const getGuardrailReasonsForAction = useCallback(
    (action: AgentAction): string[] => {
      if (String(action.status || "").toLowerCase() !== "proposed") {
        return [];
      }
      const reasons: string[] = [];
      const runStatus = String(selectedRun?.status || "").toLowerCase();
      if (runStatus === "failed" || runStatus === "completed" || runStatus === "canceled") {
        reasons.push(`Run is ${runStatus}. Start a new run or move to a healthy run state.`);
      }
      if (budgetState.actionBlocked) {
        reasons.push("Action budget reached. Increase budget or execute fewer actions.");
      }
      if (action.capability_name === "run_variant" && budgetState.variantBlocked) {
        reasons.push("Variant run budget reached. Increase budget or review completed runs.");
      }
      if (budgetState.costBlocked) {
        reasons.push("Cost budget reached. Increase max_cost_usd before approving new actions.");
      }
      return reasons;
    },
    [
      budgetState.actionBlocked,
      budgetState.costBlocked,
      budgetState.variantBlocked,
      selectedRun?.status,
    ],
  );

  const nextRecommendedAction = useMemo(() => {
    const proposed = (actions ?? [])
      .filter((item) => String(item.status || "").toLowerCase() === "proposed")
      .sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
    const next = proposed[0] ?? null;
    if (!next) {
      const approved = (actions ?? []).filter(
        (item) => String(item.status || "").toLowerCase() === "approved",
      ).length;
      return {
        action: null as AgentAction | null,
        guardrails: [] as string[],
        hint:
          approved > 0
            ? "No proposed actions left. Use Start/Step to execute approved queue."
            : "No proposed actions. Refresh to sync runtime proposals.",
      };
    }
    const guardrails = getGuardrailReasonsForAction(next);
    return {
      action: next,
      guardrails,
      hint:
        guardrails.length > 0
          ? "Review the blocked reasons before approval."
          : "Ready to approve and continue execution.",
    };
  }, [actions, getGuardrailReasonsForAction]);

  const handleCreate = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await createAgentRun(
        {
          experiment_id: createForm.experiment_id || null,
          requires_approval: createForm.requires_approval,
          run_mode: createForm.run_mode,
          allowed_capabilities: createForm.allowed_capabilities,
          objective: createForm.objective,
          budgets: createForm.budgets,
          approval_policy: createForm.approval_policy,
          status: "planned",
          state: "battery_ready",
        },
        userId,
      );
      const run = resp.run;
      setDrawerOpen(false);
      await loadRuns();
      if (run?.id) {
        setSelectedRunId(run.id);
        setSelectedEventId(null);
        router.replace(
          run.experiment_id ? `${RUNS_ROUTE}?experiment_id=${run.experiment_id}` : RUNS_ROUTE,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create agent run.");
    } finally {
      setLoading(false);
    }
  }, [createForm, loadRuns, router, userId]);

  const handleDecision = useCallback(
    async (actionId: string, decision: "approve" | "reject") => {
      if (!userId) return;
      setLoading(true);
      setError(null);
      try {
        await decideAgentAction(actionId, { decision }, userId);
        await loadSelected();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to update action.");
      } finally {
        setLoading(false);
      }
    },
    [loadSelected, userId],
  );

  const handleRunControl = useCallback(
    async (action: "start" | "pause" | "cancel" | "step") => {
      if (!userId || !selectedRunId) return;
      setLoading(true);
      setError(null);
      try {
        const response = await controlAgentRun(selectedRunId, action, userId);
        if (response.message) {
          setError(response.message);
        }
        await loadSelected();
        await loadRuns();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to control run.");
      } finally {
        setLoading(false);
      }
    },
    [loadRuns, loadSelected, selectedRunId, userId],
  );

  const handleOperatorCommand = useCallback(
    async (command: {
      command_type: AgentRunCommandType;
      action_id?: string | null;
      message?: string | null;
      metadata?: Record<string, unknown>;
    }) => {
      if (!userId || !selectedRunId) return;
      setLoading(true);
      setError(null);
      try {
        const response = await issueAgentRunCommand(selectedRunId, command, userId);
        await loadSelected();
        await loadRuns();
        return response;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to issue command.");
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [loadRuns, loadSelected, selectedRunId, userId],
  );

  const handleOperatorCommandPreflight = useCallback(
    async (command: {
      command_type: AgentRunCommandType;
      action_id?: string | null;
      message?: string | null;
      metadata?: Record<string, unknown>;
    }) => {
      if (!userId || !selectedRunId) {
        throw new Error("Select a run before issuing an operator command.");
      }
      const response = await preflightAgentRunCommand(selectedRunId, command, userId);
      return response.preflight;
    },
    [selectedRunId, userId],
  );

  const verifyExternalAgentReceipt = useCallback(async () => {
    if (!userId || !selectedRun?.id) return;
    setExternalAgentJobVerificationBusy(true);
    setError(null);
    try {
      const verification = await verifyExternalAgentJobReceiptForRun(selectedRun.id, userId);
      setExternalAgentJob((current) =>
        current ? { ...current, verification: verification ?? null } : current,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to verify external-agent job receipt.",
      );
    } finally {
      setExternalAgentJobVerificationBusy(false);
    }
  }, [selectedRun?.id, userId]);

  return (
    <div className="app agent-runs-page">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/lab")}
        sessions={[]}
        activeSessionId={null}
        onSelectSession={() => {}}
        onDeleteSession={() => {}}
        onOpenHistory={() => {}}
        showHistoryButton={false}
      />

      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Runs"
            subtitle={selectedSummary || "Governed execution workspace"}
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/experiments")}
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setDrawerOpen(true)}
                disabled={!userId || loading}
              >
                New agent run
              </button>
            }
          />

          <ControlPlaneBriefing
            label="Execution"
            title="Runs briefing"
            subtitle="Agents propose actions, guardrails shape what can execute, and operator chat explains the current state."
            summary={
              selectedRun
                ? `Selected run is ${selectedRun.status ?? "unknown"} at ${selectedRun.state ?? "unknown"} state. Use the queue, timeline, and chat together before changing execution posture.`
                : "Select a run to inspect its queue, timeline, and policy posture. This workspace is the primary place to understand why the runtime is doing what it is doing."
            }
            metrics={[
              { label: "Total", value: runCounters.total },
              {
                label: "Approvals",
                value: runCounters.approvals,
                tone: runCounters.approvals > 0 ? "warning" : "default",
              },
              { label: "Running", value: runCounters.running },
              {
                label: "Failed",
                value: runCounters.failed,
                tone: runCounters.failed > 0 ? "warning" : "default",
              },
            ]}
            error={error}
          />

          <div className="agent-workspace">
            <section className="control-surface agent-workspace__rail">
              <RunSelectionRail
                runs={displayRuns}
                selectedRunId={selectedRunId}
                runCounters={runCounters}
                onSelectRun={(runId) => {
                  setSelectedRunId(runId);
                  setSelectedEventId(null);
                }}
              />
              <OperatorConsoleChat
                run={selectedRun}
                actions={actions}
                events={runEvents}
                runtimeRegistry={runtimeRegistry}
                selectedAction={selectedAction}
                nextRecommendedAction={nextRecommendedAction}
                onJumpToNextAction={() => {
                  if (nextRecommendedAction.action?.id) {
                    setSelectedActionId(nextRecommendedAction.action.id);
                  }
                }}
                onPreflightCommand={handleOperatorCommandPreflight}
                onIssueCommand={handleOperatorCommand}
                onOpenExperiment={() => {
                  if (selectedRun?.experiment_id) {
                    const params = new URLSearchParams();
                    params.set("experiment_id", selectedRun.experiment_id);
                    params.set("run_id", selectedRun.id);
                    router.push(`/experiments?${params.toString()}`);
                  }
                }}
                onOpenValidation={() =>
                  router.push(
                    buildValidationHref({
                      experimentId: selectedRun?.experiment_id,
                      runId: selectedRun?.id,
                    }),
                  )
                }
                onOpenInterventionsForRun={() => {
                  if (!selectedRun?.id) return;
                  router.push(`/interventions?run_id=${selectedRun.id}`);
                }}
                onFocusFailures={() => {
                  setTimelineFilter("failed");
                  setTimelineStatusFilter("failed");
                  setTimelineCapabilityFilter("all");
                  setTimelinePreset("custom");
                }}
                onFocusApprovals={() => {
                  setTimelineFilter("all");
                  setTimelineStatusFilter("proposed");
                  setTimelineCapabilityFilter("all");
                  setTimelineTimeWindow("all");
                  setTimelinePreset("custom");
                  if (nextRecommendedAction.action?.id) {
                    setSelectedActionId(nextRecommendedAction.action.id);
                  }
                }}
                onFocusPolicy={() => {
                  setTimelineFilter("policy");
                  setTimelineStatusFilter("failed");
                  setTimelineCapabilityFilter("all");
                  setTimelineTimeWindow("24h");
                  setTimelinePreset("custom");
                }}
                onFocusValidationLinked={() => {
                  const validationAction =
                    actions.find((item) => Boolean(item.validation_job_id)) ??
                    actions.find(
                      (item) => item.capability_name === "request_synthetic_validation",
                    ) ??
                    null;
                  setTimelineFilter("all");
                  setTimelineStatusFilter("all");
                  setTimelineCapabilityFilter("request_synthetic_validation");
                  setTimelineTimeWindow("7d");
                  setTimelinePreset("custom");
                  if (validationAction?.id) {
                    setSelectedActionId(validationAction.id);
                  }
                }}
              />
            </section>

            <section className="control-surface agent-workspace__main">
              {selectedRun ? (
                <ExecutionControlsSummary selectedRun={selectedRun} flowSteps={flowSteps} />
              ) : null}
              <section className="control-section">
                <div className="control-section__header">
                  <div>
                    <span className="control-section__eyebrow">Queue</span>
                    <h3 className="control-section__title">Action queue</h3>
                  </div>
                  <div className="panel__meta agent-queue-controls">
                    {selectedRun?.experiment_id && (
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() =>
                          router.push(
                            buildExperimentHref(selectedRun.experiment_id, {
                              runId: selectedRun.id,
                            }),
                          )
                        }
                      >
                        Open experiment
                      </button>
                    )}
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => loadSelected()}
                      disabled={!selectedRunId || loading}
                    >
                      Refresh
                    </button>
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => handleRunControl("start")}
                      disabled={!selectedRunId || loading}
                    >
                      Start
                    </button>
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => handleRunControl("pause")}
                      disabled={!selectedRunId || loading}
                    >
                      Pause
                    </button>
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => handleRunControl("step")}
                      disabled={
                        !selectedRunId ||
                        loading ||
                        (selectedRun?.run_mode || "plan_only") === "plan_only"
                      }
                    >
                      Step
                    </button>
                  </div>
                </div>

                {!selectedRun && (
                  <div className="panel__muted">Select a run to see details.</div>
                )}

                {selectedRun && (
                  <>
                    <section className="agent-next-action">
                      <div className="control-section__header">
                        <div>
                          <span className="control-section__eyebrow">Recommendation</span>
                          <h4 className="control-section__title">Next recommended action</h4>
                        </div>
                        {nextRecommendedAction.action ? (
                          <span className="control-chip">
                            #{nextRecommendedAction.action.sequence} ·{" "}
                            {nextRecommendedAction.action.capability_name}
                          </span>
                        ) : null}
                      </div>
                      <p className="panel__muted">{nextRecommendedAction.hint}</p>
                      {nextRecommendedAction.action?.rationale ? (
                        <p className="panel__muted">{nextRecommendedAction.action.rationale}</p>
                      ) : null}
                      {nextRecommendedAction.guardrails.length > 0 ? (
                        <ul className="panel__list panel__list--compact">
                          {nextRecommendedAction.guardrails.map((reason) => (
                            <li key={reason} className="agent-guardrail-reason">
                              {reason}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </section>

                    <div className="panel__meta-strip panel__meta-strip--flat">
                      <div>
                        <strong>Status</strong>: {selectedRun.status ?? "unknown"}
                      </div>
                      <div>
                        <strong>State</strong>: {selectedRun.state ?? "unknown"}
                      </div>
                      <div>
                        <strong>Approval</strong>:{" "}
                        {selectedRun.requires_approval ? "required" : "auto-execute safe steps"}
                      </div>
                      <div>
                        <strong>Mode</strong>: {selectedRun.run_mode || "plan_only"}
                      </div>
                      <div>
                        <strong>Budget</strong>: max actions{" "}
                        {String(
                          (selectedRun.budgets as Record<string, unknown> | undefined)
                            ?.max_actions ?? "—",
                        )}{" "}
                        · max variant runs{" "}
                        {String(
                          (selectedRun.budgets as Record<string, unknown> | undefined)
                            ?.max_variant_runs ?? "—",
                        )}
                      </div>
                    </div>
                    {selectedRun.principal_type === "external_agent" ? (
                      <ExternalAgentJobPanel
                        externalAgentJob={externalAgentJob}
                        verificationBusy={externalAgentJobVerificationBusy}
                        loading={loading}
                        onVerifyReceipt={verifyExternalAgentReceipt}
                      />
                    ) : null}
                    <RegistryPanel
                      selectedRun={selectedRun}
                      runtimeRegistry={runtimeRegistry}
                      activeRuntimeSkills={activeRuntimeSkills}
                      allowedRuntimeTools={allowedRuntimeTools}
                      registryReleases={registryReleases}
                      registryReleaseBusy={registryReleaseBusy}
                      selectedRegistryRelease={selectedRegistryRelease}
                      registryAuditEvents={registryAuditEvents}
                      registryReceiptVerification={registryReceiptVerification}
                      registryReceiptVerificationBusy={registryReceiptVerificationBusy}
                      registryBackfillPreview={registryBackfillPreview}
                      registryBackfillBusy={registryBackfillBusy}
                      registryBackfillNotice={registryBackfillNotice}
                      formatDateCompact={formatDateCompact}
                      summarizeRegistryAuditDiff={summarizeRegistryAuditDiff}
                      registryAuditDiffRows={registryAuditDiffRows}
                      approvalReceiptForEvent={approvalReceiptForEvent}
                      userId={userId}
                      onLoadRegistryReleaseDetail={loadRegistryReleaseDetail}
                      onVerifyRegistryApprovalReceipt={verifyRegistryApprovalReceipt}
                      onRunRegistryBackfill={runRegistryBackfill}
                      onRegistryChanged={loadRuntimeRegistry}
                    />
                    <RunActionsPanel
                      actions={actions}
                      selectedAction={selectedAction}
                      actionCounters={actionCounters}
                      budgetTelemetry={budgetTelemetry}
                      budgetState={budgetState}
                      loading={loading}
                      getGuardrailReasonsForAction={getGuardrailReasonsForAction}
                      onSelectAction={setSelectedActionId}
                      onDecision={handleDecision}
                      formatJsonPreview={formatJsonPreview}
                    />
                    <AgentTimelinePanel
                      events={timelineEvents}
                      actionCount={actions.length}
                      livePollingActive={livePollingActive}
                      hasMoreBefore={eventsPage?.has_more_before}
                      loadingOlderEvents={loadingOlderEvents}
                      loading={loading}
                      selectedEventId={selectedEventId}
                      timelinePreset={timelinePreset}
                      timelineFilter={timelineFilter}
                      timelineStatusFilter={timelineStatusFilter}
                      timelineCapabilityFilter={timelineCapabilityFilter}
                      timelineCapabilityOptions={timelineCapabilityOptions}
                      timelineTimeWindow={timelineTimeWindow}
                      copyLinkNotice={copyLinkNotice}
                      onLoadOlderEvents={loadOlderEvents}
                      onApplyTimelinePreset={applyTimelinePreset}
                      onTimelineFilterChange={setTimelineFilter}
                      onTimelineStatusFilterChange={setTimelineStatusFilter}
                      onTimelineCapabilityFilterChange={setTimelineCapabilityFilter}
                      onTimelineTimeWindowChange={setTimelineTimeWindow}
                      onSelectEvent={setSelectedEventId}
                      onFocusAction={(event) => {
                        setSelectedEventId(event.id);
                        if (event.actionId) setSelectedActionId(event.actionId);
                        setDiffDrawerOpen(false);
                      }}
                      canOpenExperiment={(event) =>
                        Boolean(selectedRun?.experiment_id || event.anchors?.experiment_id)
                      }
                      onOpenExperiment={(event) => {
                        setSelectedEventId(event.id);
                        router.push(
                          buildExperimentHref(
                            event.anchors?.experiment_id || selectedRun?.experiment_id,
                            { runId: selectedRun?.id },
                          ),
                        );
                      }}
                      canOpenValidation={(event) => Boolean(event.anchors?.validation_job_id)}
                      onOpenValidation={(event) => {
                        setSelectedEventId(event.id);
                        router.push(
                          buildValidationHref({
                            experimentId:
                              event.anchors?.experiment_id || selectedRun?.experiment_id,
                            runId: selectedRun?.id,
                          }),
                        );
                      }}
                      onCopyEventLink={(event) => void copyEventLink(event)}
                    />
                    <SelectedActionDetailPanel
                      selectedAction={selectedAction}
                      selectedCapabilitySpec={selectedCapabilitySpec}
                      ownershipForm={ownershipForm}
                      ownershipPreflight={ownershipPreflight ?? null}
                      ownershipBusy={ownershipBusy}
                      ownershipNotice={ownershipNotice}
                      actionDiffs={actionDiffs}
                      shortKeyList={shortKeyList}
                      onOwnershipFormChange={(patch) =>
                        setOwnershipForm((current) => ({ ...current, ...patch }))
                      }
                      onClearOwnershipPreflight={() => setOwnershipPreflight(null)}
                      onSubmitRegistryOwnership={submitRegistryOwnership}
                      onOpenExperimentArtifact={() =>
                        selectedRun?.experiment_id
                          ? router.push(
                              buildExperimentHref(selectedRun.experiment_id, {
                                runId: selectedRun.id,
                              }),
                            )
                          : null
                      }
                      onOpenValidationArtifact={() =>
                        router.push(
                          buildValidationHref({
                            experimentId: selectedRun?.experiment_id,
                            runId: selectedRun?.id,
                          }),
                        )
                      }
                      onOpenDetailedDiff={() => setDiffDrawerOpen(true)}
                    />
                  </>
                )}
              </section>
            </section>
          </div>
        </div>

        <CreateAgentRunDrawer
          open={drawerOpen}
          experiments={experiments}
          form={createForm}
          loading={loading}
          canCreate={Boolean(userId)}
          onClose={() => setDrawerOpen(false)}
          onFormChange={(patch) => setCreateForm((current) => ({ ...current, ...patch }))}
          onCreate={handleCreate}
        />

        <ActionDiffDrawer
          open={diffDrawerOpen}
          selectedAction={selectedAction}
          diff={selectedActionDeepDiff}
          hideUnchangedDiffLines={hideUnchangedDiffLines}
          onHideUnchangedDiffLinesChange={setHideUnchangedDiffLines}
          onClose={() => setDiffDrawerOpen(false)}
          formatJsonPreview={formatJsonPreview}
        />

      </main>
    </div>
  );
}

export default function AgentRunsPage() {
  return (
    <Suspense fallback={null}>
      <AgentRunsPageContent />
    </Suspense>
  );
}
