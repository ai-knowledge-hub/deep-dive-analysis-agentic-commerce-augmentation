import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OperatorCommandDecision } from "./OperatorCommandDecision";
import type { OperatorCommandProposal, OperatorCommandReceipt } from "../../lib/operatorConversationTypes";

function proposal(decision: "approve" | "reject"): OperatorCommandProposal {
  return { contract: "workflow.operator-command-proposal.v4", proposal_id: "review-1", proposal_digest: "a".repeat(64), tenant_id: "tenant-1", principal_id: "human:user", run_id: "run-1", command_type: decision,
    parameters: { action_id: "action-1", action_status: "proposed", review: { capability_name: "request_synthetic_validation", normalized_inputs: { experiment_id: "experiment-1" }, inputs_hash: "b".repeat(64), registry_authority: {}, approval_id: null, approval_sequence: null, approval_envelope_digest: null, side_effects: ["Creates a validation job"], review_checklist: ["Verify experiment scope"] } },
    source: { active_graph_revision: 1, run_status: "paused", run_state: "battery_ready", snapshot_digest: "c".repeat(64) }, preflight: { digest: "d".repeat(64), result: { allowed: true, risk_level: "medium", blockers: [], warnings: [], summary: "Review this action" } }, idempotency_key: "review:1", issued_at: "2026-10-04T00:00:00Z", expires_at: "2099-01-01T00:00:00Z", consequences: ["Approval does not execute the action or start or resume this run."] };
}

describe("exact action review", () => {
  it.each(["approve", "reject"] as const)("requires explicit %s after displaying exact inputs and effects", async (decision) => {
    const user = userEvent.setup(), onConfirm = vi.fn(), onDismiss = vi.fn(); const review = proposal(decision);
    render(<OperatorCommandDecision proposal={review} receipt={null} runId="run-1" confirming={false} onConfirm={onConfirm} onDismiss={onDismiss} />);
    expect(screen.getByText(/experiment-1/)).toBeInTheDocument(); expect(screen.getByText("Creates a validation job")).toBeInTheDocument(); expect(screen.getByText("Verify experiment scope")).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled(); await user.click(screen.getByRole("button", { name: `Confirm ${decision}` })); expect(onConfirm).toHaveBeenCalledExactlyOnceWith(review);
  });
  it("dismisses without authorizing and distinguishes the durable decision from run status", async () => {
    const user = userEvent.setup(), onConfirm = vi.fn(), onDismiss = vi.fn(); const review = proposal("approve");
    const view = render(<OperatorCommandDecision proposal={review} receipt={null} runId="run-1" confirming={false} onConfirm={onConfirm} onDismiss={onDismiss} />);
    await user.click(screen.getByRole("button", { name: "Dismiss" })); expect(onDismiss).toHaveBeenCalledExactlyOnceWith("review-1"); expect(onConfirm).not.toHaveBeenCalled();
    const receipt: OperatorCommandReceipt = { contract: "workflow.operator-command-receipt.v4", receipt_id: "receipt-1", proposal_id: "review-1", proposal_digest: review.proposal_digest, run_id: "run-1", command_type: "approve", outcome: "approved", resulting_run_status: "paused", event_ids: { command: "command-1", lifecycle: "approval-event" }, acknowledgement: "exact_action_decision_recorded", propagation_state: "runtime_propagation_not_certified", completed_at: "2026-10-04T00:00:01Z", receipt_digest: "e".repeat(64), action_id: "action-1", approval_id: "approval-1", approval_sequence: 2, approval_envelope_digest: "f".repeat(64) };
    view.rerender(<OperatorCommandDecision proposal={review} receipt={receipt} runId="run-1" confirming={false} onConfirm={onConfirm} onDismiss={onDismiss} />);
    expect(screen.queryByRole("button", { name: "Confirm approve" })).not.toBeInTheDocument(); expect(screen.getByLabelText("Action approval receipt")).toHaveTextContent("Recorded outcome: approved"); expect(screen.getByLabelText("Action approval receipt")).toHaveTextContent("approval-1"); expect(screen.getByText("This decision did not execute the action or start or resume the run.")).toBeInTheDocument();
  });
});

it("shows exact retry scope, requires confirmation and reports a proposed child needing fresh approval", async () => {
  const user = userEvent.setup(), onConfirm = vi.fn(), onDismiss = vi.fn();
  const base = proposal("approve");
  const retry: OperatorCommandProposal = { ...base, contract: "workflow.operator-command-proposal.v5", command_type: "retry", parameters: { action_id: "failed-action", action_status: "failed", retry_strategy: "same_action", retry_plan: { strategy: "same_action", capability_name: "request_synthetic_validation", normalized_inputs: { experiment_id: "retry-experiment" }, inputs_hash: "b".repeat(64), side_effects: ["Creates a validation job"], review_checklist: ["Verify experiment scope"] } }, consequences: ["Fresh approval is required before execution; prior approval is not copied."] };
  const view = render(<OperatorCommandDecision proposal={retry} receipt={null} runId="run-1" confirming={false} onConfirm={onConfirm} onDismiss={onDismiss} />);
  expect(screen.getByText(/Failed source action failed-action/)).toBeInTheDocument();
  expect(screen.getByText(/retry-experiment/)).toBeInTheDocument();
  expect(onConfirm).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(onConfirm).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Confirm retry" }));
  expect(onConfirm).toHaveBeenCalledExactlyOnceWith(retry);
  const receipt: OperatorCommandReceipt = { contract: "workflow.operator-command-receipt.v5", receipt_id: "retry-receipt", proposal_id: retry.proposal_id, proposal_digest: retry.proposal_digest, run_id: "run-1", command_type: "retry", outcome: "proposed", resulting_run_status: "paused", event_ids: { command: "command-1", lifecycle: "retry-event" }, acknowledgement: "retry_action_proposed", propagation_state: "runtime_propagation_not_certified", completed_at: "2026-10-05T00:00:01Z", receipt_digest: "e".repeat(64), source_action_id: "failed-action", action_id: "new-action", retry_strategy: "same_action", retry_count: 1, action_sequence: 2, effect_idempotency_key: "retry:failed-action:same_action:1" };
  view.rerender(<OperatorCommandDecision proposal={retry} receipt={receipt} runId="run-1" confirming={false} onConfirm={onConfirm} onDismiss={onDismiss} />);
  expect(screen.queryByRole("button", { name: "Confirm retry" })).not.toBeInTheDocument();
  const recorded = screen.getByLabelText("Retry action proposed receipt");
  expect(recorded).toHaveTextContent("Recorded outcome: proposed");
  expect(recorded).toHaveTextContent("failed-action → proposed action new-action");
  expect(recorded).toHaveTextContent("Approve action new-action");
  expect(recorded).toHaveTextContent("Confirmation did not execute work or start or resume the run.");
  expect(recorded).not.toHaveTextContent("approval undefined");
});
