"use client";

import React from "react";

type OntologyOption = {
  label: string;
  subCategories: string[];
  useCases: string[];
  archetypes: string[];
  featureConcepts: string[];
  constraints: string[];
  exclusions: string[];
};

export type CanonicalIntentSpecForm = {
  category: string;
  subCategory: string;
  useCases: string;
  archetypes: string;
  featureConcepts: string;
  constraints: string;
  exclusions: string;
  objectiveKeywords: string;
  bannedKeywords: string;
};

type Props = {
  isOpen: boolean;
  canAutofill: boolean;
  canSave: boolean;
  form: CanonicalIntentSpecForm;
  currentClientName?: string | null;
  currentBrandName?: string | null;
  currentProductName?: string | null;
  canonicalOntology: Record<string, OntologyOption>;
  selectedOntology: OntologyOption | null;
  useCases: string[];
  archetypes: string[];
  featureConcepts: string[];
  constraints: string[];
  exclusions: string[];
  onClose: () => void;
  onFormChange: (patch: Partial<CanonicalIntentSpecForm>) => void;
  onAutofill: (mode: "preview" | "apply") => void | Promise<void>;
  onSave: () => void | Promise<void>;
};

function parseCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function selectedValues(event: React.ChangeEvent<HTMLSelectElement>) {
  return Array.from(event.target.selectedOptions)
    .map((option) => option.value)
    .join(", ");
}

export function CanonicalIntentSpecDrawer({
  isOpen,
  canAutofill,
  canSave,
  form,
  currentClientName,
  currentBrandName,
  currentProductName,
  canonicalOntology,
  selectedOntology,
  useCases,
  archetypes,
  featureConcepts,
  constraints,
  exclusions,
  onClose,
  onFormChange,
  onAutofill,
  onSave,
}: Props) {
  if (!isOpen) return null;

  return (
    <div className="admin-onboarding__drawer-overlay" onClick={onClose}>
      <aside
        className="admin-onboarding__drawer"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel__header">
          <h3>Canonical intent spec</h3>
          <button type="button" className="button button--ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="panel__meta">
          Scope: {currentClientName ?? "No client"} / {currentBrandName ?? "No brand"} /{" "}
          {currentProductName ?? "No product"}
        </p>
        <div className="admin-scope-strip">
          <span className="panel__muted">
            Changes will be saved to the selected product metadata.
          </span>
        </div>
        <div className="admin__form">
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 1 · Autofill source (optional)</p>
            <p className="panel__step-helper">
              Load a draft from UCP/ACP/feed signals before editing manually.
            </p>
            <div className="panel__row panel__row--compact">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => void onAutofill("preview")}
                disabled={!canAutofill}
              >
                Preview UCP/ACP autofill
              </button>
              <button
                type="button"
                className="button button--primary-subtle"
                onClick={() => void onAutofill("apply")}
                disabled={!canAutofill}
              >
                Apply autofill
              </button>
            </div>
          </section>
          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 2 · Category and taxonomy</p>
            <p className="panel__step-helper">
              Set category first, then sub-category and ontology-aligned dimensions.
            </p>
            <label className="panel__label">Category (required)</label>
            <p className="panel__meta">
              Choose category first. Use cases are required for bottom-up query generation.
            </p>
            <select
              value={form.category}
              onChange={(event) =>
                onFormChange({
                  category: event.target.value,
                  subCategory: "",
                })
              }
            >
              <option value="">Select category</option>
              {Object.entries(canonicalOntology).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
            <label className="panel__label">Sub category</label>
            <select
              value={form.subCategory}
              onChange={(event) => onFormChange({ subCategory: event.target.value })}
            >
              <option value="">Select sub category</option>
              {(selectedOntology?.subCategories ?? []).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </section>
          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 3 · Use cases and audience</p>
            <p className="panel__step-helper">
              Choose concrete use cases and target audience archetypes.
            </p>
            <label className="panel__label">Use cases (ontology)</label>
            <select
              multiple
              size={Math.min(6, Math.max(3, useCases.length || 3))}
              value={parseCsv(form.useCases)}
              onChange={(event) => onFormChange({ useCases: selectedValues(event) })}
            >
              {useCases.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <p className="panel__meta">Example: daily_training, long_distance, speed_work</p>
            <label className="panel__label">Audience archetypes (ontology)</label>
            <select
              multiple
              size={Math.min(6, Math.max(3, archetypes.length || 3))}
              value={parseCsv(form.archetypes)}
              onChange={(event) => onFormChange({ archetypes: selectedValues(event) })}
            >
              {archetypes.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <p className="panel__meta">Example: beginner_runner, performance_runner</p>
          </section>
          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 4 · Features and constraints</p>
            <p className="panel__step-helper">
              Capture feature concepts, core constraints, and exclusions.
            </p>
            <label className="panel__label">Feature concepts (ontology)</label>
            <select
              multiple
              size={Math.min(6, Math.max(3, featureConcepts.length || 3))}
              value={parseCsv(form.featureConcepts)}
              onChange={(event) => onFormChange({ featureConcepts: selectedValues(event) })}
            >
              {featureConcepts.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <p className="panel__meta">Example: cushioning, stability, breathability</p>
            <label className="panel__label">Core constraints</label>
            <select
              multiple
              size={Math.min(6, Math.max(3, constraints.length || 3))}
              value={parseCsv(form.constraints)}
              onChange={(event) => onFormChange({ constraints: selectedValues(event) })}
            >
              {constraints.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <p className="panel__meta">Example: budget_sensitive, availability_required</p>
            <label className="panel__label">Must-not-target segments</label>
            <select
              multiple
              size={Math.min(6, Math.max(3, exclusions.length || 3))}
              value={parseCsv(form.exclusions)}
              onChange={(event) => onFormChange({ exclusions: selectedValues(event) })}
            >
              {exclusions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <p className="panel__meta">Example: elite_racer_only, non_sport_use</p>
          </section>
          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 5 · Keyword controls (optional)</p>
            <p className="panel__step-helper">
              Add objective and banned keyword lists to tighten generation behavior.
            </p>
            <textarea
              rows={2}
              placeholder="Objective keywords (optional, comma separated)"
              value={form.objectiveKeywords}
              onChange={(event) => onFormChange({ objectiveKeywords: event.target.value })}
            />
            <textarea
              rows={2}
              placeholder="Banned keywords (optional, comma separated)"
              value={form.bannedKeywords}
              onChange={(event) => onFormChange({ bannedKeywords: event.target.value })}
            />
          </section>
          <div className="panel__separator" />
          <button
            type="button"
            className="button button--primary-subtle"
            onClick={() => void onSave()}
            disabled={!canSave}
          >
            Save intent spec
          </button>
        </div>
      </aside>
    </div>
  );
}
