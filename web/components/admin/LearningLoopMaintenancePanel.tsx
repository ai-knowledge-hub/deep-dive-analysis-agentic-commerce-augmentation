"use client";

import React from "react";
import type {
  LoopMaintenanceRunHistoryItem,
  LoopMaintenanceRunResponse,
} from "../../lib/types";

type Props = {
  userId?: string | null;
  activeClientId: string;
  isRunning: boolean;
  error: string | null;
  result: LoopMaintenanceRunResponse | null;
  history: LoopMaintenanceRunHistoryItem[];
  lookbackDays: string;
  minConfidence: string;
  onLookbackDaysChange: (value: string) => void;
  onMinConfidenceChange: (value: string) => void;
  onRunMaintenance: () => void | Promise<void>;
};

export function LearningLoopMaintenancePanel({
  userId,
  activeClientId,
  isRunning,
  error,
  result,
  history,
  lookbackDays,
  minConfidence,
  onLookbackDaysChange,
  onMinConfidenceChange,
  onRunMaintenance,
}: Props) {
  return (
    <details className="admin-ops__details">
      <summary>Learning loop maintenance</summary>
      {!userId ? (
        <p className="panel__empty">Sign in to run maintenance.</p>
      ) : (
        <div className="admin__form">
          <p className="panel__meta">
            Refresh calibration profiles and distill high-confidence belief memory.
          </p>
          <div className="panel__grid">
            <label className="panel__label">
              <span>Client scope</span>
              <input
                className="panel__input panel__input--neutral"
                type="text"
                readOnly
                value={activeClientId || "all clients"}
              />
            </label>
            <label className="panel__label">
              <span>Lookback days</span>
              <input
                className="panel__input panel__input--neutral"
                type="number"
                min={1}
                max={365}
                value={lookbackDays}
                onChange={(event) => onLookbackDaysChange(event.target.value)}
              />
            </label>
            <label className="panel__label">
              <span>Min confidence</span>
              <input
                className="panel__input panel__input--neutral"
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minConfidence}
                onChange={(event) => onMinConfidenceChange(event.target.value)}
              />
            </label>
          </div>
          <div className="panel__actions">
            <button
              type="button"
              className="button button--primary-subtle"
              onClick={() => void onRunMaintenance()}
              disabled={isRunning}
            >
              {isRunning ? "Running..." : "Run maintenance"}
            </button>
          </div>
          {error ? <p className="panel__error">{error}</p> : null}
          {result ? (
            <div className="admin__history">
              <span className="panel__label">Last run summary</span>
              <ul className="admin__list">
                {result.results.map((item) => (
                  <li key={item.client_id}>
                    <span>{item.client_id}</span>
                    <span className="admin__meta">
                      calibration {item.calibration_profiles_updated} · distilled{" "}
                      {item.memory_artifacts_distilled}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="admin__history">
            <span className="panel__label">Recent runs</span>
            {history.length === 0 ? (
              <p className="panel__meta">No maintenance runs logged yet.</p>
            ) : (
              <ul className="admin__list">
                {history.map((item) => (
                  <li key={item.id}>
                    <span>
                      {item.created_at ?? "n/a"} · lookback {item.lookback_days}d · min conf{" "}
                      {item.min_confidence}
                    </span>
                    <span className="admin__meta">
                      calibration {item.calibration_profiles_updated} · distilled{" "}
                      {item.memory_artifacts_distilled}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </details>
  );
}
