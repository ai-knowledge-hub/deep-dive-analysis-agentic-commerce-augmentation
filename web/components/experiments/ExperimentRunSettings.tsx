import React from "react";

type ExperimentRunSettingsProps = {
  runMode: "simulation" | "retrieval_backed";
  retrievalMaxResults: string;
  currentProtocolSnapshotVersion: number | null;
  runVariantDisabledReason: string | null;
  onRunModeChange: (mode: "simulation" | "retrieval_backed") => void;
  onRetrievalMaxResultsChange: (value: string) => void;
};

export function ExperimentRunSettings({
  runMode,
  retrievalMaxResults,
  currentProtocolSnapshotVersion,
  runVariantDisabledReason,
  onRunModeChange,
  onRetrievalMaxResultsChange,
}: ExperimentRunSettingsProps) {
  return (
    <>
      <div className="panel__grid panel__grid--two">
        <label className="panel__label">
          Execution mode
          <select
            className="panel__input"
            value={runMode}
            onChange={(event) =>
              onRunModeChange(
                event.target.value === "retrieval_backed"
                  ? "retrieval_backed"
                  : "simulation",
              )
            }
          >
            <option value="simulation">Simulation (catalog competitors)</option>
            <option value="retrieval_backed">Retrieval-backed (web candidates)</option>
          </select>
        </label>
        {runMode === "retrieval_backed" ? (
          <label className="panel__label">
            Retrieval candidates per query
            <input
              className="panel__input"
              type="number"
              min={1}
              max={10}
              value={retrievalMaxResults}
              onChange={(event) => onRetrievalMaxResultsChange(event.target.value || "5")}
            />
          </label>
        ) : (
          <div className="panel__label">
            <span className="panel__muted">
              Uses local catalog + configured competitor policy.
            </span>
          </div>
        )}
      </div>
      <p className="panel__muted">
        Retrieval-backed mode pulls external web candidates per query, then scores variants against
        that set.
      </p>
      {currentProtocolSnapshotVersion && currentProtocolSnapshotVersion > 0 ? (
        <p className="panel__muted">
          Active evidence set: v{currentProtocolSnapshotVersion}
        </p>
      ) : null}
      {runVariantDisabledReason ? <p className="panel__muted">{runVariantDisabledReason}</p> : null}
    </>
  );
}
