"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type { AgentAction, AgentRun } from "../../lib/types";
import {
  controlAgentRun,
  createAgentRun,
  decideAgentAction,
  getAgentRun,
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
  "update_posterior_and_decisions",
];

function formatJsonPreview(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

export default function AgentRunsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
  const userId = user?.id ?? null;

  const experimentIdParam = searchParams.get("experiment_id")?.trim() || "";
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

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

  const loadSelected = useCallback(async () => {
    if (!userId || !selectedRunId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await getAgentRun(selectedRunId, { limit: 200 }, userId);
      setSelectedRun(response.run ?? null);
      setActions(response.actions ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent run.");
    } finally {
      setLoading(false);
    }
  }, [selectedRunId, userId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    loadSelected();
  }, [loadSelected]);

  const selectedSummary = useMemo(() => {
    if (!selectedRun) return null;
    return `${selectedRun.status ?? "unknown"} · ${selectedRun.state ?? "unknown"}`;
  }, [selectedRun]);

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
    <div className="layout">
      <Sidebar
        mobileOpen={false}
        onMobileClose={() => {}}
        onNewConversation={() => router.push("/")}
        sessions={[]}
        activeSessionId={null}
        onSelectSession={() => {}}
        onDeleteSession={() => {}}
        onOpenHistory={() => {}}
        showHistoryButton={false}
      />

      <main className="main">
        <DetailHeader title="Agent runs" subtitle={selectedSummary || "Governed lab automation (planned)"} />

        <section className="panel__card panel__card--secondary panel__card--full-row">
          <div className="panel__header">
            <div className="panel__meta panel__meta--stack">
              <h3>Runs</h3>
              <div className="panel__subtitle">
                Agents propose actions. Guardrails and approvals are enforced by the platform.
              </div>
            </div>
            <button
              type="button"
              className="button button--primary"
              onClick={() => setDrawerOpen(true)}
              disabled={!userId || loading}
            >
              New agent run
            </button>
          </div>

          {error && <div className="panel__error">{error}</div>}

          <div className="panel__grid" style={{ gridTemplateColumns: "340px 1fr" }}>
            <div className="panel__column">
              <div className="panel__card">
                <div className="panel__header">
                  <h3>Recent</h3>
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
            </div>

            <div className="panel__column">
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
                    </div>

                    <div className="table">
                      <div className="table__header">
                        <div>#</div>
                        <div>Capability</div>
                        <div>Status</div>
                        <div>Rationale</div>
                        <div>Actions</div>
                      </div>
                      {(actions ?? []).map((a) => (
                        <div key={a.id} className="table__row">
                          <div>{a.sequence}</div>
                          <div>
                            <div className="table__strong">{a.capability_name}</div>
                            {a.capability_version && (
                              <div className="table__muted">{a.capability_version}</div>
                            )}
                          </div>
                          <div>{a.status}</div>
                          <div className="table__muted">
                            {a.rationale || (a.error ? `Error: ${a.error}` : "—")}
                          </div>
                          <div className="table__actions">
                            {a.status === "proposed" ? (
                              <>
                                <button
                                  type="button"
                                  className="button button--primary button--sm"
                                  onClick={() => handleDecision(a.id, "approve")}
                                  disabled={loading}
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
                          </div>
                        </div>
                      ))}
                      {actions.length === 0 && (
                        <div className="panel__muted">
                          No actions recorded yet. Next: we’ll add plan generation and execution ticks.
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

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
                  <span className="field__label">Experiment id (optional)</span>
                  <input
                    className="field__input"
                    value={createForm.experiment_id}
                    onChange={(e) =>
                      setCreateForm((p) => ({ ...p, experiment_id: e.target.value }))
                    }
                    placeholder="experiment uuid"
                  />
                </label>

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
                  className="button button--primary"
                  onClick={() => handleCreate()}
                  disabled={!userId || loading}
                >
                  Create run
                </button>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
