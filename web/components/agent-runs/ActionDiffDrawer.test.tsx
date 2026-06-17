import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ActionDiffDrawer } from "./ActionDiffDrawer";

const emptyDiff = {
  outputsVsPreviousAction: { added: [], changed: [], removed: [] },
  outputsVsPreviousCapability: { added: [], changed: [], removed: [] },
  inputsVsPreviousAction: { added: [], changed: [], removed: [] },
  inputsVsPreviousCapability: { added: [], changed: [], removed: [] },
  currentInputs: { product: "Demo product" },
  currentOutputs: { result: "Ready" },
  previousOutputs: {},
  previousCapabilityOutputs: {},
  copyDiffVsPreviousAction: [],
  copyDiffVsPreviousCapability: [],
};

describe("ActionDiffDrawer", () => {
  it("uses readable change detail wording", () => {
    render(
      <ActionDiffDrawer
        open
        selectedAction={{
          id: "action-1",
          sequence: 3,
          status: "executed",
          capability_name: "run_variant",
          inputs: {},
          outputs: {},
        }}
        diff={emptyDiff}
        hideUnchangedDiffLines={false}
        onHideUnchangedDiffLinesChange={vi.fn()}
        onClose={vi.fn()}
        formatJsonPreview={(value) => JSON.stringify(value, null, 2)}
      />,
    );

    expect(screen.getByRole("heading", { name: /Change details/i })).toBeInTheDocument();
    expect(screen.getByText(/Run inputs and outputs/i)).toBeInTheDocument();
    expect(screen.getByText(/Output changes vs previous similar action/i)).toBeInTheDocument();
    expect(screen.queryByText(/Artifact diff details/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Snapshot payloads/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/previous same capability/i)).not.toBeInTheDocument();
  });
});
