"use client";

import React from "react";
import type { LoopGeneratedVariantCandidate } from "../../lib/types";

type Props = {
  hasBatteryId: boolean;
  hasQueries: boolean;
  hasValidationSignals: boolean;
  isGenerating: boolean;
  isSubmitting: boolean;
  isCreatingAndRunning: boolean;
  generatedVariants: LoopGeneratedVariantCandidate[];
  selectedCandidateIndex: number;
  generationStatus: string | null;
  onGenerateFromLoopEvidence: () => void;
  onGenerateColdStart: () => void;
  onCreateAndRunSelected: () => void;
  onShowManualControls: () => void;
  onSelectedCandidateIndexChange: (index: number) => void;
};

export function LabVariantAutomationPanel({
  hasBatteryId,
  hasQueries,
  hasValidationSignals,
  isGenerating,
  isSubmitting,
  isCreatingAndRunning,
  generatedVariants,
  selectedCandidateIndex,
  generationStatus,
  onGenerateFromLoopEvidence,
  onGenerateColdStart,
  onCreateAndRunSelected,
  onShowManualControls,
  onSelectedCandidateIndexChange,
}: Props) {
  const selectedCandidate = generatedVariants[selectedCandidateIndex];

  return (
    <section className="panel__notice panel__notice--info">
      <strong>Lab iteration path:</strong> generate candidates, create the selected one, then run it.
      <div className="panel__actions panel__actions--priority">
        <button
          type="button"
          className="panel__action panel__action--prominent"
          onClick={() =>
            hasValidationSignals ? onGenerateFromLoopEvidence() : onGenerateColdStart()
          }
          disabled={!hasBatteryId || !hasQueries || isGenerating}
        >
          {isGenerating
            ? "Generating candidates…"
            : hasValidationSignals
              ? "Generate candidate from loop evidence"
              : "Generate cold-start candidate"}
        </button>
        <button
          type="button"
          className="panel__action panel__action--ghost"
          onClick={onCreateAndRunSelected}
          disabled={generatedVariants.length === 0 || isSubmitting}
        >
          {isCreatingAndRunning ? "Creating + running candidate…" : "Create + run selected candidate"}
        </button>
        <button
          type="button"
          className="panel__action panel__action--ghost"
          onClick={onShowManualControls}
        >
          Show manual variant controls
        </button>
      </div>
      {generatedVariants.length > 0 ? (
        <label className="panel__label">
          Selected candidate
          <select
            className="panel__input"
            value={String(selectedCandidateIndex)}
            onChange={(event) => onSelectedCandidateIndexChange(Number(event.target.value))}
          >
            {generatedVariants.map((candidate, index) => (
              <option key={`${candidate.label}-${index}`} value={String(index)}>
                {index + 1}. {candidate.label} · conf {candidate.confidence.toFixed(2)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {selectedCandidate?.rationale ? (
        <p className="panel__muted">{selectedCandidate.rationale}</p>
      ) : null}
      {generationStatus ? <p className="panel__success">{generationStatus}</p> : null}
    </section>
  );
}
