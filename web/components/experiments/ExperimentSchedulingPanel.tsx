"use client";

import React from "react";
import type { Experiment } from "../../lib/types";

export type ExperimentScheduleForm = {
  enabled: boolean;
  intervalMinutes: string;
};

type Props = {
  selectedExperiment: Experiment | null;
  scheduleForm: ExperimentScheduleForm;
  scheduleStatus: string | null;
  onScheduleFormChange: (form: ExperimentScheduleForm) => void;
  onScheduleSave: () => void;
  onBackfill: () => void;
};

export function ExperimentSchedulingPanel({
  selectedExperiment,
  scheduleForm,
  scheduleStatus,
  onScheduleFormChange,
  onScheduleSave,
  onBackfill,
}: Props) {
  const updateScheduleForm = (patch: Partial<ExperimentScheduleForm>) => {
    onScheduleFormChange({ ...scheduleForm, ...patch });
  };

  return (
    <section className="panel__card panel__card--secondary panel__card--full-row">
      <div className="panel__header">
        <h3>Scheduling</h3>
      </div>
      <p className="panel__subheading">Operational scheduling</p>
      <p className="panel__step-helper">
        Configure recurring reruns and backfills after the main experiment cycle is set.
      </p>
      {selectedExperiment ? (
        <div className="panel__form">
          {scheduleStatus ? <p className="panel__success">{scheduleStatus}</p> : null}
          <label className="panel__label">
            Enable schedule
            <input
              type="checkbox"
              checked={scheduleForm.enabled}
              onChange={(event) => updateScheduleForm({ enabled: event.target.checked })}
            />
          </label>
          <label className="panel__label">
            Interval (minutes)
            <input
              className="panel__input"
              type="number"
              min={15}
              step={15}
              value={scheduleForm.intervalMinutes}
              onChange={(event) => updateScheduleForm({ intervalMinutes: event.target.value })}
              disabled={!scheduleForm.enabled}
            />
          </label>
          <div className="panel__meta">
            <span className="panel__muted">
              Last run:{" "}
              {selectedExperiment.last_run_at
                ? new Date(selectedExperiment.last_run_at).toLocaleString()
                : "—"}
            </span>
            <span className="panel__muted">
              Next run:{" "}
              {selectedExperiment.next_run_at
                ? new Date(selectedExperiment.next_run_at).toLocaleString()
                : "—"}
            </span>
          </div>
          <div className="panel__actions">
            <button
              type="button"
              className="panel__action panel__action--prominent product__tooltip tooltip--below"
              data-tooltip="Save interval settings and schedule future due runs."
              onClick={onScheduleSave}
            >
              Save schedule
            </button>
            <button
              type="button"
              className="panel__action panel__action--ghost product__tooltip tooltip--below"
              data-tooltip="Run all variants now and refresh last/next run timestamps."
              onClick={onBackfill}
            >
              Backfill schedule
            </button>
          </div>
        </div>
      ) : (
        <p className="panel__empty">Select an experiment to schedule reruns.</p>
      )}
    </section>
  );
}
