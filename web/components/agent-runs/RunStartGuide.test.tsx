import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RunStartGuide } from "./RunStartGuide";
import type { AgentAction, AgentRun } from "../../lib/types";

describe("RunStartGuide cancellation", () => {
  it.each(["canceled", "cancelled"])("routes %s runs with pending work to the receipt instead of execution", async (status) => {
    const onStart = vi.fn();
    const onApprove = vi.fn();
    const onOpenInterventions = vi.fn();
    render(<RunStartGuide
      selectedRun={{ id: "run-a", status } as AgentRun}
      nextRecommendedAction={{ action: { id: "action-a", rationale: "Pending work" } as AgentAction, guardrails: [], hint: "Continue" }}
      loading={false}
      onStart={onStart}
      onApprove={onApprove}
      onOpenInterventions={onOpenInterventions}
      onReviewAction={vi.fn()}
    />);
    expect(screen.getByText(/This run is terminal/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start or step run" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve next action" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View cancellation record" }));
    expect(onOpenInterventions).toHaveBeenCalledOnce();
    expect(onStart).not.toHaveBeenCalled();
    expect(onApprove).not.toHaveBeenCalled();
  });
});
