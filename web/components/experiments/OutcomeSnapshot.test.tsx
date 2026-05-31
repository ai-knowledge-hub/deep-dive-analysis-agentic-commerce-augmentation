import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { OutcomeSnapshot } from "./OutcomeSnapshot";

describe("OutcomeSnapshot", () => {
  it("uses readable evidence protocol wording", () => {
    render(
      <OutcomeSnapshot
        snapshot={{
          runVariantLabel: "Homepage benefit copy",
          runQueryLabel: "Best trail shoes",
          runCreatedAt: null,
          winRate: "60%",
          avgScore: "0.72",
          validationState: "Pending",
          snapshotVersion: 3,
        }}
        hasValidationSignals={false}
        onOpenValidation={vi.fn()}
      />,
    );

    expect(screen.getByText(/Evidence protocol:/i)).toBeInTheDocument();
    expect(screen.getByText(/Outcome summary/i)).toBeInTheDocument();
    expect(screen.queryByText(/Protocol snapshot/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Outcome snapshot/i)).not.toBeInTheDocument();
  });
});
