import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ExperimentRunSettings } from "./ExperimentRunSettings";

describe("ExperimentRunSettings", () => {
  it("uses readable evidence set wording", () => {
    render(
      <ExperimentRunSettings
        runMode="simulation"
        retrievalMaxResults="5"
        currentProtocolSnapshotVersion={4}
        runVariantDisabledReason={null}
        onRunModeChange={vi.fn()}
        onRetrievalMaxResultsChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/Active evidence set: v4/i)).toBeInTheDocument();
    expect(screen.queryByText(/evidence protocol/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/snapshot v4/i)).not.toBeInTheDocument();
  });
});
