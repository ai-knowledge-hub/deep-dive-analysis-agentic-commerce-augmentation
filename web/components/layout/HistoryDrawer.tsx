"use client";

import { useEffect, useMemo, useState } from "react";
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
  onRequestDeleteSessionsBulk?: (sessionIds: string[]) => void;
  onRequestDeleteSimulationsBulk?: (runIds: string[]) => void;
  onRequestDeleteExperimentsBulk?: (experimentIds: string[]) => void;
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
  onRequestDeleteSessionsBulk,
  onRequestDeleteSimulationsBulk,
  onRequestDeleteExperimentsBulk,
}: Props) {
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);
  const [selectedSimulations, setSelectedSimulations] = useState<string[]>([]);
  const [selectedExperiments, setSelectedExperiments] = useState<string[]>([]);

  useEffect(() => {
    if (!isOpen) {
      setIsSelecting(false);
      setSelectedSessions([]);
      setSelectedSimulations([]);
      setSelectedExperiments([]);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const showSimulations = simulations.length > 0;
  const showExperiments = experiments.length > 0;
  const showSessions = sessions.length > 0;
  const totalSelected = selectedSessions.length + selectedSimulations.length + selectedExperiments.length;
  const canBulkDelete = totalSelected > 0;
  const supportsBulk = Boolean(
    onRequestDeleteSessionsBulk ||
      onRequestDeleteSimulationsBulk ||
      onRequestDeleteExperimentsBulk,
  );

  const toggleSession = (id: string) => {
    setSelectedSessions((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };
  const toggleSimulation = (id: string) => {
    setSelectedSimulations((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };
  const toggleExperiment = (id: string) => {
    setSelectedExperiments((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const handleBulkDelete = () => {
    if (!canBulkDelete) return;
    if (selectedSessions.length > 0) {
      if (onRequestDeleteSessionsBulk) {
        onRequestDeleteSessionsBulk(selectedSessions);
      } else {
        selectedSessions.forEach((id) => onRequestDelete(id));
      }
    }
    if (selectedSimulations.length > 0) {
      if (onRequestDeleteSimulationsBulk) {
        onRequestDeleteSimulationsBulk(selectedSimulations);
      } else if (onRequestDeleteSimulation) {
        selectedSimulations.forEach((id) => onRequestDeleteSimulation(id));
      }
    }
    if (selectedExperiments.length > 0) {
      if (onRequestDeleteExperimentsBulk) {
        onRequestDeleteExperimentsBulk(selectedExperiments);
      } else if (onRequestDeleteExperiment) {
        selectedExperiments.forEach((id) => onRequestDeleteExperiment(id));
      }
    }
    setSelectedSessions([]);
    setSelectedSimulations([]);
    setSelectedExperiments([]);
    setIsSelecting(false);
  };

  const sectionCounts = useMemo(
    () => ({
      sessions: selectedSessions.length,
      simulations: selectedSimulations.length,
      experiments: selectedExperiments.length,
    }),
    [selectedExperiments.length, selectedSessions.length, selectedSimulations.length],
  );

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
          <div className="history-panel__header-actions">
            {supportsBulk ? (
              isSelecting ? (
                <>
                  <button
                    type="button"
                    className="history-panel__action"
                    onClick={() => {
                      setIsSelecting(false);
                      setSelectedSessions([]);
                      setSelectedSimulations([]);
                      setSelectedExperiments([]);
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="history-panel__action history-panel__action--danger"
                    disabled={!canBulkDelete}
                    onClick={handleBulkDelete}
                  >
                    Delete selected ({totalSelected})
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="history-panel__action"
                  onClick={() => setIsSelecting(true)}
                >
                  Select
                </button>
              )
            ) : null}
            <button
              type="button"
              className="history-panel__close"
              onClick={onClose}
              aria-label="Close history"
            >
              ×
            </button>
          </div>
        </div>
        <div className="history-panel__list">
          {!showSessions && !showSimulations && !showExperiments ? (
            <p className="panel__empty">No history yet.</p>
          ) : null}

          <div className="history-panel__section">
            <h5 className="history-panel__section-title">Chat sessions</h5>
            {isSelecting && sectionCounts.sessions > 0 ? (
              <p className="history-panel__empty">Selected: {sectionCounts.sessions}</p>
            ) : null}
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
                  onClick={() => {
                    if (isSelecting) {
                      toggleSession(session.id);
                      return;
                    }
                    onSelect(session);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      if (isSelecting) {
                        toggleSession(session.id);
                      } else {
                        onSelect(session);
                      }
                    }
                  }}
                >
                  <div className="history-panel__row">
                    {isSelecting ? (
                      <input
                        type="checkbox"
                        className="history-panel__check"
                        checked={selectedSessions.includes(session.id)}
                        onChange={() => toggleSession(session.id)}
                        onClick={(event) => event.stopPropagation()}
                        aria-label="Select chat session"
                      />
                    ) : null}
                    <span
                      className="history-panel__title"
                      title={session.preview || "Conversation"}
                    >
                      {session.preview || "Conversation"}
                    </span>
                    {!isSelecting ? (
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
                    ) : null}
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
            {isSelecting && sectionCounts.simulations > 0 ? (
              <p className="history-panel__empty">Selected: {sectionCounts.simulations}</p>
            ) : null}
            {!showSimulations ? (
              <p className="history-panel__empty">No simulations yet.</p>
            ) : (
              simulations.map((run) => (
                <div
                  key={run.id}
                  role="button"
                  tabIndex={0}
                  className="history-panel__item"
                  onClick={() => {
                    if (isSelecting) {
                      toggleSimulation(run.id);
                      return;
                    }
                    onSelectSimulation?.(run);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      if (isSelecting) {
                        toggleSimulation(run.id);
                      } else {
                        onSelectSimulation?.(run);
                      }
                    }
                  }}
                >
                  <div className="history-panel__row">
                    {isSelecting ? (
                      <input
                        type="checkbox"
                        className="history-panel__check"
                        checked={selectedSimulations.includes(run.id)}
                        onChange={() => toggleSimulation(run.id)}
                        onClick={(event) => event.stopPropagation()}
                        aria-label="Select simulation"
                      />
                    ) : null}
                    <span className="history-panel__title" title={run.query}>
                      {run.query || "Simulation run"}
                    </span>
                    {onRequestDeleteSimulation && !isSelecting ? (
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
            {isSelecting && sectionCounts.experiments > 0 ? (
              <p className="history-panel__empty">Selected: {sectionCounts.experiments}</p>
            ) : null}
            {!showExperiments ? (
              <p className="history-panel__empty">No experiments yet.</p>
            ) : (
              experiments.map((experiment) => (
                <div
                  key={experiment.id}
                  role="button"
                  tabIndex={0}
                  className="history-panel__item"
                  onClick={() => {
                    if (isSelecting) {
                      toggleExperiment(experiment.id);
                      return;
                    }
                    onSelectExperiment?.(experiment);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      if (isSelecting) {
                        toggleExperiment(experiment.id);
                      } else {
                        onSelectExperiment?.(experiment);
                      }
                    }
                  }}
                >
                  <div className="history-panel__row">
                    {isSelecting ? (
                      <input
                        type="checkbox"
                        className="history-panel__check"
                        checked={selectedExperiments.includes(experiment.id)}
                        onChange={() => toggleExperiment(experiment.id)}
                        onClick={(event) => event.stopPropagation()}
                        aria-label="Select experiment"
                      />
                    ) : null}
                    <span
                      className="history-panel__title"
                      title={experiment.name}
                    >
                      {experiment.name || "Experiment"}
                    </span>
                    {onRequestDeleteExperiment && !isSelecting ? (
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
