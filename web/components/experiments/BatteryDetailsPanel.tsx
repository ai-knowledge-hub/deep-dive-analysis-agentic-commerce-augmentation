"use client";

import React from "react";
import type { QueryBattery, QueryBatteryMetrics, QueryBatteryQuery } from "../../lib/types";

export type BatteryDetailsEdit = {
  name: string;
  purpose: string;
  status: string;
};

type Props = {
  open: boolean;
  selectedBattery: QueryBattery | null;
  edit: BatteryDetailsEdit;
  queryStatus: string | null;
  queries: QueryBatteryQuery[];
  metrics: QueryBatteryMetrics | null;
  isSubmitting: boolean;
  onOpenChange: (open: boolean) => void;
  onEditChange: (edit: BatteryDetailsEdit) => void;
  onQueryToggle: (batteryId: string, queryId: string, enabled: boolean) => void;
  onQueryDelete: (batteryId: string, queryId: string) => void;
  onQueryWeight: (batteryId: string, queryId: string, weight: number) => void;
  onUpdateBattery: () => void;
};

export function BatteryDetailsPanel({
  open,
  selectedBattery,
  edit,
  queryStatus,
  queries,
  metrics,
  isSubmitting,
  onOpenChange,
  onEditChange,
  onQueryToggle,
  onQueryDelete,
  onQueryWeight,
  onUpdateBattery,
}: Props) {
  const updateEdit = (patch: Partial<BatteryDetailsEdit>) => {
    onEditChange({ ...edit, ...patch });
  };

  return (
    <details open={open} onToggle={(event) => onOpenChange(event.currentTarget.open)}>
      <summary className="panel__label">Battery details and query settings</summary>
      {selectedBattery ? (
        <div className="panel__form">
          <label className="panel__label">
            Battery name
            <input
              className="panel__input"
              value={edit.name}
              onChange={(event) => updateEdit({ name: event.target.value })}
            />
          </label>
          <label className="panel__label">
            Purpose
            <input
              className="panel__input"
              value={edit.purpose}
              onChange={(event) => updateEdit({ purpose: event.target.value })}
            />
          </label>
          <label className="panel__label">
            Status
            <select
              className="panel__input"
              value={edit.status}
              onChange={(event) => updateEdit({ status: event.target.value })}
            >
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
            </select>
          </label>
          {queryStatus ? <p className="panel__success">{queryStatus}</p> : null}
          {queries.length === 0 ? (
            <p className="panel__empty">No queries yet.</p>
          ) : (
            <ul className="panel__list">
              {queries.map((query) => (
                <li key={query.id}>
                  <div className="panel__meta">
                    <span>{query.query_text}</span>
                    <label className="panel__toggle">
                      <input
                        type="checkbox"
                        checked={query.enabled}
                        onChange={(event) =>
                          onQueryToggle(selectedBattery.id, query.id, event.target.checked)
                        }
                      />
                      <span>Enabled</span>
                    </label>
                    <button
                      type="button"
                      className="panel__action panel__action--ghost"
                      onClick={() => onQueryDelete(selectedBattery.id, query.id)}
                    >
                      Delete
                    </button>
                  </div>
                  <div className="panel__meta">
                    <span className="panel__muted">Weight</span>
                    <input
                      className="panel__input panel__input--inline"
                      type="number"
                      step="0.1"
                      min="0"
                      defaultValue={query.weight ?? 1}
                      onBlur={(event) =>
                        onQueryWeight(selectedBattery.id, query.id, Number(event.target.value))
                      }
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
          {metrics ? <BatteryMetricsSummary metrics={metrics} /> : null}
          <button
            type="button"
            className="panel__action panel__action--prominent"
            onClick={onUpdateBattery}
            disabled={isSubmitting}
          >
            Save battery details
          </button>
        </div>
      ) : (
        <p className="panel__empty">Select a battery to review details and query settings.</p>
      )}
    </details>
  );
}

function BatteryMetricsSummary({ metrics }: { metrics: QueryBatteryMetrics }) {
  return (
    <div className="panel__metrics">
      <p className="panel__muted">
        Total: {metrics.total_queries ?? 0} · Enabled: {metrics.enabled_queries ?? 0} · Unique:{" "}
        {metrics.unique_queries ?? 0}
      </p>
      <p className="panel__muted">
        Redundancy:{" "}
        {metrics.redundancy_rate !== undefined
          ? `${Number(metrics.redundancy_rate) * 100}%`
          : "—"}
      </p>
      <p className="panel__muted">
        Quality score: {metrics.quality_score !== undefined ? `${metrics.quality_score}/100` : "—"}
        {metrics.avg_words ? ` · Avg words: ${metrics.avg_words}` : ""}
      </p>
      {Array.isArray(metrics.quality_issues) && metrics.quality_issues.length > 0 ? (
        <ul className="panel__list panel__list--compact">
          {metrics.quality_issues.map((issue, index) => (
            <li key={`${issue}-${index}`}>{issue}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
