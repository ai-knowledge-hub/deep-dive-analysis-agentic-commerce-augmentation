import { render } from "@testing-library/react";
import React, { createRef } from "react";
import { describe, expect, it, vi } from "vitest";

import { BrandSetupPanel } from "./BrandSetupPanel";

describe("BrandSetupPanel", () => {
  it("exposes a focus target for onboarding shortcuts", () => {
    const ref = createRef<HTMLDetailsElement>();
    const { container } = render(
      <BrandSetupPanel
        ref={ref}
        activeClientId="client-a"
        selectedClientName="Client A"
        brands={[]}
        showCreateBrand={false}
        brandForm={{ id: "", name: "" }}
        canCreateBrand={false}
        onShowCreateBrandChange={vi.fn()}
        onBrandFormChange={vi.fn()}
        onCreateBrand={vi.fn()}
      />,
    );

    const panel = container.querySelector('[aria-label="Brand setup"]');

    expect(ref.current).toBe(panel);
    ref.current?.focus();
    expect(document.activeElement).toBe(ref.current);
  });
});
