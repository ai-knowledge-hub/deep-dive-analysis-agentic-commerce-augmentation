import React, { type RefObject } from "react";
import { buildSimulationHref } from "../../lib/routes";
import type {
  Experiment,
  ExperimentRun,
  QueryBattery,
  SimulationGapReport,
} from "../../lib/types";

type ExperimentSnapshot = {
  winnerLabel?: string;
  winRate?: number | null;
  measuredAt?: string | null;
};

type ExperimentHistoryPanelProps = {
  experiments: Experiment[];
  runs: ExperimentRun[];
  metricsCount: number;
  variantCount: number;
  historyCollapsed: boolean;
  selectedExperimentId: string | null;
  experimentSnapshots: Record<string, ExperimentSnapshot>;
  batteries: QueryBattery[];
  savingExperimentId: string | null;
  queryMap: Map<string, string>;
  variantLabelById: Map<string, string>;
  runGapDetails: Map<string, SimulationGapReport>;
  hypothesisLabelById: Map<string, string>;
  hypothesisStatementById: Map<string, Record<string, unknown>>;
  expandedHypothesisId: string | null;
  runsSectionRef: RefObject<HTMLDivElement>;
  formatTimestamp: (value?: string | null) => string;
  onToggleHistory: () => void;
  onSelectExperiment: (id: string) => void;
  onSaveExperimentDraft: (id: string) => void;
  onScrollVariants: () => void;
  onScrollRuns: () => void;
  onScrollMetrics: () => void;
  onToggleHypothesis: (hypothesisId: string | null) => void;
  onDeleteRun: (runId: string) => void;
};

export function ExperimentHistoryPanel({
  experiments,
  runs,
  metricsCount,
  variantCount,
  historyCollapsed,
  selectedExperimentId,
  experimentSnapshots,
  batteries,
  savingExperimentId,
  queryMap,
  variantLabelById,
  runGapDetails,
  hypothesisLabelById,
  hypothesisStatementById,
  expandedHypothesisId,
  runsSectionRef,
  formatTimestamp,
  onToggleHistory,
  onSelectExperiment,
  onSaveExperimentDraft,
  onScrollVariants,
  onScrollRuns,
  onScrollMetrics,
  onToggleHypothesis,
  onDeleteRun,
}: ExperimentHistoryPanelProps) {
  const formatVariantLabel = (variantId: string) =>
    variantLabelById.get(variantId) ?? "Selected variant";

  return (
    <section className="panel__card panel__card--secondary panel__card--full-row">
      <div className="panel__header">
        <h3>History</h3>
        <div className="panel__meta">
          <span className="panel__badge panel__badge--secondary">
            Experiments: {experiments.length}
          </span>
          <span className="panel__badge panel__badge--secondary">Runs: {runs.length}</span>
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={onToggleHistory}
          >
            {historyCollapsed ? "Expand history" : "Collapse history"}
          </button>
        </div>
      </div>
      <p className="panel__subheading">Past experiments and runs</p>
      <p className="panel__step-helper">
        Review past experiments, runs, and metrics without interrupting the active flow.
      </p>
      {historyCollapsed ? (
        <p className="panel__muted">
          History is collapsed to keep focus on the active experiment flow.
        </p>
      ) : (
        <div className="panel__grid">
          <div className="panel__column">
            <div className="panel__meta">
              <h4 className="panel__subtitle">Experiments</h4>
              {experiments.length > 0 ? <span className="panel__badge">{experiments.length}</span> : null}
            </div>
            {experiments.length === 0 ? (
              <p className="panel__empty">No experiments yet.</p>
            ) : (
              <ul className="panel__list">
                {experiments.map((experiment) => (
                  <li key={experiment.id}>
                    <button
                      type="button"
                      className={`history-panel__item ${
                        experiment.id === selectedExperimentId ? "is-active" : ""
                      }`}
                      onClick={() => onSelectExperiment(experiment.id)}
                    >
                      <div className="history-panel__row">
                        <span className="history-panel__title">{experiment.name}</span>
                        {experiment.status ? (
                          <span className="panel__badge panel__badge--secondary">
                            {experiment.status}
                          </span>
                        ) : null}
                      </div>
                      {experiment.hypothesis ? (
                        <span className="history-panel__meta">Test idea configured</span>
                      ) : (
                        <span className="history-panel__meta">No test idea yet</span>
                      )}
                      <span className="history-panel__meta">
                        Created: {formatTimestamp(experiment.created_at)}
                      </span>
                      {typeof experimentSnapshots[experiment.id]?.winRate === "number" ? (
                        <span className="history-panel__meta">
                          Latest win rate:{" "}
                          {Math.round((experimentSnapshots[experiment.id]?.winRate ?? 0) * 100)}%
                          {" · "}Winner: {experimentSnapshots[experiment.id]?.winnerLabel ?? "—"}
                        </span>
                      ) : (
                        <span className="history-panel__meta">Latest win rate: — · Winner: —</span>
                      )}
                    </button>
                    {experiment.id === selectedExperimentId ? (
                      <div className="panel__meta panel__meta--stack">
                        <span className="panel__muted">
                          Battery:{" "}
                          {batteries.find((battery) => battery.id === experiment.battery_id)?.name ??
                            experiment.battery_id ??
                            "Not linked"}
                        </span>
                        <span className="panel__muted">
                          Updated: {formatTimestamp(experiment.updated_at)}
                        </span>
                        <span className="panel__muted">Variants: {variantCount}</span>
                        <span className="panel__muted">Runs: {runs.length}</span>
                        <span className="panel__muted">Metrics: {metricsCount}</span>
                        <div className="panel__actions">
                          {experiment.status === "draft" ? (
                            <button
                              type="button"
                              className="panel__action"
                              onClick={() => onSaveExperimentDraft(experiment.id)}
                              disabled={savingExperimentId === experiment.id}
                            >
                              {savingExperimentId === experiment.id ? "Saving…" : "Save draft"}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className="panel__action panel__action--ghost"
                            onClick={onScrollVariants}
                          >
                            View variants
                          </button>
                          <button
                            type="button"
                            className="panel__action panel__action--ghost"
                            onClick={onScrollRuns}
                          >
                            View runs
                          </button>
                          <button
                            type="button"
                            className="panel__action panel__action--ghost"
                            onClick={onScrollMetrics}
                          >
                            View metrics
                          </button>
                        </div>
                      </div>
                    ) : experiment.status === "draft" ? (
                      <div className="panel__actions">
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={() => onSaveExperimentDraft(experiment.id)}
                          disabled={savingExperimentId === experiment.id}
                        >
                          {savingExperimentId === experiment.id ? "Saving…" : "Save draft"}
                        </button>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div
            ref={runsSectionRef}
            className="panel__column"
            tabIndex={-1}
            aria-label="Experiment runs"
          >
            <div className="panel__meta">
              <h4 className="panel__subtitle">Runs</h4>
              {runs.length > 0 ? <span className="panel__badge">{runs.length}</span> : null}
            </div>
            {runs.length === 0 ? (
              <p className="panel__empty">No experiment runs yet.</p>
            ) : (
              <ul className="panel__list">
                {runs.map((run) => (
                  <li key={run.id}>
                    <div className="panel__meta">
                      <span>{queryMap.get(run.query_id) ?? run.query_id}</span>
                      <span className="panel__badge panel__badge--secondary">
                        {run.simulation_run_id ? "linked" : "pending"}
                      </span>
                    </div>
                    <div className="panel__meta panel__meta--stack">
                      <span className="history-panel__meta">
                        Variant: {formatVariantLabel(run.variant_id)}
                      </span>
                      {typeof run.snapshot_version === "number" ? (
                        <span className="history-panel__meta">Evidence version: v{run.snapshot_version}</span>
                      ) : null}
                      {run.hypothesis_id ? (
                        <span className="history-panel__meta">
                          Test idea: {hypothesisLabelById.get(run.hypothesis_id) ?? "Linked test idea"}
                        </span>
                      ) : null}
                      {run.hypothesis_id ? (
                        <button
                          type="button"
                          className="panel__action panel__action--ghost"
                          onClick={() =>
                            onToggleHypothesis(
                              expandedHypothesisId === run.hypothesis_id
                                ? null
                                : run.hypothesis_id ?? null,
                            )
                          }
                        >
                          {expandedHypothesisId === run.hypothesis_id
                            ? "Hide test idea details"
                            : "View test idea details"}
                        </button>
                      ) : null}
                      {run.hypothesis_id && expandedHypothesisId === run.hypothesis_id ? (
                        <div className="panel__meta panel__meta--stack">
                          <span className="panel__muted">
                            If: {String(hypothesisStatementById.get(run.hypothesis_id)?.if ?? "—")}
                          </span>
                          <span className="panel__muted">
                            Then: {String(hypothesisStatementById.get(run.hypothesis_id)?.then ?? "—")}
                          </span>
                          <span className="panel__muted">
                            For: {String(hypothesisStatementById.get(run.hypothesis_id)?.for ?? "—")}
                          </span>
                        </div>
                      ) : null}
                      {run.simulation_run_id ? (
                        <span className="history-panel__meta">
                          Simulation:{" "}
                          <a
                            className="panel__link"
                            href={buildSimulationHref(run.simulation_run_id)}
                          >
                            Open linked simulation
                          </a>
                        </span>
                      ) : null}
                      {runGapDetails.get(run.id) ? (
                        <span className="history-panel__meta">
                          Gap: {runGapDetails.get(run.id)?.missing_signals?.slice(0, 3).join(", ") || "—"}
                        </span>
                      ) : null}
                    </div>
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="panel__action panel__action--ghost"
                        onClick={() => onDeleteRun(run.id)}
                      >
                        Delete run
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
