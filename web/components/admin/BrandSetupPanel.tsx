"use client";

import React from "react";
import type { AdminBrand } from "../../lib/types";

export type BrandSetupForm = {
  id: string;
  name: string;
};

type Props = {
  activeClientId: string;
  selectedClientName?: string | null;
  brands: AdminBrand[];
  showCreateBrand: boolean;
  brandForm: BrandSetupForm;
  canCreateBrand: boolean;
  onShowCreateBrandChange: (show: boolean) => void;
  onBrandFormChange: (patch: Partial<BrandSetupForm>) => void;
  onCreateBrand: () => void;
};

export function BrandSetupPanel({
  activeClientId,
  selectedClientName,
  brands,
  showCreateBrand,
  brandForm,
  canCreateBrand,
  onShowCreateBrandChange,
  onBrandFormChange,
  onCreateBrand,
}: Props) {
  return (
    <details>
      <summary>Brand setup</summary>
      {activeClientId ? (
        <>
          <p className="panel__meta">
            Creates and edits brands for client: <strong>{selectedClientName ?? activeClientId}</strong>
          </p>
          {brands.length === 0 ? (
            <p className="panel__empty">No brands yet.</p>
          ) : (
            <ul className="admin__list">
              {brands.map((brand) => (
                <li key={brand.id}>
                  <span>{brand.name}</span>
                  <span className="admin__meta">{brand.id}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="panel__actions">
            <button
              type="button"
              className="button button--ghost"
              onClick={() => onShowCreateBrandChange(!showCreateBrand)}
            >
              {showCreateBrand ? "Hide create brand form" : "Add new brand"}
            </button>
          </div>
          {showCreateBrand ? (
            <div className="admin__form">
              <span className="panel__label">
                Create brand for {selectedClientName ?? activeClientId}
              </span>
              <input
                type="text"
                placeholder="brand-id"
                value={brandForm.id}
                onChange={(event) => onBrandFormChange({ id: event.target.value })}
                required
              />
              <input
                type="text"
                placeholder="Brand name"
                value={brandForm.name}
                onChange={(event) => onBrandFormChange({ name: event.target.value })}
                required
              />
              <button
                type="button"
                className="button button--primary-subtle"
                onClick={onCreateBrand}
                disabled={!canCreateBrand}
              >
                Add brand
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <p className="panel__empty">Select a client first.</p>
      )}
    </details>
  );
}
