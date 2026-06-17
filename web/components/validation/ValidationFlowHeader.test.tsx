import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ValidationFlowHeader } from "./ValidationFlowHeader";

describe("ValidationFlowHeader", () => {
  it("surfaces one primary next validation action before outcome detail", () => {
    const onRunNextAction = vi.fn();
    render(
      <ValidationFlowHeader
        currentStep={2}
        steps={[
          { id: 1, label: "Provider defaults", done: true },
          { id: 2, label: "Run synthetic validation", done: false },
        ]}
        nextAction={{
          label: "Create synthetic validation",
          helper: "Run a fast validation before reviewing secondary evidence.",
        }}
        winnerLabel="No result yet"
        scoreText="--"
        evidenceText="--"
        observedLogged={0}
        observedVerified={0}
        observedAccuracyText="--"
        observedUnlockReady={false}
        hasSyntheticResult={false}
        onRunNextAction={onRunNextAction}
        onOpenExperiments={vi.fn()}
      />,
    );

    expect(screen.getByText(/Next recommended action/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Create synthetic validation/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Validation outcome summary/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Create synthetic validation/i }));
    expect(onRunNextAction).toHaveBeenCalledTimes(1);
  });
});
