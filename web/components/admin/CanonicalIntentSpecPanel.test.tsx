import { render, screen } from "@testing-library/react";
import React, { createRef } from "react";
import { describe, expect, it, vi } from "vitest";

import { CanonicalIntentSpecPanel } from "./CanonicalIntentSpecPanel";

describe("CanonicalIntentSpecPanel", () => {
  it("exposes a focus target for onboarding shortcuts", () => {
    const ref = createRef<HTMLDetailsElement>();
    const { container } = render(
      <CanonicalIntentSpecPanel
        ref={ref}
        canOpenIntentEditor
        intentSpecSaved={false}
        intentSpecAutofillStatus={null}
        intentSpecError={null}
        onOpenIntentEditor={vi.fn()}
      />,
    );

    const panel = container.querySelector('[aria-label="Canonical intent spec"]');

    expect(ref.current).toBe(panel);
    ref.current?.focus();
    expect(document.activeElement).toBe(ref.current);
  });

  it("describes saved intent context without exposing metadata keys", () => {
    render(
      <CanonicalIntentSpecPanel
        canOpenIntentEditor
        intentSpecSaved={false}
        intentSpecAutofillStatus={null}
        intentSpecError={null}
        onOpenIntentEditor={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/canonical intent profile/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/canonical_intent_spec/i)).not.toBeInTheDocument();
  });
});
