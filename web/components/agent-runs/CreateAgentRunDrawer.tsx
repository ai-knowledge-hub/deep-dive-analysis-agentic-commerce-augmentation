"use client";

import React from "react";
import type { Experiment } from "../../lib/types";
import { formatJsonPreview } from "./actionDiffUtils";
import { formatDateCompact } from "./registryAudit";

export type CreateAgentRunForm = {
  experiment_id: string;
  requires_approval: boolean;
  run_mode: "plan_only" | "auto_execute_safe";
  allowed_capabilities: string[];
  objective: Record<string, unknown>;
  budgets: Record<string, unknown>;
  approval_policy: Record<string, unknown>;
};

type Props = {
  open: boolean;
  experiments: Experiment[];
  form: CreateAgentRunForm;
  loading: boolean;
  canCreate: boolean;
  onClose: () => void;
  onFormChange: (patch: Partial<CreateAgentRunForm>) => void;
  onCreate: () => void;
};

export function CreateAgentRunDrawer({
  open,
  experiments,
  form,
  loading,
  canCreate,
  onClose,
  onFormChange,
  onCreate,
}: Props) {
  if (!open) return null;

  return (
    <div className="drawer">
      <div className="drawer__overlay" onClick={onClose} />
      <div className="drawer__panel">
        <div className="drawer__header">
          <h2 className="drawer__title">New agent run</h2>
          <button className="drawer__close" onClick={onClose}>
            x
          </button>
        </div>
        <div className="drawer__body">
          <label className="field">
            <span className="field__label">Experiment (optional)</span>
            <select
              className="field__input"
              value={form.experiment_id}
              onChange={(event) => onFormChange({ experiment_id: event.target.value })}
            >
              <option value="">None (global agent run)</option>
              {experiments.map((experiment) => (
                <option key={experiment.id} value={experiment.id}>
                  {experiment.name || "Untitled"} · {experiment.id.slice(0, 8)} ·{" "}
                  {formatDateCompact(experiment.updated_at || experiment.created_at)}
                </option>
              ))}
            </select>
            {experiments.length === 0 ? (
              <div className="panel__muted">
                No experiments found in current scope. You can still create a global run.
              </div>
            ) : null}
          </label>

          <details className="admin-advanced-defaults">
            <summary>Manual experiment id (advanced)</summary>
            <label className="field">
              <span className="field__label">Override with UUID</span>
              <input
                className="field__input"
                value={form.experiment_id}
                onChange={(event) => onFormChange({ experiment_id: event.target.value.trim() })}
                placeholder="paste experiment uuid"
              />
            </label>
          </details>

          <label className="field field--row">
            <span className="field__label">Requires approval</span>
            <input
              type="checkbox"
              checked={form.requires_approval}
              onChange={(event) => onFormChange({ requires_approval: event.target.checked })}
            />
          </label>

          <label className="field">
            <span className="field__label">Run mode</span>
            <select
              className="field__input"
              value={form.run_mode}
              onChange={(event) =>
                onFormChange({
                  run_mode:
                    event.target.value === "auto_execute_safe" ? "auto_execute_safe" : "plan_only",
                })
              }
            >
              <option value="plan_only">Plan only (recommended)</option>
              <option value="auto_execute_safe">Auto-execute safe steps</option>
            </select>
          </label>

          <JsonTextArea
            label="Run objective"
            helper="What this run should optimize. The default is tuned for confidence-weighted test planning."
            value={form.objective}
            rows={8}
            onChange={(objective) => onFormChange({ objective })}
          />
          <details className="admin-advanced-defaults">
            <summary>Advanced run setup</summary>
            <p className="panel__muted">
              Optional controls for allowed actions, budget limits, and approval rules.
            </p>
            <label className="field">
              <span className="field__label">Allowed actions</span>
              <textarea
                className="field__input field__textarea"
                value={form.allowed_capabilities.join("\n")}
                onChange={(event) =>
                  onFormChange({
                    allowed_capabilities: event.target.value
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
                rows={7}
              />
            </label>
            <JsonTextArea
              label="Budget limits"
              helper="Caps that prevent a run from spending or testing more than intended."
              value={form.budgets}
              rows={6}
              onChange={(budgets) => onFormChange({ budgets })}
            />
            <JsonTextArea
              label="Approval rules"
              helper="Actions that must wait for a human decision before the run continues."
              value={form.approval_policy}
              rows={6}
              onChange={(approval_policy) => onFormChange({ approval_policy })}
            />
          </details>
        </div>
        <div className="drawer__footer">
          <button className="button button--ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="button button--ghost" onClick={onCreate} disabled={!canCreate || loading}>
            Create run
          </button>
        </div>
      </div>
    </div>
  );
}

function JsonTextArea({
  label,
  helper,
  value,
  rows,
  onChange,
}: {
  label: string;
  helper?: string;
  value: Record<string, unknown>;
  rows: number;
  onChange: (value: Record<string, unknown>) => void;
}) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      <textarea
        className="field__input field__textarea"
        value={formatJsonPreview(value)}
        onChange={(event) => {
          try {
            const parsed = JSON.parse(event.target.value || "{}");
            onChange(parsed);
          } catch {
            // Keep last valid structured value until the operator finishes editing.
          }
        }}
        rows={rows}
      />
      {helper ? <span className="panel__muted">{helper}</span> : null}
    </label>
  );
}
