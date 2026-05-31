import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { CanonicalIntentSpecPanel } from "./CanonicalIntentSpecPanel";

describe("CanonicalIntentSpecPanel", () => {
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
