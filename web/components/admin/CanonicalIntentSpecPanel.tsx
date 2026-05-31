"use client";

import React from "react";

type Props = {
  canOpenIntentEditor: boolean;
  intentSpecSaved: boolean;
  intentSpecAutofillStatus: string | null;
  intentSpecError: string | null;
  onOpenIntentEditor: () => void;
};

export function CanonicalIntentSpecPanel({
  canOpenIntentEditor,
  intentSpecSaved,
  intentSpecAutofillStatus,
  intentSpecError,
  onOpenIntentEditor,
}: Props) {
  return (
    <details>
      <summary>Canonical intent spec</summary>
      <p className="panel__meta">
        Capture objective product context used by bottom-up query generation.
      </p>
      <p className="panel__meta">
        Saved with the selected product as its canonical intent profile.
      </p>
      <button
        type="button"
        className="button button--primary-subtle"
        onClick={onOpenIntentEditor}
        disabled={!canOpenIntentEditor}
      >
        Open intent spec editor
      </button>
      {intentSpecSaved ? <p className="panel__success">Saved canonical intent spec.</p> : null}
      {intentSpecAutofillStatus ? (
        <p className="panel__meta">{intentSpecAutofillStatus}</p>
      ) : null}
      {intentSpecError ? <p className="panel__error">{intentSpecError}</p> : null}
    </details>
  );
}
