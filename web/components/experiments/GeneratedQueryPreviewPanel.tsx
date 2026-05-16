"use client";

import React from "react";
import type { QueryBatteryCandidate } from "../../lib/types";

export type GeneratedQueryCandidate = QueryBatteryCandidate & { selected: boolean };

type Props = {
  candidates: GeneratedQueryCandidate[];
  isSubmitting: boolean;
  selectedBatteryId: string;
  onCandidateChange: (index: number, patch: Partial<GeneratedQueryCandidate>) => void;
  onClear: () => void;
  onSaveSelected: (batteryId: string) => void;
};

export function GeneratedQueryPreviewPanel({
  candidates,
  isSubmitting,
  selectedBatteryId,
  onCandidateChange,
  onClear,
  onSaveSelected,
}: Props) {
  if (candidates.length === 0) return null;

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h4>Preview & approve queries</h4>
        <button type="button" className="button button--ghost" onClick={onClear}>
          Clear preview
        </button>
      </div>
      <div className="panel__form">
        {candidates.map((candidate, index) => (
          <div className="panel__row panel__row--dense" key={`${candidate.query_text}-${index}`}>
            <label className="panel__toggle">
              <input
                type="checkbox"
                checked={candidate.selected}
                onChange={(event) => onCandidateChange(index, { selected: event.target.checked })}
              />
              <span>{candidate.query_text}</span>
            </label>
            <input
              className="panel__input panel__input--tiny"
              type="number"
              min={0}
              step={0.1}
              value={candidate.weight ?? 1}
              onChange={(event) => onCandidateChange(index, { weight: Number(event.target.value) })}
            />
          </div>
        ))}
        <button
          type="button"
          className="panel__action panel__action--prominent"
          onClick={() => onSaveSelected(selectedBatteryId)}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              Saving queries<span className="button__dots" />
            </>
          ) : (
            "Save selected queries"
          )}
        </button>
      </div>
    </div>
  );
}
