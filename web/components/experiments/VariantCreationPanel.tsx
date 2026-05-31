import React, { type Dispatch, type SetStateAction } from "react";
import type { LoopGeneratedVariantCandidate } from "../../lib/types";
import { GeneratedCopyPreview } from "./GeneratedCopyPreview";

type VariantSourceMode = "manual" | "simulation" | "loop_evidence" | "cold_start";
type ColdStartStrategy = "bottom_up" | "top_down" | "both";

type VariantFormState = {
  label: string;
  role: string;
  description: string;
  type: string;
  payload: string;
};

type CopyRevisionOption = {
  id: string;
  created_at?: string | null;
  updated_at?: string | null;
  status?: string | null;
};

function formatDisplayToken(value: string | null | undefined, fallback: string): string {
  const text = String(value || fallback)
    .replace(/[._-]+/g, " ")
    .trim();
  if (!text) return fallback;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatVariantSourceMode(value: VariantSourceMode): string {
  if (value === "loop_evidence") return "Loop evidence";
  if (value === "cold_start") return "Cold start";
  return formatDisplayToken(value, "Manual");
}

function formatSimulationRevisionOption(revision: CopyRevisionOption): string {
  const timestamp = revision.updated_at ?? revision.created_at;
  const updatedLabel = timestamp ? new Date(timestamp).toLocaleString() : "No date";
  return `${updatedLabel} · ${formatDisplayToken(revision.status, "Draft")}`;
}

type Props = {
  variantSourceMode: VariantSourceMode;
  setVariantSourceMode: Dispatch<SetStateAction<VariantSourceMode>>;
  setVariantSourceManualOverride: Dispatch<SetStateAction<boolean>>;
  recommendedVariantSource: VariantSourceMode;
  recommendedVariantSourceReason: string;
  variantSourceManualOverride: boolean;
  variantForm: VariantFormState;
  setVariantForm: Dispatch<SetStateAction<VariantFormState>>;
  selectedSimulationRevisionId: string;
  setSelectedSimulationRevisionId: Dispatch<SetStateAction<string>>;
  simulationRevisions: CopyRevisionOption[];
  handleUseSimulationRevision: () => void;
  simulationRevisionStatus: string | null;
  loopGeneratedVariants: LoopGeneratedVariantCandidate[];
  selectedLoopCandidateIndex: number;
  setSelectedLoopCandidateIndex: Dispatch<SetStateAction<number>>;
  handleGenerateLoopVariants: () => void;
  handleUseGeneratedLoopVariant: () => void;
  handleCreateVariantFromLoopCandidate: () => void;
  loopGenerationStatus: string | null;
  loopEvidenceAdvisory: string | null;
  coldStartGenerationStrategy: ColdStartStrategy;
  setColdStartGenerationStrategy: Dispatch<SetStateAction<ColdStartStrategy>>;
  handleGenerateColdStartVariants: () => void;
  variantSecondaryActionsOpen: boolean;
  setVariantSecondaryActionsOpen: Dispatch<SetStateAction<boolean>>;
  variantAdvancedOpen: boolean;
  setVariantAdvancedOpen: Dispatch<SetStateAction<boolean>>;
  jsonErrorVariantPayload: string | null;
  addVariantDisabledReason: string | null;
  handleCreateVariant: () => void;
  labMode: "lab" | "manual";
  setLabShowManualControls: Dispatch<SetStateAction<boolean>>;
  isSubmitting: boolean;
  isGeneratingLoopVariant: boolean;
  variantGenerationRequestType: "loop" | "cold_start" | null;
  isCreatingVariant: boolean;
  isCreatingLoopCandidateVariant: boolean;
  canGenerateCandidates: boolean;
};

export function VariantCreationPanel({
  variantSourceMode,
  setVariantSourceMode,
  setVariantSourceManualOverride,
  recommendedVariantSource,
  recommendedVariantSourceReason,
  variantSourceManualOverride,
  variantForm,
  setVariantForm,
  selectedSimulationRevisionId,
  setSelectedSimulationRevisionId,
  simulationRevisions,
  handleUseSimulationRevision,
  simulationRevisionStatus,
  loopGeneratedVariants,
  selectedLoopCandidateIndex,
  setSelectedLoopCandidateIndex,
  handleGenerateLoopVariants,
  handleUseGeneratedLoopVariant,
  handleCreateVariantFromLoopCandidate,
  loopGenerationStatus,
  loopEvidenceAdvisory,
  coldStartGenerationStrategy,
  setColdStartGenerationStrategy,
  handleGenerateColdStartVariants,
  variantSecondaryActionsOpen,
  setVariantSecondaryActionsOpen,
  variantAdvancedOpen,
  setVariantAdvancedOpen,
  jsonErrorVariantPayload,
  addVariantDisabledReason,
  handleCreateVariant,
  labMode,
  setLabShowManualControls,
  isSubmitting,
  isGeneratingLoopVariant,
  variantGenerationRequestType,
  isCreatingVariant,
  isCreatingLoopCandidateVariant,
  canGenerateCandidates,
}: Props) {
  return (
    <>
      <div className="variant-source">
        <div className="variant-source__header">
          <h4>Choose variant source</h4>
          <span className="panel__muted">
            Recommended now: <strong>{formatVariantSourceMode(recommendedVariantSource)}</strong>
          </span>
        </div>
        <div className="variant-source__tabs">
          <button
            type="button"
            className={`variant-source__tab ${
              variantSourceMode === "manual" ? "is-active" : ""
            }`}
            onClick={() => {
              setVariantSourceMode("manual");
              setVariantSourceManualOverride(true);
            }}
          >
            Manual
          </button>
          <button
            type="button"
            className={`variant-source__tab ${
              variantSourceMode === "simulation" ? "is-active" : ""
            }`}
            onClick={() => {
              setVariantSourceMode("simulation");
              setVariantSourceManualOverride(true);
            }}
          >
            Simulation prefill
          </button>
          <button
            type="button"
            className={`variant-source__tab ${
              variantSourceMode === "loop_evidence" ? "is-active" : ""
            }`}
            onClick={() => {
              setVariantSourceMode("loop_evidence");
              setVariantSourceManualOverride(true);
            }}
          >
            Loop evidence
          </button>
          <button
            type="button"
            className={`variant-source__tab ${
              variantSourceMode === "cold_start" ? "is-active" : ""
            }`}
            onClick={() => {
              setVariantSourceMode("cold_start");
              setVariantSourceManualOverride(true);
            }}
          >
            Cold-start
          </button>
        </div>
        <p className="panel__step-helper">{recommendedVariantSourceReason}</p>
        <p className="variant-source__hint">
          {variantSourceMode === "manual"
            ? "Use when you already have candidate copy and want full control."
            : variantSourceMode === "simulation"
              ? "Use when simulation already produced a useful revision for this product."
              : variantSourceMode === "loop_evidence"
                ? "Use when runs/metrics/validation history exists and you want evidence-weighted candidates."
                : "Use when history is sparse and you need a first set of aligned variants."}
        </p>
        {variantSourceManualOverride && variantSourceMode !== recommendedVariantSource ? (
          <div className="panel__actions">
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={() => {
                setVariantSourceMode(recommendedVariantSource);
                setVariantSourceManualOverride(false);
              }}
            >
              Use recommended source
            </button>
          </div>
        ) : null}
      </div>
      <p className="panel__subheading">Step 8 · Generate next variants from updated evidence</p>
      <p className="panel__step-helper">
        Prefer loop evidence once runs and validation signals are available.
      </p>
      <div className="panel__form">
        <label className="panel__label">
          Role
          <select
            className="panel__input"
            value={variantForm.role}
            onChange={(event) => {
              const role = event.target.value as "candidate" | "control";
              setVariantForm((prev) => ({
                ...prev,
                role,
                label:
                  role === "control"
                    ? "Control (current copy)"
                    : prev.label === "Control (current copy)"
                      ? "Hypothesis (variant)"
                      : prev.label,
              }));
            }}
          >
            <option value="candidate">Candidate</option>
            <option value="control">Control</option>
          </select>
        </label>
        <label className="panel__label">
          Label
          <input
            className="panel__input"
            value={variantForm.label}
            onChange={(event) =>
              setVariantForm((prev) => ({
                ...prev,
                label: event.target.value,
              }))
            }
            placeholder="Variant A"
          />
        </label>
        <label className="panel__label">
          Candidate description
          <textarea
            className="panel__textarea"
            value={variantForm.description}
            onChange={(event) =>
              setVariantForm((prev) => ({
                ...prev,
                description: event.target.value,
              }))
            }
            rows={5}
            placeholder="Write the copy variation to test..."
          />
        </label>
        {variantSourceMode === "simulation" ? (
          <>
            <label className="panel__label">
              Prefill from simulation revision (same product)
              <select
                className="panel__input"
                value={selectedSimulationRevisionId}
                onChange={(event) => setSelectedSimulationRevisionId(event.target.value)}
                disabled={simulationRevisions.length === 0}
              >
                {simulationRevisions.length === 0 ? (
                  <option value="">No simulation revisions found</option>
                ) : null}
                {simulationRevisions.map((revision) => (
                  <option key={revision.id} value={revision.id}>
                    {formatSimulationRevisionOption(revision)}
                  </option>
                ))}
              </select>
            </label>
            <div className="panel__actions">
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={handleUseSimulationRevision}
                disabled={simulationRevisions.length === 0}
              >
                Use selected simulation revision
              </button>
            </div>
            {simulationRevisionStatus ? (
              <p className="panel__success">{simulationRevisionStatus}</p>
            ) : null}
            <div className="panel__separator" />
          </>
        ) : null}
        {variantSourceMode === "loop_evidence" ? (
          <>
            <label className="panel__label">
              Prefill from loop evidence (experiment + simulation + validation)
              <select
                className="panel__input"
                value={String(selectedLoopCandidateIndex)}
                onChange={(event) => setSelectedLoopCandidateIndex(Number(event.target.value))}
                disabled={loopGeneratedVariants.length === 0}
              >
                {loopGeneratedVariants.length === 0 ? (
                  <option value="0">No generated candidates yet</option>
                ) : null}
                {loopGeneratedVariants.map((candidate, index) => (
                  <option key={`${candidate.label}-${index}`} value={String(index)}>
                    {index + 1}. {candidate.label} · conf {candidate.confidence.toFixed(2)}
                  </option>
                ))}
              </select>
            </label>
            <div className="panel__actions">
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={handleGenerateLoopVariants}
                disabled={!canGenerateCandidates || isGeneratingLoopVariant}
              >
                {isGeneratingLoopVariant && variantGenerationRequestType === "loop" ? (
                  <>
                    Generating from loop<span className="button__dots" />
                  </>
                ) : (
                  "Generate from loop evidence"
                )}
              </button>
            </div>
            {loopGeneratedVariants[selectedLoopCandidateIndex]?.rationale ? (
              <p className="panel__muted">
                {loopGeneratedVariants[selectedLoopCandidateIndex]?.rationale}
              </p>
            ) : null}
            {loopGenerationStatus ? <p className="panel__success">{loopGenerationStatus}</p> : null}
            <GeneratedCopyPreview
              candidates={loopGeneratedVariants}
              selectedIndex={selectedLoopCandidateIndex}
              onSelect={setSelectedLoopCandidateIndex}
              radioName="generated-copy-preview-loop"
            />
            {loopEvidenceAdvisory ? <p className="panel__muted">{loopEvidenceAdvisory}</p> : null}
            <div className="panel__separator" />
          </>
        ) : null}
        {variantSourceMode === "cold_start" ? (
          <>
            <label className="panel__label">
              Generate cold-start copy (no prior loop evidence)
              <select
                className="panel__input"
                value={coldStartGenerationStrategy}
                onChange={(event) =>
                  setColdStartGenerationStrategy(
                    event.target.value as "bottom_up" | "top_down" | "both",
                  )
                }
              >
                <option value="both">Both (recommended)</option>
                <option value="bottom_up">Bottom-up (features/use-cases)</option>
                <option value="top_down">Top-down (goals/positioning)</option>
              </select>
            </label>
            <div className="panel__actions">
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={handleGenerateColdStartVariants}
                disabled={!canGenerateCandidates || isGeneratingLoopVariant}
              >
                {isGeneratingLoopVariant && variantGenerationRequestType === "cold_start" ? (
                  <>
                    Generating cold-start copy
                    <span className="button__dots" />
                  </>
                ) : (
                  "Generate cold-start copy"
                )}
              </button>
            </div>
            {loopGenerationStatus ? <p className="panel__success">{loopGenerationStatus}</p> : null}
            <GeneratedCopyPreview
              candidates={loopGeneratedVariants}
              selectedIndex={selectedLoopCandidateIndex}
              onSelect={setSelectedLoopCandidateIndex}
              radioName="generated-copy-preview"
            />
            <div className="panel__separator" />
          </>
        ) : null}
        <details
          className="panel__details"
          open={variantSecondaryActionsOpen}
          onToggle={(event) => setVariantSecondaryActionsOpen(event.currentTarget.open)}
        >
          <summary className="panel__details-summary">More variant actions</summary>
          <div className="panel__actions">
            {variantSourceMode === "loop_evidence" ? (
              <>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={handleUseGeneratedLoopVariant}
                  disabled={loopGeneratedVariants.length === 0}
                >
                  Use selected loop candidate
                </button>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={handleCreateVariantFromLoopCandidate}
                  disabled={loopGeneratedVariants.length === 0 || isSubmitting}
                >
                  {isCreatingLoopCandidateVariant
                    ? "Creating variant…"
                    : "Create variant from selected loop candidate"}
                </button>
              </>
            ) : null}
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={() =>
                setVariantForm((prev) => ({
                  ...prev,
                  description:
                    "Outcome-led copy that emphasizes user goals and capabilities.",
                }))
              }
            >
              Use description template
            </button>
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={() => setVariantAdvancedOpen((open) => !open)}
            >
              {variantAdvancedOpen ? "Hide advanced" : "Advanced JSON"}
            </button>
          </div>
        </details>
        {variantAdvancedOpen ? (
          <>
            <label className="panel__label">
              Type
              <input
                className="panel__input"
                value={variantForm.type}
                onChange={(event) =>
                  setVariantForm((prev) => ({
                    ...prev,
                    type: event.target.value,
                  }))
                }
                placeholder="copy"
              />
            </label>
            <label className="panel__label">
              Payload overrides (JSON)
              <textarea
                className="panel__textarea"
                value={variantForm.payload}
                onChange={(event) =>
                  setVariantForm((prev) => ({
                    ...prev,
                    payload: event.target.value,
                  }))
                }
                rows={3}
                placeholder='{"metadata":{"channel":"web"}}'
              />
            </label>
            {jsonErrorVariantPayload ? (
              <span className="panel__error">{jsonErrorVariantPayload}</span>
            ) : null}
          </>
        ) : null}
        <button
          type="button"
          className="panel__action panel__action--prominent"
          onClick={handleCreateVariant}
          disabled={Boolean(addVariantDisabledReason)}
        >
          {isCreatingVariant ? (
            <>
              Adding variant<span className="button__dots" />
            </>
          ) : (
            "Add variant"
          )}
        </button>
        {addVariantDisabledReason ? <p className="panel__muted">{addVariantDisabledReason}</p> : null}
      </div>
      {labMode === "lab" ? (
        <div className="panel__actions">
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={() => setLabShowManualControls(false)}
          >
            Hide manual variant controls
          </button>
        </div>
      ) : null}
    </>
  );
}
