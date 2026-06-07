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

export type CreateClientOnboardingForm = {
  clientId: string;
  clientName: string;
  brandId: string;
  brandName: string;
  productsText: string;
  category: string;
  subCategory: string;
  useCases: string;
  archetypes: string;
  featureConcepts: string;
  constraints: string;
  exclusions: string;
  objectiveKeywords: string;
  bannedKeywords: string;
  ucpOfferUrl: string;
  ucpMerchantName: string;
  ucpCurrency: string;
  acpEnableSearch: boolean;
  acpEnableCheckout: boolean;
};

type Props = {
  isOpen: boolean;
  isBusy: boolean;
  canSubmit: boolean;
  error: string | null;
  success: string | null;
  form: CreateClientOnboardingForm;
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
  onFormChange: (patch: Partial<CreateClientOnboardingForm>) => void;
  onSubmit: () => void | Promise<void>;
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

export function CreateClientOnboardingDrawer({
  isOpen,
  isBusy,
  canSubmit,
  error,
  success,
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
  onSubmit,
}: Props) {
  if (!isOpen) return null;

  return (
    <div
      className="admin-onboarding__drawer-overlay"
      onClick={() => {
        if (!isBusy) onClose();
      }}
    >
      <aside
        className="admin-onboarding__drawer"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel__header">
          <h3>Add new client</h3>
          <button
            type="button"
            className="button button--ghost"
            onClick={onClose}
            disabled={isBusy}
          >
            Close
          </button>
        </div>
        <p className="panel__meta">
          Creates one client, one initial brand, a product list, and canonical/UCP/ACP metadata
          in one flow.
        </p>
        <div className="admin-scope-strip">
          <span className="panel__muted">
            Current scope: {currentClientName ?? "No client"} / {currentBrandName ?? "No brand"} /{" "}
            {currentProductName ?? "No product"}
          </span>
        </div>
        <div className="admin__form">
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 1 · Client</p>
            <p className="panel__step-helper">
              Define the tenant workspace that will own brands and products.
            </p>
            <span className="panel__label">Client</span>
            <input
              type="text"
              placeholder="Client key"
              value={form.clientId}
              onChange={(event) => onFormChange({ clientId: event.target.value })}
            />
            <input
              type="text"
              placeholder="Client name"
              value={form.clientName}
              onChange={(event) => onFormChange({ clientName: event.target.value })}
            />
          </section>

          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 2 · Initial brand</p>
            <p className="panel__step-helper">Create the first brand under the new client.</p>
            <span className="panel__label">Initial brand</span>
            <input
              type="text"
              placeholder="Brand key"
              value={form.brandId}
              onChange={(event) => onFormChange({ brandId: event.target.value })}
            />
            <input
              type="text"
              placeholder="Brand name"
              value={form.brandName}
              onChange={(event) => onFormChange({ brandName: event.target.value })}
            />
          </section>

          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 3 · Products</p>
            <p className="panel__step-helper">
              Add one or more products. Each line should include key, name, and description.
            </p>
            <span className="panel__label">Products list</span>
            <textarea
              rows={5}
              placeholder={
                "product-key|Product name|Short description\nproduct-key-2|Product 2|Short description"
              }
              value={form.productsText}
              onChange={(event) => onFormChange({ productsText: event.target.value })}
            />
          </section>

          <div className="panel__separator" />
          <section className="admin-drawer-step">
            <p className="panel__subheading">Step 4 · Canonical intent spec</p>
            <p className="panel__step-helper">
              Category and use cases are required to enable bottom-up query generation.
            </p>
            <span className="panel__label">Canonical intent spec</span>
            <p className="panel__meta">Choose a category first to load ontology options.</p>
            <label className="panel__label">Category</label>
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
            <label className="panel__label">Use cases</label>
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
            <label className="panel__label">Audience archetypes</label>
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
            <label className="panel__label">Feature concepts</label>
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
          <details className="admin-advanced-defaults">
            <summary>Advanced defaults (optional)</summary>
            <span className="panel__label">UCP defaults</span>
            <input
              type="url"
              placeholder="Offer URL"
              value={form.ucpOfferUrl}
              onChange={(event) => onFormChange({ ucpOfferUrl: event.target.value })}
            />
            <input
              type="text"
              placeholder="Merchant name"
              value={form.ucpMerchantName}
              onChange={(event) => onFormChange({ ucpMerchantName: event.target.value })}
            />
            <input
              type="text"
              placeholder="Currency"
              value={form.ucpCurrency}
              onChange={(event) => onFormChange({ ucpCurrency: event.target.value })}
            />

            <span className="panel__label">ACP defaults</span>
            <label className="panel__label panel__label--inline">
              <input
                type="checkbox"
                checked={form.acpEnableSearch}
                onChange={(event) => onFormChange({ acpEnableSearch: event.target.checked })}
              />
              Enable search
            </label>
            <label className="panel__label panel__label--inline">
              <input
                type="checkbox"
                checked={form.acpEnableCheckout}
                onChange={(event) => onFormChange({ acpEnableCheckout: event.target.checked })}
              />
              Enable checkout
            </label>
          </details>

          <div className="panel__separator" />
          {error ? <p className="panel__error">{error}</p> : null}
          {success ? <p className="panel__success">{success}</p> : null}
          <button
            type="button"
            className="button button--primary-subtle"
            onClick={() => void onSubmit()}
            disabled={!canSubmit || isBusy}
          >
            {isBusy ? "Creating..." : "Create client onboarding"}
          </button>
        </div>
      </aside>
    </div>
  );
}
