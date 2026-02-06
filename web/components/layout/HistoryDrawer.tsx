"use client";

import type { Experiment, SessionSummary, SimulationRunSummary } from "../../lib/types";

type Props = {
  isOpen: boolean;
  isClosing: boolean;
  sessions: SessionSummary[];
  simulations?: SimulationRunSummary[];
  experiments?: Experiment[];
  activeSessionId?: string | null;
  onClose: () => void;
  onSelect: (session: SessionSummary) => void;
  onSelectSimulation?: (run: SimulationRunSummary) => void;
  onSelectExperiment?: (experiment: Experiment) => void;
  onRequestDelete: (sessionId: string) => void;
  onRequestDeleteSimulation?: (runId: string) => void;
  onRequestDeleteExperiment?: (experimentId: string) => void;
};

export function HistoryDrawer({
  isOpen,
  isClosing,
  sessions,
  simulations = [],
  experiments = [],
  activeSessionId,
  onClose,
  onSelect,
  onSelectSimulation,
  onSelectExperiment,
  onRequestDelete,
  onRequestDeleteSimulation,
  onRequestDeleteExperiment,
}: Props) {
  if (!isOpen) return null;

  const showSimulations = simulations.length > 0;
  const showExperiments = experiments.length > 0;
  const showSessions = sessions.length > 0;

  return (
    <div
      className={`history-overlay ${isClosing ? "is-closing" : ""}`}
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className={`history-panel ${isClosing ? "is-closing" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="history-panel__header">
          <h4>History</h4>
          <button
            type="button"
            className="history-panel__close"
            onClick={onClose}
            aria-label="Close history"
          >
            ×
          </button>
        </div>
        <div className="history-panel__list">
          {!showSessions && !showSimulations && !showExperiments ? (
            <p className="panel__empty">No history yet.</p>
          ) : null}

          <div className="history-panel__section">
            <h5 className="history-panel__section-title">Chat sessions</h5>
            {!showSessions ? (
              <p className="history-panel__empty">No conversations yet.</p>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  role="button"
                  tabIndex={0}
                  className={`history-panel__item ${
                    session.id === activeSessionId ? "is-active" : ""
                  }`}
                  onClick={() => onSelect(session)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(session);
                    }
                  }}
                >
                  <div className="history-panel__row">
                    <span
                      className="history-panel__title"
                      title={session.preview || "Conversation"}
                    >
                      {session.preview || "Conversation"}
                    </span>
                    <button
                      type="button"
                      className="history-panel__delete"
                      onClick={(event) => {
                        event.stopPropagation();
                        onRequestDelete(session.id);
                      }}
                      aria-label="Delete conversation"
                      title="Delete conversation"
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true" className="icon">
                        <path
                          d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z"
                          fill="currentColor"
                        />
                      </svg>
                    </button>
                  </div>
                  {session.last_turn_at && (
                    <span className="history-panel__meta">
                      {new Date(session.last_turn_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>

          <div className="history-panel__section">
            <h5 className="history-panel__section-title">Simulations</h5>
            {!showSimulations ? (
              <p className="history-panel__empty">No simulations yet.</p>
            ) : (
              simulations.map((run) => (
                <div
                  key={run.id}
                  role="button"
                  tabIndex={0}
                  className="history-panel__item"
                  onClick={() => onSelectSimulation?.(run)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectSimulation?.(run);
                    }
                  }}
                >
                  <div className="history-panel__row">
                    <span className="history-panel__title" title={run.query}>
                      {run.query || "Simulation run"}
                    </span>
                    {onRequestDeleteSimulation ? (
                      <button
                        type="button"
                        className="history-panel__delete"
                        onClick={(event) => {
                          event.stopPropagation();
                          onRequestDeleteSimulation(run.id);
                        }}
                        aria-label="Delete simulation"
                        title="Delete simulation"
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true" className="icon">
                          <path
                            d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z"
                            fill="currentColor"
                          />
                        </svg>
                      </button>
                    ) : null}
                  </div>
                  {run.created_at && (
                    <span className="history-panel__meta">
                      {new Date(run.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>

          <div className="history-panel__section">
            <h5 className="history-panel__section-title">Experiments</h5>
            {!showExperiments ? (
              <p className="history-panel__empty">No experiments yet.</p>
            ) : (
              experiments.map((experiment) => (
                <div
                  key={experiment.id}
                  role="button"
                  tabIndex={0}
                  className="history-panel__item"
                  onClick={() => onSelectExperiment?.(experiment)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectExperiment?.(experiment);
                    }
                  }}
                >
                  <div className="history-panel__row">
                    <span
                      className="history-panel__title"
                      title={experiment.name}
                    >
                      {experiment.name || "Experiment"}
                    </span>
                    {onRequestDeleteExperiment ? (
                      <button
                        type="button"
                        className="history-panel__delete"
                        onClick={(event) => {
                          event.stopPropagation();
                          onRequestDeleteExperiment(experiment.id);
                        }}
                        aria-label="Delete experiment"
                        title="Delete experiment"
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true" className="icon">
                          <path
                            d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z"
                            fill="currentColor"
                          />
                        </svg>
                      </button>
                    ) : null}
                  </div>
                  {experiment.created_at && (
                    <span className="history-panel__meta">
                      {new Date(experiment.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
