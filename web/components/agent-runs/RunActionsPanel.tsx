"use client";

import React from "react";
import {
  formatOperatorActionName,
  formatOperatorIdentifier,
} from "../../lib/operatorDisplayLanguage";
import type { AgentAction } from "../../lib/types";

type BudgetSeverity = "ok" | "warn" | "danger";

type BudgetTelemetry = {
  maxActions: number | null;
  maxVariantRuns: number | null;
  maxCostUsd: number | null;
  executedActions: number;
  executedVariantRuns: number;
  totalCostUsd: number;
  actionPct: number | null;
  variantPct: number | null;
  costPct: number | null;
};

type BudgetState = {
  actionSeverity: BudgetSeverity;
  variantSeverity: BudgetSeverity;
  costSeverity: BudgetSeverity;
  actionBlocked: boolean;
  variantBlocked: boolean;
  costBlocked: boolean;
};

type ActionCounters = {
  proposed: number;
  approved: number;
  executing: number;
  executed: number;
  failed: number;
};

type Props = {
  actions: AgentAction[];
  selectedAction: AgentAction | null;
  actionCounters: ActionCounters;
  budgetTelemetry: BudgetTelemetry;
  budgetState: BudgetState;
  loading: boolean;
  getGuardrailReasonsForAction: (action: AgentAction) => string[];
  onSelectAction: (actionId: string) => void;
  onDecision: (actionId: string, decision: "approve" | "reject") => void;
  formatJsonPreview: (value: unknown) => string;
};

function budgetCardClass(severity: BudgetSeverity): string {
  if (severity === "warn") return "agent-budget-card is-warn";
  if (severity === "danger") return "agent-budget-card is-danger";
  return "agent-budget-card";
}

function BudgetCard({
  title,
  value,
  pct,
  severity,
}: {
  title: string;
  value: string;
  pct: number | null;
  severity: BudgetSeverity;
}) {
  return (
    <div className={budgetCardClass(severity)}>
      <div className="agent-budget-card__header">
        <strong>{title}</strong>
        <span>{value}</span>
      </div>
      <div className="agent-budget-card__bar">
        <div
          className="agent-budget-card__fill"
          style={{ width: pct == null ? "0%" : `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function RunActionsPanel({
  actions,
  selectedAction,
  actionCounters,
  budgetTelemetry,
  budgetState,
  loading,
  getGuardrailReasonsForAction,
  onSelectAction,
  onDecision,
  formatJsonPreview,
}: Props) {
  return (
    <>
      {budgetState.actionBlocked || budgetState.variantBlocked || budgetState.costBlocked ? (
        <div className="panel__notice panel__notice--warning">
          Budget guardrail active:{" "}
          {budgetState.actionBlocked
            ? "max actions reached."
            : budgetState.variantBlocked
              ? "max variant runs reached for run variant."
            : "max cost reached."}{" "}
          Proposed risky approvals are disabled until budget changes.
        </div>
      ) : null}

      <details className="panel__details agent-action-health">
        <summary className="panel__details-summary">Action health and budgets</summary>
        <div className="agent-budget-grid">
          <BudgetCard
            title="Action budget"
            value={`${budgetTelemetry.executedActions}/${budgetTelemetry.maxActions ?? "—"}`}
            pct={budgetTelemetry.actionPct}
            severity={budgetState.actionSeverity}
          />
          <BudgetCard
            title="Variant run budget"
            value={`${budgetTelemetry.executedVariantRuns}/${budgetTelemetry.maxVariantRuns ?? "—"}`}
            pct={budgetTelemetry.variantPct}
            severity={budgetState.variantSeverity}
          />
          <BudgetCard
            title="Estimated spend"
            value={`$${budgetTelemetry.totalCostUsd.toFixed(2)}${
              budgetTelemetry.maxCostUsd != null
                ? ` / $${budgetTelemetry.maxCostUsd.toFixed(2)}`
                : ""
            }`}
            pct={budgetTelemetry.costPct}
            severity={budgetState.costSeverity}
          />
        </div>
        <div className="control-chip-row">
          <span className="control-chip">
            Proposed: {actionCounters.proposed}
          </span>
          <span className="control-chip">
            Approved: {actionCounters.approved}
          </span>
          <span className="control-chip">
            Executing: {actionCounters.executing}
          </span>
          <span className="control-chip">
            Executed: {actionCounters.executed}
          </span>
          <span className="control-chip">
            Failed: {actionCounters.failed}
          </span>
        </div>
      </details>

      <div className="table">
        <div className="table__header">
          <div className="table__cell">#</div>
          <div className="table__cell">Action</div>
          <div className="table__cell">Status</div>
          <div className="table__cell">Why</div>
          <div className="table__cell">Decision</div>
        </div>
        {actions.map((action) => {
          const guardrailReasons = getGuardrailReasonsForAction(action);
          const hasGuardrailBlock = guardrailReasons.length > 0;
          return (
            <div
              key={action.id}
              className={`table__row ${selectedAction?.id === action.id ? "is-active" : ""}`}
              onClick={() => onSelectAction(action.id)}
            >
              <div className="table__cell" data-label="#">
                {action.sequence}
              </div>
              <div className="table__cell" data-label="Action">
                <div className="table__strong">
                  {formatOperatorActionName(action.capability_name)}
                </div>
                {action.skill_id || action.tool_id ? (
                  <details className="panel__details agent-action-technical">
                    <summary className="panel__details-summary">Technical mapping</summary>
                    <div className="table__muted">
                      {action.capability_version ? (
                        <div>Version: {action.capability_version}</div>
                      ) : null}
                      {action.skill_id ? (
                        <div>Skill: {formatOperatorIdentifier(action.skill_id)}</div>
                      ) : null}
                      {action.tool_id ? (
                        <div>Tool: {formatOperatorIdentifier(action.tool_id)}</div>
                      ) : null}
                    </div>
                  </details>
                ) : null}
              </div>
              <div className="table__cell" data-label="Status">
                {action.status}
              </div>
              <div
                className="table__cell table__cell--rationale table__muted"
                data-label="Why"
              >
                {action.rationale || (action.error ? `Error: ${action.error}` : "—")}
              </div>
              <div className="table__cell table__actions" data-label="Decision">
                {action.status === "proposed" ? (
                  <>
                    <button
                      type="button"
                      className="button button--ghost button--sm"
                      onClick={() => onDecision(action.id, "approve")}
                      disabled={loading || hasGuardrailBlock}
                      title={guardrailReasons[0] || undefined}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="button button--ghost button--sm"
                      onClick={() => onDecision(action.id, "reject")}
                      disabled={loading}
                    >
                      Reject
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="button button--ghost button--sm"
                    onClick={() => {
                      const payload = formatJsonPreview({
                        inputs: action.inputs,
                        outputs: action.outputs,
                      });
                      window.navigator.clipboard?.writeText(payload);
                    }}
                    disabled={loading}
                  >
                    Copy payload
                  </button>
                )}
                {hasGuardrailBlock ? (
                  <div className="agent-guardrail-list">
                    {guardrailReasons.map((reason) => (
                      <span
                        key={`${action.id}-${reason}`}
                        className="panel__badge panel__badge--warning"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
        {actions.length === 0 ? (
          <div className="panel__muted">
            No actions recorded yet. Next: we’ll add plan generation and execution ticks.
          </div>
        ) : null}
      </div>
    </>
  );
}
