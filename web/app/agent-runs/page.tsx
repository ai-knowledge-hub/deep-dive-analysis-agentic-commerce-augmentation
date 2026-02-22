"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { DetailHeader } from "../../components/layout/DetailHeader";

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

export default function AgentRunsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
  const userId = user?.id ?? null;

  const experimentIdParam = searchParams.get("experiment_id")?.trim() || "";
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [runEvents, setRunEvents] = useState<AgentRunEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [diffDrawerOpen, setDiffDrawerOpen] = useState(false);
  const [hideUnchangedDiffLines, setHideUnchangedDiffLines] = useState(true);
  const [timelineFilter, setTimelineFilter] = useState<
    "all" | "failed" | "policy" | "executed"
  >("all");
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);

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
      if (!selectedRunId && nextRuns.length > 0) {
        setSelectedRunId(nextRuns[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent runs.");
    } finally {
      setLoading(false);
    }
  }, [experimentIdParam, selectedRunId, userId]);

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
            limit: 500,
            event_type: timelineFilter,
          },
          userId,
        ),
      ]);
      setSelectedRun(response.run ?? null);
      setActions(response.actions ?? []);
      setRunEvents(eventsResponse.events ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent run.");
    } finally {
      setLoading(false);
    }
  }, [selectedRunId, timelineFilter, userId]);

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

  const selectedSummary = useMemo(() => {
    if (!selectedRun) return null;
    return `${selectedRun.status ?? "unknown"} · ${selectedRun.state ?? "unknown"}`;
  }, [selectedRun]);

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

  const getBudgetRiskForAction = useCallback(
    (
      action: AgentAction,
    ): {
      risky: boolean;
      reason: string | null;
    } => {
      if (String(action.status || "").toLowerCase() !== "proposed") {
        return { risky: false, reason: null };
      }
      if (budgetState.actionBlocked) {
        return {
          risky: true,
          reason: "Action budget reached. Increase budget or execute fewer actions.",
        };
      }
      if (
        action.capability_name === "run_variant" &&
        budgetState.variantBlocked
      ) {
        return {
          risky: true,
          reason: "Variant run budget reached. Increase budget or review completed runs.",
        };
      }
      if (budgetState.costBlocked) {
        return {
          risky: true,
          reason: "Cost budget reached. Increase max_cost_usd before approving new actions.",
        };
      }
      return { risky: false, reason: null };
    },
    [budgetState.actionBlocked, budgetState.variantBlocked, budgetState.costBlocked],
  );

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
        router.replace(
          run.experiment_id ? `/agent-runs?experiment_id=${run.experiment_id}` : "/agent-runs",
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
        onNewConversation={() => router.push("/")}
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
          title="Agent runs"
          subtitle={selectedSummary || "Governed lab automation (planned)"}
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

        <section className="panel__card panel__card--secondary panel__card--full-row">
          <div className="panel__header">
            <div className="panel__meta panel__meta--stack">
              <h3>Agent operator workspace</h3>
              <div className="panel__subtitle">
                Agents propose actions. Guardrails and approvals are enforced by the platform.
              </div>
            </div>
          </div>
          <p className="panel__subheading">Step 1 · Select scope and run</p>
          <p className="panel__step-helper">
            Define the run scope, create a run when needed, then select the run you want to operate.
          </p>

          {error && <div className="panel__error">{error}</div>}

          <div className="detail__grid">
            <section className="panel__card panel__card--secondary">
              <p className="panel__subheading">Step 1 · Scope and run selection</p>
              <p className="panel__step-helper">
                Use recent runs to inspect history and continue from the current state.
              </p>
              <div className="panel__card">
                <div className="panel__header">
                  <h3>Recent</h3>
                  <button
                    type="button"
                    className="button button--primary-subtle"
                    onClick={() => setDrawerOpen(true)}
                    disabled={!userId || loading}
                  >
                    New run
                  </button>
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
                        onClick={() => setSelectedRunId(run.id)}
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
            </section>

            <section className="panel__card panel__card--secondary">
              <p className="panel__subheading">Step 2 · Control execution</p>
              <p className="panel__step-helper">
                Start, pause, or refresh the selected run while keeping policy and budgets enforced.
              </p>
              {selectedRun ? (
                <div className="flow-rail">
                  <div className="flow-rail__header">
                    <h4>Execution flow</h4>
                    <span className="flow-rail__status">
                      Current: {selectedRun.state ?? "unknown"}
                    </span>
                  </div>
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
              ) : null}
              <div className="panel__card">
                <div className="panel__header">
                  <h3>Action queue</h3>
                  <div className="panel__meta">
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
                    <p className="panel__subheading">Step 3 · Review approvals and audit</p>
                    <p className="panel__step-helper">
                      Approve or reject proposed actions and inspect rationale plus I/O for traceability.
                    </p>
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
                        const budgetRisk = getBudgetRiskForAction(a);
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
                                  disabled={loading || budgetRisk.risky}
                                  title={budgetRisk.reason || undefined}
                                >
                                  Approve
                                </button>
                                {budgetRisk.risky && budgetRisk.reason ? (
                                  <span className="panel__badge panel__badge--warning">
                                    {budgetRisk.reason}
                                  </span>
                                ) : null}
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
                        <span className="panel__badge panel__badge--secondary">
                          {timelineEvents.length}/{actions.length} events
                        </span>
                      </div>
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
                      </div>
                      {timelineEvents.length === 0 ? (
                        <p className="panel__muted">No timeline events yet.</p>
                      ) : (
                        <div className="agent-timeline__list">
                          {timelineEvents.map((event) => (
                            <div key={event.id} className="agent-timeline__item">
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
                                    onClick={() => {
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
                                    onClick={() =>
                                      router.push(
                                        `/experiments?experiment_id=${
                                          event.anchors?.experiment_id ||
                                          selectedRun?.experiment_id
                                        }`,
                                      )
                                    }
                                  >
                                    Open experiment
                                  </button>
                                ) : null}
                                {event.anchors?.validation_job_id ? (
                                  <button
                                    type="button"
                                    className="button button--ghost button--sm"
                                    onClick={() => router.push("/validation")}
                                  >
                                    Open validation
                                  </button>
                                ) : null}
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
        </section>
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
