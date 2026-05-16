"use client";

import React from "react";

export type BatteryCreationForm = {
  name: string;
  purpose: string;
  generationMode: string;
};

type Props = {
  status: string | null;
  form: BatteryCreationForm;
  useLlm: boolean;
  isSubmitting: boolean;
  hasBottomUpMetadata: boolean;
  advancedOverridesOpen: boolean;
  seedQueries: string;
  seedFeatures: string;
  seedUseCases: string;
  onFormChange: (form: BatteryCreationForm) => void;
  onUseLlmChange: (value: boolean) => void;
  onAdvancedOverridesOpenChange: (value: boolean) => void;
  onSeedQueriesChange: (value: string) => void;
  onSeedFeaturesChange: (value: string) => void;
  onSeedUseCasesChange: (value: string) => void;
  onCreateBattery: () => void;
};

export function BatteryCreationPanel({
  status,
  form,
  useLlm,
  isSubmitting,
  hasBottomUpMetadata,
  advancedOverridesOpen,
  seedQueries,
  seedFeatures,
  seedUseCases,
  onFormChange,
  onUseLlmChange,
  onAdvancedOverridesOpenChange,
  onSeedQueriesChange,
  onSeedFeaturesChange,
  onSeedUseCasesChange,
  onCreateBattery,
}: Props) {
  const updateForm = (patch: Partial<BatteryCreationForm>) => {
    onFormChange({ ...form, ...patch });
  };

  return (
    <>
      {status ? <p className="panel__success">{status}</p> : null}
      <p className="panel__subheading">Step 1 · Create query battery foundation</p>
      <label className="panel__label">
        Battery name
        <input
          className="panel__input"
          value={form.name}
          onChange={(event) => updateForm({ name: event.target.value })}
          placeholder="Baseline coverage"
        />
      </label>
      <label className="panel__label">
        Purpose
        <input
          className="panel__input"
          value={form.purpose}
          onChange={(event) => updateForm({ purpose: event.target.value })}
          placeholder="Why this battery exists"
        />
      </label>
      <label className="panel__label">
        Generation mode
        <select
          className="panel__input"
          value={form.generationMode}
          onChange={(event) => updateForm({ generationMode: event.target.value })}
        >
          <option value="bottom_up">Bottom-up</option>
          <option value="top_down">Top-down</option>
          <option value="hybrid">Hybrid</option>
        </select>
      </label>
      <label className="panel__toggle">
        <input
          type="checkbox"
          checked={useLlm}
          onChange={(event) => onUseLlmChange(event.target.checked)}
        />
        <span>Use LLM-assisted query generation</span>
      </label>
      <button
        type="button"
        className="panel__action panel__action--prominent"
        onClick={onCreateBattery}
        disabled={isSubmitting || form.name.trim() === ""}
      >
        {isSubmitting ? (
          <>
            Creating battery<span className="button__dots" />
          </>
        ) : (
          "Create battery"
        )}
      </button>
      {form.generationMode === "bottom_up" && !hasBottomUpMetadata ? (
        <div className="panel__notice panel__notice--info">
          Bottom-up has weak product metadata. Use Advanced overrides below or we will offer
          fallback to top-down at generation time.
        </div>
      ) : null}
      <details
        open={advancedOverridesOpen}
        onToggle={(event) => onAdvancedOverridesOpenChange(event.currentTarget.open)}
      >
        <summary className="panel__label">Advanced overrides (optional)</summary>
        <div className="panel__form">
          <label className="panel__label">
            Seed queries (optional, one per line)
            <textarea
              className="panel__textarea"
              value={seedQueries}
              onChange={(event) => onSeedQueriesChange(event.target.value)}
              rows={3}
            />
          </label>
          <label className="panel__label">
            Seed features (recommended for bottom-up)
            <textarea
              className="panel__textarea"
              value={seedFeatures}
              onChange={(event) => onSeedFeaturesChange(event.target.value)}
              rows={2}
              placeholder="lightweight cushioning, breathable upper, stable heel support"
            />
          </label>
          <label className="panel__label">
            Seed use-cases (recommended for bottom-up)
            <textarea
              className="panel__textarea"
              value={seedUseCases}
              onChange={(event) => onSeedUseCasesChange(event.target.value)}
              rows={2}
              placeholder="daily training, long-distance running, injury prevention"
            />
          </label>
        </div>
      </details>
    </>
  );
}
