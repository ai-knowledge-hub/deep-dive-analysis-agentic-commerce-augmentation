"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type { AgentAction, AgentRun, AgentRunEvent, Experiment } from "../../lib/types";
import {
  controlAgentRun,
  createAgentRun,
  decideAgentAction,
  getAgentRun,
  getAgentRunEvents,
  listExperiments,
  listAgentRuns,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { OperatorConsoleChat } from "../../components/agent/OperatorConsoleChat";

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

const AGENT_FLOW_STEPS: { id: AgentRun["state"] | string; label: string }[] = [
  { id: "battery_ready", label: "Battery ready" },
  { id: "retrieval_snapshots_ready", label: "Retrieval snapshots ready" },
  { id: "baseline_scored", label: "Baseline scored" },
  { id: "hypotheses_ready", label: "Hypotheses ready" },
  { id: "variants_ready", label: "Variants ready" },
  { id: "experiment_run_completed", label: "Experiment run completed" },
  { id: "validation_completed", label: "Validation completed" },
  { id: "posterior_updated", label: "Posterior updated" },
];

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

const TIMELINE_PRESET_STORAGE_KEY = "agent_runs.timeline_preset.v1";

type TimelineStatusFilter =
  | "all"
  | "proposed"
  | "approved"
  | "executing"
  | "executed"
  | "failed"
  | "rejected";
type TimelineWindowFilter = "all" | "24h" | "7d";
type TimelinePresetId =
  | "all_activity"
  | "policy_failures_24h"
  | "variant_execution_7d"
  | "validation_focus_7d"
  | "custom";

const TIMELINE_EVENT_TYPES = new Set(["all", "failed", "policy", "executed"]);
const TIMELINE_STATUS_TYPES = new Set([
  "all",
  "proposed",
  "approved",
  "executing",
  "executed",
  "failed",
  "rejected",
]);
const TIMELINE_WINDOWS = new Set(["all", "24h", "7d"]);
const TIMELINE_PRESET_IDS = new Set([
  "all_activity",
  "policy_failures_24h",
  "variant_execution_7d",
  "validation_focus_7d",
  "custom",
]);

const TIMELINE_PRESETS: Array<{
  id: Exclude<TimelinePresetId, "custom">;
  label: string;
  eventType: "all" | "failed" | "policy" | "executed";
  status: TimelineStatusFilter;
  capabilityName: string;
  timeWindow: TimelineWindowFilter;
}> = [
  {
    id: "all_activity",
    label: "All activity",
    eventType: "all",
    status: "all",
    capabilityName: "all",
    timeWindow: "all",
  },
  {
    id: "policy_failures_24h",
    label: "Policy failures (24h)",
    eventType: "policy",
    status: "failed",
    capabilityName: "all",
    timeWindow: "24h",
  },
  {
    id: "variant_execution_7d",
    label: "Variant execution (7d)",
    eventType: "executed",
    status: "executed",
    capabilityName: "run_variant",
    timeWindow: "7d",
  },
  {
    id: "validation_focus_7d",
    label: "Validation focus (7d)",
    eventType: "all",
    status: "all",
    capabilityName: "request_synthetic_validation",
    timeWindow: "7d",
  },
];

function formatJsonPreview(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

function formatDateCompact(value?: string | null): string {
  if (!value) return "unknown date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "unknown date";
  return parsed.toLocaleDateString();
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function collectNumericValues(value: unknown, keys: Set<string>): number[] {
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectNumericValues(item, keys));
  }
  const entries = Object.entries(value as Record<string, unknown>);
  return entries.flatMap(([key, nested]) => {
    const direct = keys.has(key) ? toFiniteNumber(nested) : null;
    return [...(direct == null ? [] : [direct]), ...collectNumericValues(nested, keys)];
  });
}

function keyDiffSummary(
  current: Record<string, unknown>,
  previous: Record<string, unknown>,
): { added: string[]; changed: string[]; removed: string[] } {
  const currentKeys = new Set(Object.keys(current));
  const previousKeys = new Set(Object.keys(previous));
  const added = [...currentKeys].filter((key) => !previousKeys.has(key));
  const removed = [...previousKeys].filter((key) => !currentKeys.has(key));
  const changed = [...currentKeys].filter((key) => {
    if (!previousKeys.has(key)) return false;
    const nextValue = formatJsonPreview(current[key]);
    const prevValue = formatJsonPreview(previous[key]);
    return nextValue !== prevValue;
  });
  return { added, changed, removed };
}

function shortKeyList(keys: string[], max = 6): string {
  if (keys.length === 0) return "None";
  const sliced = keys.slice(0, max);
  return keys.length > max ? `${sliced.join(", ")} +${keys.length - max} more` : sliced.join(", ");
}

function safeRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function buildDetailedDiffEntries(
  current: Record<string, unknown>,
  previous: Record<string, unknown>,
): {
  added: { key: string; current: string }[];
  changed: { key: string; current: string; previous: string }[];
  removed: { key: string; previous: string }[];
} {
  const currentKeys = new Set(Object.keys(current));
  const previousKeys = new Set(Object.keys(previous));
  const added = [...currentKeys]
    .filter((key) => !previousKeys.has(key))
    .map((key) => ({
      key,
      current: formatJsonPreview(current[key]),
    }));
  const removed = [...previousKeys]
    .filter((key) => !currentKeys.has(key))
    .map((key) => ({
      key,
      previous: formatJsonPreview(previous[key]),
    }));
  const changed = [...currentKeys]
    .filter((key) => previousKeys.has(key))
    .map((key) => ({
      key,
      current: formatJsonPreview(current[key]),
      previous: formatJsonPreview(previous[key]),
    }))
    .filter((entry) => entry.current !== entry.previous);
  return { added, changed, removed };
}

type TextDiffLine = { kind: "same" | "added" | "removed"; text: string };

function buildTextDiffLines(previousText: string, currentText: string): TextDiffLine[] {
  const before = previousText.split("\n");
  const after = currentText.split("\n");
  const rows: TextDiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      rows.push({ kind: "same", text: after[j] });
      i += 1;
      j += 1;
      continue;
    }
    if (i + 1 < before.length && before[i + 1] === after[j]) {
      rows.push({ kind: "removed", text: before[i] });
      i += 1;
      continue;
    }
    if (j + 1 < after.length && before[i] === after[j + 1]) {
      rows.push({ kind: "added", text: after[j] });
      j += 1;
      continue;
    }
    rows.push({ kind: "removed", text: before[i] });
    rows.push({ kind: "added", text: after[j] });
    i += 1;
    j += 1;
  }
  while (i < before.length) {
    rows.push({ kind: "removed", text: before[i] });
    i += 1;
  }
  while (j < after.length) {
    rows.push({ kind: "added", text: after[j] });
    j += 1;
  }
  return rows;
}

function getStringDiffCandidates(
  current: Record<string, unknown>,
  previous: Record<string, unknown>,
): { key: string; current: string; previous: string; lines: TextDiffLine[] }[] {
  const keys = Object.keys(current).filter((key) => key in previous);
  return keys
    .map((key) => {
      const next = current[key];
      const prev = previous[key];
      if (typeof next !== "string" || typeof prev !== "string") return null;
      if (next === prev) return null;
      const isCopyLike =
        next.length >= 40 ||
        prev.length >= 40 ||
        next.includes("\n") ||
        prev.includes("\n");
      if (!isCopyLike) return null;
      return {
        key,
        current: next,
        previous: prev,
        lines: buildTextDiffLines(prev, next),
      };
    })
    .filter(Boolean) as { key: string; current: string; previous: string; lines: TextDiffLine[] }[];
}

function budgetSeverity(
  used: number,
  limit: number | null,
  percent: number | null,
): "ok" | "warn" | "danger" {
  if (limit == null) return "ok";
  if (used >= limit) return "danger";
  if ((percent ?? 0) >= 80) return "warn";
  return "ok";
}

function resolveSinceForWindow(windowId: "all" | "24h" | "7d"): string | null {
  if (windowId === "all") return null;
  const now = Date.now();
  const deltaMs = windowId === "24h" ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
  return new Date(now - deltaMs).toISOString();
}

export default function AgentRunsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
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
    : "all") as "all" | "failed" | "policy" | "executed";
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
  const [actions, setActions] = useState<AgentAction[]>([]);
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
  const [timelineFilter, setTimelineFilter] = useState<
    "all" | "failed" | "policy" | "executed"
  >(initialTimelineFilter);
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

  const [createForm, setCreateForm] = useState({
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
          setSelectedRunId(nextRuns[0].id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent runs.");
    } finally {
      setLoading(false);
    }
  }, [experimentIdParam, runIdParam, selectedRunId, userId]);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent run.");
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
    const counters = { total: 0, running: 0, planned: 0, failed: 0, completed: 0 };
    (runs ?? []).forEach((run) => {
      counters.total += 1;
      const status = String(run.status ?? "").toLowerCase();
      if (status === "running") counters.running += 1;
      if (status === "planned") counters.planned += 1;
      if (status === "failed") counters.failed += 1;
      if (status === "completed") counters.completed += 1;
    });
    return counters;
  }, [runs]);

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

  const timelineEvents = useMemo(() => {
    return (runEvents ?? []).map((event) => ({
      id: event.id,
      actionId: event.action_id ?? null,
      sequence: event.sequence,
      capability: event.capability_name ?? "unknown",
      status: String(event.status || "unknown").toLowerCase(),
      when: event.timestamp ?? null,
      note: event.note ?? null,
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
              { label: "Running", value: runCounters.running },
              { label: "Planned", value: runCounters.planned },
              {
                label: "Failed",
                value: runCounters.failed,
                tone: runCounters.failed > 0 ? "warning" : "default",
              },
            ]}
            error={error}
          />

          <div className="agent-workspace">
            <section className="panel__card panel__card--secondary agent-workspace__rail">
              <div className="panel__card">
                <div className="panel__header">
                  <h3>Run selection</h3>
                </div>
                <div className="list">
                  {(runs ?? []).map((run) => {
                    const active = run.id === selectedRunId;
                    const label = run.experiment_id
                      ? `Experiment ${String(run.experiment_id).slice(0, 8)}`
                      : `Run ${String(run.id).slice(0, 8)}`;
                    return (
                      <button
                        key={run.id}
                        type="button"
                        className={`list__row ${active ? "is-active" : ""}`}
                        onClick={() => {
                          setSelectedRunId(run.id);
                          setSelectedEventId(null);
                        }}
                      >
                        <div className="list__title">{label}</div>
                        <div className="list__meta">
                          {run.status ?? "unknown"} · {run.state ?? "unknown"}
                        </div>
                      </button>
                    );
                  })}
                  {runs.length === 0 && (
                    <div className="panel__muted">No agent runs yet.</div>
                  )}
                </div>
              </div>
              <div className="panel__card">
                <div className="panel__header">
                  <h4>Run stats</h4>
                </div>
                <div className="agent-ops-summary">
                  <span className="panel__badge panel__badge--secondary">
                    Total: {runCounters.total}
                  </span>
                  <span className="panel__badge panel__badge--secondary">
                    Running: {runCounters.running}
                  </span>
                  <span className="panel__badge panel__badge--secondary">
                    Planned: {runCounters.planned}
                  </span>
                  <span className="panel__badge panel__badge--secondary">
                    Completed: {runCounters.completed}
                  </span>
                  <span className="panel__badge panel__badge--secondary">
                    Failed: {runCounters.failed}
                  </span>
                </div>
              </div>
              <OperatorConsoleChat
                run={selectedRun}
                actions={actions}
                events={runEvents}
                selectedAction={selectedAction}
                nextRecommendedAction={nextRecommendedAction}
                onJumpToNextAction={() => {
                  if (nextRecommendedAction.action?.id) {
                    setSelectedActionId(nextRecommendedAction.action.id);
                  }
                }}
                onOpenExperiment={() => {
                  if (selectedRun?.experiment_id) {
                    const params = new URLSearchParams();
                    params.set("experiment_id", selectedRun.experiment_id);
                    params.set("run_id", selectedRun.id);
                    router.push(`/experiments?${params.toString()}`);
                  }
                }}
                onOpenValidation={() => router.push("/validation")}
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

            <section className="panel__card panel__card--secondary agent-workspace__main">
              {selectedRun ? (
                <div className="agent-run-summary">
                  <div className="panel__header">
                    <h4>Execution controls</h4>
                    <span className="panel__badge panel__badge--secondary">
                      Current: {selectedRun.state ?? "unknown"}
                    </span>
                  </div>
                  <div className="agent-run-summary__chips">
                    <span className="panel__badge panel__badge--secondary">
                      Status: {selectedRun.status ?? "unknown"}
                    </span>
                    <span className="panel__badge panel__badge--secondary">
                      Approval:{" "}
                      {selectedRun.requires_approval ? "required" : "auto-execute safe"}
                    </span>
                    <span className="panel__badge panel__badge--secondary">
                      Mode: {selectedRun.run_mode || "plan_only"}
                    </span>
                  </div>
                  <details className="agent-flow-details">
                    <summary>View full execution flow</summary>
                    <div className="flow-rail">
                      <div className="flow-rail__steps">
                        {flowSteps.map((step, index) => (
                          <div key={step.id} className={`flow-rail__step ${step.className}`}>
                            <span className="flow-rail__index">{index + 1}</span>
                            <span className="flow-rail__label">{step.label}</span>
                            <span className="flow-rail__status">{step.status}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </details>
                </div>
              ) : null}
              <div className="panel__card">
                <div className="panel__header">
                  <h3>Action queue</h3>
                  <div className="panel__meta agent-queue-controls">
                    {selectedRun?.experiment_id && (
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() =>
                          router.push(`/experiments?experiment_id=${selectedRun.experiment_id}`)
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
                      <div className="panel__header">
                        <h4>Next recommended action</h4>
                        {nextRecommendedAction.action ? (
                          <span className="panel__badge panel__badge--secondary">
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

                    <div className="panel__meta-strip">
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
                    <div className="agent-budget-grid">
                      <div
                        className={`agent-budget-card ${
                          budgetState.actionSeverity === "warn"
                            ? "is-warn"
                            : budgetState.actionSeverity === "danger"
                              ? "is-danger"
                              : ""
                        }`}
                      >
                        <div className="agent-budget-card__header">
                          <strong>Action budget</strong>
                          <span>
                            {budgetTelemetry.executedActions}/
                            {budgetTelemetry.maxActions ?? "—"}
                          </span>
                        </div>
                        <div className="agent-budget-card__bar">
                          <div
                            className="agent-budget-card__fill"
                            style={{
                              width:
                                budgetTelemetry.actionPct == null
                                  ? "0%"
                                  : `${budgetTelemetry.actionPct}%`,
                            }}
                          />
                        </div>
                      </div>
                      <div
                        className={`agent-budget-card ${
                          budgetState.variantSeverity === "warn"
                            ? "is-warn"
                            : budgetState.variantSeverity === "danger"
                              ? "is-danger"
                              : ""
                        }`}
                      >
                        <div className="agent-budget-card__header">
                          <strong>Variant run budget</strong>
                          <span>
                            {budgetTelemetry.executedVariantRuns}/
                            {budgetTelemetry.maxVariantRuns ?? "—"}
                          </span>
                        </div>
                        <div className="agent-budget-card__bar">
                          <div
                            className="agent-budget-card__fill"
                            style={{
                              width:
                                budgetTelemetry.variantPct == null
                                  ? "0%"
                                  : `${budgetTelemetry.variantPct}%`,
                            }}
                          />
                        </div>
                      </div>
                      <div
                        className={`agent-budget-card ${
                          budgetState.costSeverity === "warn"
                            ? "is-warn"
                            : budgetState.costSeverity === "danger"
                              ? "is-danger"
                              : ""
                        }`}
                      >
                        <div className="agent-budget-card__header">
                          <strong>Estimated spend</strong>
                          <span>
                            ${budgetTelemetry.totalCostUsd.toFixed(2)}
                            {budgetTelemetry.maxCostUsd != null
                              ? ` / $${budgetTelemetry.maxCostUsd.toFixed(2)}`
                              : ""}
                          </span>
                        </div>
                        <div className="agent-budget-card__bar">
                          <div
                            className="agent-budget-card__fill"
                            style={{
                              width:
                                budgetTelemetry.costPct == null
                                  ? "0%"
                                  : `${budgetTelemetry.costPct}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                    {budgetState.actionBlocked ||
                    budgetState.variantBlocked ||
                    budgetState.costBlocked ? (
                      <div className="panel__notice panel__notice--warning">
                        Budget guardrail active:{" "}
                        {budgetState.actionBlocked
                          ? "max actions reached."
                          : budgetState.variantBlocked
                            ? "max variant runs reached for run_variant."
                            : "max cost reached."}{" "}
                        Proposed risky approvals are disabled until budget changes.
                      </div>
                    ) : null}

                    <div className="agent-ops-summary">
                      <span className="panel__badge panel__badge--secondary">
                        Proposed: {actionCounters.proposed}
                      </span>
                      <span className="panel__badge panel__badge--secondary">
                        Approved: {actionCounters.approved}
                      </span>
                      <span className="panel__badge panel__badge--secondary">
                        Executing: {actionCounters.executing}
                      </span>
                      <span className="panel__badge panel__badge--secondary">
                        Executed: {actionCounters.executed}
                      </span>
                      <span className="panel__badge panel__badge--secondary">
                        Failed: {actionCounters.failed}
                      </span>
                    </div>

                    <div className="table">
                      <div className="table__header">
                        <div className="table__cell">#</div>
                        <div className="table__cell">Capability</div>
                        <div className="table__cell">Status</div>
                        <div className="table__cell">Rationale</div>
                        <div className="table__cell">Actions</div>
                      </div>
                      {(actions ?? []).map((a) => {
                        const guardrailReasons = getGuardrailReasonsForAction(a);
                        const hasGuardrailBlock = guardrailReasons.length > 0;
                        return (
                        <div
                          key={a.id}
                          className={`table__row ${selectedAction?.id === a.id ? "is-active" : ""}`}
                          onClick={() => setSelectedActionId(a.id)}
                        >
                          <div className="table__cell" data-label="#">
                            {a.sequence}
                          </div>
                          <div className="table__cell" data-label="Capability">
                            <div className="table__strong">{a.capability_name}</div>
                            {a.capability_version && (
                              <div className="table__muted">{a.capability_version}</div>
                            )}
                          </div>
                          <div className="table__cell" data-label="Status">
                            {a.status}
                          </div>
                          <div
                            className="table__cell table__cell--rationale table__muted"
                            data-label="Rationale"
                          >
                            {a.rationale || (a.error ? `Error: ${a.error}` : "—")}
                          </div>
                          <div className="table__cell table__actions" data-label="Actions">
                            {a.status === "proposed" ? (
                              <>
                                <button
                                  type="button"
                                  className="button button--ghost button--sm"
                                  onClick={() => handleDecision(a.id, "approve")}
                                  disabled={loading || hasGuardrailBlock}
                                  title={guardrailReasons[0] || undefined}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="button button--ghost button--sm"
                                  onClick={() => handleDecision(a.id, "reject")}
                                  disabled={loading}
                                >
                                  Reject
                                </button>
                              </>
                            ) : (
                              <button
                                type="button"
                                className="button button--ghost button--sm"
                                onClick={() => {
                                  const payload = formatJsonPreview({
                                    inputs: a.inputs,
                                    outputs: a.outputs,
                                  });
                                  window.navigator.clipboard?.writeText(payload);
                                }}
                                disabled={loading}
                              >
                                Copy I/O
                              </button>
                            )}
                            {hasGuardrailBlock ? (
                              <div className="agent-guardrail-list">
                                {guardrailReasons.map((reason) => (
                                  <span key={`${a.id}-${reason}`} className="panel__badge panel__badge--warning">
                                    {reason}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        </div>
                        );
                      })}
                      {actions.length === 0 && (
                        <div className="panel__muted">
                          No actions recorded yet. Next: we’ll add plan generation and execution ticks.
                        </div>
                      )}
                    </div>
                    <section className="agent-timeline">
                      <div className="panel__header">
                        <h4>Execution timeline</h4>
                        <div className="panel__row panel__row--compact">
                          <span className="panel__badge panel__badge--secondary">
                            {timelineEvents.length}/{actions.length} events
                          </span>
                          <span className="panel__badge panel__badge--secondary">
                            Live: {livePollingActive ? "on" : "paused"}
                          </span>
                          {eventsPage?.has_more_before ? (
                            <button
                              type="button"
                              className="button button--ghost button--sm"
                              onClick={loadOlderEvents}
                              disabled={loadingOlderEvents || loading}
                            >
                              {loadingOlderEvents ? "Loading..." : "Load older events"}
                            </button>
                          ) : null}
                        </div>
                      </div>
                      <div className="agent-timeline__filters">
                        {TIMELINE_PRESETS.map((preset) => (
                          <button
                            key={preset.id}
                            type="button"
                            className={`button button--ghost button--sm ${
                              timelinePreset === preset.id ? "is-active" : ""
                            }`}
                            onClick={() => applyTimelinePreset(preset.id)}
                          >
                            {preset.label}
                          </button>
                        ))}
                        {timelinePreset === "custom" ? (
                          <span className="panel__badge panel__badge--secondary">Custom view</span>
                        ) : null}
                      </div>
                      {copyLinkNotice ? (
                        <div
                          className={`panel__notice ${
                            copyLinkNotice.type === "error"
                              ? "panel__notice--error"
                              : "panel__notice--info"
                          }`}
                        >
                          {copyLinkNotice.text}
                        </div>
                      ) : null}
                      <div className="agent-timeline__filters">
                        <button
                          type="button"
                          className={`button button--ghost button--sm ${
                            timelineFilter === "all" ? "is-active" : ""
                          }`}
                          onClick={() => setTimelineFilter("all")}
                        >
                          All
                        </button>
                        <button
                          type="button"
                          className={`button button--ghost button--sm ${
                            timelineFilter === "failed" ? "is-active" : ""
                          }`}
                          onClick={() => setTimelineFilter("failed")}
                        >
                          Failed
                        </button>
                        <button
                          type="button"
                          className={`button button--ghost button--sm ${
                            timelineFilter === "policy" ? "is-active" : ""
                          }`}
                          onClick={() => setTimelineFilter("policy")}
                        >
                          Policy
                        </button>
                        <button
                          type="button"
                          className={`button button--ghost button--sm ${
                            timelineFilter === "executed" ? "is-active" : ""
                          }`}
                          onClick={() => setTimelineFilter("executed")}
                        >
                          Executed
                        </button>
                        <select
                          className="input"
                          style={{ minWidth: 170 }}
                          value={timelineStatusFilter}
                          onChange={(event) =>
                            setTimelineStatusFilter(event.target.value as TimelineStatusFilter)
                          }
                        >
                          <option value="all">All statuses</option>
                          <option value="proposed">Proposed</option>
                          <option value="approved">Approved</option>
                          <option value="executing">Executing</option>
                          <option value="executed">Executed</option>
                          <option value="failed">Failed</option>
                          <option value="rejected">Rejected</option>
                        </select>
                        <select
                          className="input"
                          style={{ minWidth: 220 }}
                          value={timelineCapabilityFilter}
                          onChange={(event) => setTimelineCapabilityFilter(event.target.value)}
                        >
                          {timelineCapabilityOptions.map((item) => (
                            <option key={item} value={item}>
                              {item === "all" ? "All capabilities" : item}
                            </option>
                          ))}
                        </select>
                        <select
                          className="input"
                          style={{ minWidth: 160 }}
                          value={timelineTimeWindow}
                          onChange={(event) =>
                            setTimelineTimeWindow(event.target.value as TimelineWindowFilter)
                          }
                        >
                          <option value="all">All time</option>
                          <option value="24h">Last 24h</option>
                          <option value="7d">Last 7d</option>
                        </select>
                      </div>
                      {timelineEvents.length === 0 ? (
                        <p className="panel__muted">No timeline events yet.</p>
                      ) : (
                        <div className="agent-timeline__list">
                          {timelineEvents.map((event) => (
                            <div
                              key={event.id}
                              id={`agent-event-${event.id}`}
                              className={`agent-timeline__item ${
                                selectedEventId === event.id ? "is-focused" : ""
                              }`}
                              onClick={() => setSelectedEventId(event.id)}
                            >
                              <div className="agent-timeline__meta">
                                <span className="agent-timeline__seq">#{event.sequence}</span>
                                <span className="agent-timeline__cap">{event.capability}</span>
                                <span
                                  className={`agent-timeline__status is-${event.status}`}
                                >
                                  {event.status}
                                </span>
                                <span className="agent-timeline__time">
                                  {event.when
                                    ? new Date(event.when).toLocaleString()
                                    : "time unavailable"}
                                </span>
                              </div>
                              <div className="agent-timeline__actions">
                                {event.actionId ? (
                                  <button
                                    type="button"
                                    className="button button--ghost button--sm"
                                    onClick={(clickEvent) => {
                                      clickEvent.stopPropagation();
                                      setSelectedEventId(event.id);
                                      setSelectedActionId(event.actionId);
                                      setDiffDrawerOpen(false);
                                    }}
                                  >
                                    Focus action
                                  </button>
                                ) : null}
                                {selectedRun?.experiment_id || event.anchors?.experiment_id ? (
                                  <button
                                    type="button"
                                    className="button button--ghost button--sm"
                                    onClick={(clickEvent) => {
                                      clickEvent.stopPropagation();
                                      setSelectedEventId(event.id);
                                      router.push(
                                        `/experiments?experiment_id=${
                                          event.anchors?.experiment_id ||
                                          selectedRun?.experiment_id
                                        }`,
                                      )
                                    }}
                                  >
                                    Open experiment
                                  </button>
                                ) : null}
                                {event.anchors?.validation_job_id ? (
                                  <button
                                    type="button"
                                    className="button button--ghost button--sm"
                                    onClick={(clickEvent) => {
                                      clickEvent.stopPropagation();
                                      setSelectedEventId(event.id);
                                      router.push("/validation");
                                    }}
                                  >
                                    Open validation
                                  </button>
                                ) : null}
                                <button
                                  type="button"
                                  className="button button--ghost button--sm"
                                  onClick={async (clickEvent) => {
                                    clickEvent.stopPropagation();
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
                                  }}
                                >
                                  Copy link
                                </button>
                              </div>
                              {event.note ? (
                                <p
                                  className={`agent-timeline__note ${
                                    event.isPolicy ? "is-policy" : ""
                                  }`}
                                >
                                  {event.note}
                                </p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                    {selectedAction ? (
                      <section className="agent-action-detail">
                        <div className="panel__header">
                          <h4>Selected action details</h4>
                          <span className="panel__badge panel__badge--secondary">
                            {selectedAction.capability_name}
                          </span>
                        </div>
                        <p className="panel__muted">
                          {CAPABILITY_EXPLAIN[selectedAction.capability_name]?.summary ??
                            "Capability summary not yet documented."}
                        </p>
                        <p className="panel__subheading">What it changes</p>
                        <ul className="panel__list panel__list--compact">
                          {(
                            CAPABILITY_EXPLAIN[selectedAction.capability_name]
                              ?.sideEffects ?? ["No side-effect metadata yet."]
                          ).map((effect, index) => (
                            <li key={`${effect}-${index}`}>{effect}</li>
                          ))}
                        </ul>
                        <p className="panel__subheading">Rationale and confidence</p>
                        <p className="panel__muted">
                          {selectedAction.rationale || "No rationale captured."}
                        </p>
                        <p className="panel__muted">
                          Confidence:{" "}
                          {typeof selectedAction.confidence === "number"
                            ? selectedAction.confidence.toFixed(2)
                            : "—"}
                        </p>
                        <p className="panel__subheading">Linked artifacts</p>
                        <div className="panel__actions">
                          {selectedAction.variant_id ? (
                            <button
                              type="button"
                              className="button button--ghost button--sm"
                              onClick={() =>
                                selectedRun?.experiment_id
                                  ? router.push(
                                      `/experiments?experiment_id=${selectedRun.experiment_id}`,
                                    )
                                  : null
                              }
                            >
                              Variant: {selectedAction.variant_id.slice(0, 8)}
                            </button>
                          ) : null}
                          {selectedAction.validation_job_id ? (
                            <button
                              type="button"
                              className="button button--ghost button--sm"
                              onClick={() => router.push("/validation")}
                            >
                              Validation job:{" "}
                              {selectedAction.validation_job_id.slice(0, 8)}
                            </button>
                          ) : null}
                          {(() => {
                            const outputs = (selectedAction.outputs ??
                              {}) as Record<string, unknown>;
                            const metricId =
                              typeof outputs.metric_id === "string"
                                ? outputs.metric_id
                                : null;
                            if (!metricId) return null;
                            return (
                              <button
                                type="button"
                                className="button button--ghost button--sm"
                                onClick={() =>
                                  selectedRun?.experiment_id
                                    ? router.push(
                                        `/experiments?experiment_id=${selectedRun.experiment_id}`,
                                      )
                                    : null
                                }
                              >
                                Metric: {metricId.slice(0, 8)}
                              </button>
                            );
                          })()}
                        </div>
                        <p className="panel__subheading">Artifact diff preview</p>
                        <div className="agent-diff-grid">
                          <div className="agent-diff-card">
                            <div className="agent-diff-card__title">
                              vs previous action
                              {actionDiffs?.previousAction
                                ? ` #${actionDiffs.previousAction.sequence}`
                                : ""}
                            </div>
                            <div className="agent-diff-card__meta">
                              Added:{" "}
                              {shortKeyList(actionDiffs?.vsPreviousAction.added ?? [])}
                            </div>
                            <div className="agent-diff-card__meta">
                              Changed:{" "}
                              {shortKeyList(actionDiffs?.vsPreviousAction.changed ?? [])}
                            </div>
                            <div className="agent-diff-card__meta">
                              Removed:{" "}
                              {shortKeyList(actionDiffs?.vsPreviousAction.removed ?? [])}
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
                              Added:{" "}
                              {shortKeyList(actionDiffs?.vsPreviousCapability.added ?? [])}
                            </div>
                            <div className="agent-diff-card__meta">
                              Changed:{" "}
                              {shortKeyList(actionDiffs?.vsPreviousCapability.changed ?? [])}
                            </div>
                            <div className="agent-diff-card__meta">
                              Removed:{" "}
                              {shortKeyList(actionDiffs?.vsPreviousCapability.removed ?? [])}
                            </div>
                          </div>
                        </div>
                        <p className="panel__muted">
                          Diff compares output payload keys, so operators can audit what changed
                          before approving downstream actions.
                        </p>
                        <div className="panel__actions">
                          <button
                            type="button"
                            className="button button--ghost button--sm"
                            onClick={() => setDiffDrawerOpen(true)}
                          >
                            Open detailed diff
                          </button>
                        </div>
                      </section>
                    ) : null}
                  </>
                )}
              </div>
            </section>
          </div>
        </div>

        {drawerOpen && (
          <div className="drawer">
            <div className="drawer__overlay" onClick={() => setDrawerOpen(false)} />
            <div className="drawer__panel">
              <div className="drawer__header">
                <h2 className="drawer__title">New agent run</h2>
                <button className="drawer__close" onClick={() => setDrawerOpen(false)}>
                  ×
                </button>
              </div>
              <div className="drawer__body">
                <label className="field">
                  <span className="field__label">Experiment (optional)</span>
                  <select
                    className="field__input"
                    value={createForm.experiment_id}
                    onChange={(e) =>
                      setCreateForm((p) => ({ ...p, experiment_id: e.target.value }))
                    }
                  >
                    <option value="">None (global agent run)</option>
                    {experiments.map((experiment) => (
                      <option key={experiment.id} value={experiment.id}>
                        {experiment.name || "Untitled"} · {experiment.id.slice(0, 8)} ·{" "}
                        {formatDateCompact(experiment.updated_at || experiment.created_at)}
                      </option>
                    ))}
                  </select>
                  {experiments.length === 0 ? (
                    <div className="panel__muted">
                      No experiments found in current scope. You can still create a global run.
                    </div>
                  ) : null}
                </label>

                <details className="admin-advanced-defaults">
                  <summary>Manual experiment id (advanced)</summary>
                  <label className="field">
                    <span className="field__label">Override with UUID</span>
                    <input
                      className="field__input"
                      value={createForm.experiment_id}
                      onChange={(e) =>
                        setCreateForm((p) => ({ ...p, experiment_id: e.target.value.trim() }))
                      }
                      placeholder="paste experiment uuid"
                    />
                  </label>
                </details>

                <label className="field field--row">
                  <span className="field__label">Requires approval</span>
                  <input
                    type="checkbox"
                    checked={createForm.requires_approval}
                    onChange={(e) =>
                      setCreateForm((p) => ({ ...p, requires_approval: e.target.checked }))
                    }
                  />
                </label>

                <label className="field">
                  <span className="field__label">Run mode</span>
                  <select
                    className="field__input"
                    value={createForm.run_mode}
                    onChange={(e) =>
                      setCreateForm((p) => ({
                        ...p,
                        run_mode:
                          e.target.value === "auto_execute_safe"
                            ? "auto_execute_safe"
                            : "plan_only",
                      }))
                    }
                  >
                    <option value="plan_only">Plan only (recommended)</option>
                    <option value="auto_execute_safe">Auto-execute safe steps</option>
                  </select>
                </label>

                <label className="field">
                  <span className="field__label">Allowed capabilities</span>
                  <textarea
                    className="field__input field__textarea"
                    value={createForm.allowed_capabilities.join("\n")}
                    onChange={(e) =>
                      setCreateForm((p) => ({
                        ...p,
                        allowed_capabilities: e.target.value
                          .split("\n")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      }))
                    }
                    rows={7}
                  />
                </label>

                <label className="field">
                  <span className="field__label">Objective (JSON)</span>
                  <textarea
                    className="field__input field__textarea"
                    value={formatJsonPreview(createForm.objective)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value || "{}");
                        setCreateForm((p) => ({ ...p, objective: parsed }));
                      } catch {
                        // keep last valid json
                      }
                    }}
                    rows={8}
                  />
                </label>

                <label className="field">
                  <span className="field__label">Budgets (JSON)</span>
                  <textarea
                    className="field__input field__textarea"
                    value={formatJsonPreview(createForm.budgets)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value || "{}");
                        setCreateForm((p) => ({ ...p, budgets: parsed }));
                      } catch {
                        // keep last valid json
                      }
                    }}
                    rows={6}
                  />
                </label>

                <label className="field">
                  <span className="field__label">Approval policy (JSON)</span>
                  <textarea
                    className="field__input field__textarea"
                    value={formatJsonPreview(createForm.approval_policy)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value || "{}");
                        setCreateForm((p) => ({ ...p, approval_policy: parsed }));
                      } catch {
                        // keep last valid json
                      }
                    }}
                    rows={6}
                  />
                </label>
              </div>
              <div className="drawer__footer">
                <button className="button button--ghost" onClick={() => setDrawerOpen(false)}>
                  Cancel
                </button>
                <button
                  className="button button--ghost"
                  onClick={() => handleCreate()}
                  disabled={!userId || loading}
                >
                  Create run
                </button>
              </div>
            </div>
          </div>
        )}

        {diffDrawerOpen && selectedAction && selectedActionDeepDiff && (
          <div className="drawer">
            <div className="drawer__overlay" onClick={() => setDiffDrawerOpen(false)} />
            <div className="drawer__panel">
              <div className="drawer__header">
                <h2 className="drawer__title">Artifact diff details</h2>
                <button className="drawer__close" onClick={() => setDiffDrawerOpen(false)}>
                  ×
                </button>
              </div>
              <div className="drawer__body">
                <p className="panel__muted">
                  Action #{selectedAction.sequence} · {selectedAction.capability_name}
                </p>

                <p className="panel__subheading">Output changes vs previous action</p>
                <div className="agent-diff-detail-grid">
                  <div>
                    <strong>Added</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(selectedActionDeepDiff.outputsVsPreviousAction.added)}
                    </pre>
                  </div>
                  <div>
                    <strong>Changed</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(selectedActionDeepDiff.outputsVsPreviousAction.changed)}
                    </pre>
                  </div>
                  <div>
                    <strong>Removed</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(selectedActionDeepDiff.outputsVsPreviousAction.removed)}
                    </pre>
                  </div>
                </div>

                <p className="panel__subheading">Output changes vs previous same capability</p>
                <div className="agent-diff-detail-grid">
                  <div>
                    <strong>Added</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(
                        selectedActionDeepDiff.outputsVsPreviousCapability.added,
                      )}
                    </pre>
                  </div>
                  <div>
                    <strong>Changed</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(
                        selectedActionDeepDiff.outputsVsPreviousCapability.changed,
                      )}
                    </pre>
                  </div>
                  <div>
                    <strong>Removed</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(
                        selectedActionDeepDiff.outputsVsPreviousCapability.removed,
                      )}
                    </pre>
                  </div>
                </div>

                <p className="panel__subheading">Input changes (traceability)</p>
                <div className="agent-diff-detail-grid">
                  <div>
                    <strong>vs previous action</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(
                        selectedActionDeepDiff.inputsVsPreviousAction.changed,
                      )}
                    </pre>
                  </div>
                  <div>
                    <strong>vs previous same capability</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(
                        selectedActionDeepDiff.inputsVsPreviousCapability.changed,
                      )}
                    </pre>
                  </div>
                </div>

                <p className="panel__subheading">Snapshot payloads</p>
                <div className="agent-diff-detail-grid">
                  <div>
                    <strong>Current inputs</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(selectedActionDeepDiff.currentInputs)}
                    </pre>
                  </div>
                  <div>
                    <strong>Current outputs</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(selectedActionDeepDiff.currentOutputs)}
                    </pre>
                  </div>
                  <div>
                    <strong>Previous action outputs</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(selectedActionDeepDiff.previousOutputs)}
                    </pre>
                  </div>
                  <div>
                    <strong>Previous same-capability outputs</strong>
                    <pre className="panel__pre">
                      {formatJsonPreview(
                        selectedActionDeepDiff.previousCapabilityOutputs,
                      )}
                    </pre>
                  </div>
                </div>

                <p className="panel__subheading">Copy diff mode (string-heavy fields)</p>
                <label className="panel__toggle">
                  <input
                    type="checkbox"
                    checked={hideUnchangedDiffLines}
                    onChange={(event) => setHideUnchangedDiffLines(event.target.checked)}
                  />
                  Hide unchanged lines
                </label>
                {(selectedActionDeepDiff.copyDiffVsPreviousAction.length === 0 &&
                  selectedActionDeepDiff.copyDiffVsPreviousCapability.length === 0) ? (
                  <p className="panel__muted">
                    No string-heavy output fields changed for this action.
                  </p>
                ) : null}
                {selectedActionDeepDiff.copyDiffVsPreviousAction.length > 0 ? (
                  <div className="agent-copy-diff-block">
                    <strong>vs previous action</strong>
                    {selectedActionDeepDiff.copyDiffVsPreviousAction.map((entry) => (
                      <details key={`prev-${entry.key}`} className="agent-copy-diff">
                        <summary>{entry.key}</summary>
                        <div className="agent-copy-diff__lines">
                          {entry.lines
                            .filter((line) =>
                              hideUnchangedDiffLines ? line.kind !== "same" : true,
                            )
                            .map((line, index) => (
                            <div
                              key={`${entry.key}-${index}`}
                              className={`agent-copy-diff__line is-${line.kind}`}
                            >
                              <span className="agent-copy-diff__prefix">
                                {line.kind === "added"
                                  ? "+"
                                  : line.kind === "removed"
                                    ? "-"
                                    : " "}
                              </span>
                              <span className="agent-copy-diff__text">{line.text || " "}</span>
                            </div>
                            ))}
                        </div>
                      </details>
                    ))}
                  </div>
                ) : null}
                {selectedActionDeepDiff.copyDiffVsPreviousCapability.length > 0 ? (
                  <div className="agent-copy-diff-block">
                    <strong>vs previous same capability</strong>
                    {selectedActionDeepDiff.copyDiffVsPreviousCapability.map((entry) => (
                      <details key={`cap-${entry.key}`} className="agent-copy-diff">
                        <summary>{entry.key}</summary>
                        <div className="agent-copy-diff__lines">
                          {entry.lines
                            .filter((line) =>
                              hideUnchangedDiffLines ? line.kind !== "same" : true,
                            )
                            .map((line, index) => (
                            <div
                              key={`${entry.key}-cap-${index}`}
                              className={`agent-copy-diff__line is-${line.kind}`}
                            >
                              <span className="agent-copy-diff__prefix">
                                {line.kind === "added"
                                  ? "+"
                                  : line.kind === "removed"
                                    ? "-"
                                    : " "}
                              </span>
                              <span className="agent-copy-diff__text">{line.text || " "}</span>
                            </div>
                            ))}
                        </div>
                      </details>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="drawer__footer">
                <button className="button button--ghost" onClick={() => setDiffDrawerOpen(false)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
