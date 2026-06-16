import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { VariantsIterationPanel } from "./VariantsIterationPanel";

describe("VariantsIterationPanel", () => {
  it("exposes a focus target for variants shortcuts", () => {
    const ref = React.createRef<HTMLElement>();

    render(
      <VariantsIterationPanel
        ref={ref}
        labMode="lab"
        variantCount={0}
        selectedExperimentId="experiment-1"
        isRecommending={false}
        onRecommendNextTest={vi.fn()}
      >
        <div>Variant controls</div>
      </VariantsIterationPanel>,
    );

    ref.current?.focus();

    expect(screen.getByLabelText(/Variants and iteration/i)).toHaveFocus();
  });
});
