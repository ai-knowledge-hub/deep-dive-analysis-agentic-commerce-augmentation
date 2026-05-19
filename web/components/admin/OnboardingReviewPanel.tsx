"use client";

import React from "react";

type CompletionState = {
  doneClient: boolean;
  doneBrand: boolean;
  doneProduct: boolean;
  doneIntent: boolean;
};

type Props = {
  onboardingCompletion: CompletionState;
  canOpenIntentEditor: boolean;
  onAddClient: () => void;
  onAddBrand: () => void;
  onAddProduct: () => void;
  onOpenIntentEditor: () => void;
};

export function OnboardingReviewPanel({
  onboardingCompletion,
  canOpenIntentEditor,
  onAddClient,
  onAddBrand,
  onAddProduct,
  onOpenIntentEditor,
}: Props) {
  return (
    <details>
      <summary>Review</summary>
      <ul className="admin__list">
        <li>
          <span>Client</span>
          <span className="admin__meta">
            {onboardingCompletion.doneClient ? "Done" : "Missing"}
          </span>
          {!onboardingCompletion.doneClient ? (
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onAddClient}
            >
              Add client
            </button>
          ) : null}
        </li>
        <li>
          <span>Brand</span>
          <span className="admin__meta">
            {onboardingCompletion.doneBrand ? "Done" : "Missing"}
          </span>
          {!onboardingCompletion.doneBrand ? (
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onAddBrand}
            >
              Add brand
            </button>
          ) : null}
        </li>
        <li>
          <span>Product</span>
          <span className="admin__meta">
            {onboardingCompletion.doneProduct ? "Done" : "Missing"}
          </span>
          {!onboardingCompletion.doneProduct ? (
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onAddProduct}
            >
              Add product
            </button>
          ) : null}
        </li>
        <li>
          <span>Canonical intent spec</span>
          <span className="admin__meta">
            {onboardingCompletion.doneIntent ? "Done" : "Missing"}
          </span>
          {!onboardingCompletion.doneIntent ? (
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onOpenIntentEditor}
              disabled={!canOpenIntentEditor}
            >
              Open intent editor
            </button>
          ) : null}
        </li>
      </ul>
    </details>
  );
}
