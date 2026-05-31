"use client";

import React from "react";
import type { BrandBelief, ExperimentRun } from "../../lib/types";
import {
  FlowStatusPanel,
  type FlowStep,
  type LabLoopStep,
  type NextFlowActionView,
} from "./FlowStatusPanel";

type Props = {
  labMode: "lab" | "manual";
  selectedExperimentId: string | null;
  batteryLinked: boolean;
  variantCount: number;
  runCount: number;
  metricCount: number;
  beliefCount: number;
  labAutoRunEnabled: boolean;
  showManualControls: boolean;
  currentFlowStep: number;
  activeFlowSteps: FlowStep[];
  labLoopSteps: LabLoopStep[];
  lastRun: ExperimentRun | null;
  variantLabelById: Map<string, string>;
  latestBelief: BrandBelief | null;
  latestBeliefSummary: string;
  nextFlowAction: NextFlowActionView;
  showValidationCheckpoint: boolean;
  onLabAutoRunEnabledChange: (value: boolean) => void;
  onShowManualControlsChange: (value: boolean) => void;
  onSwitchToManual: () => void;
  onOpenBeliefsTimeline: () => void;
  onUseLatestBelief: () => void;
  onRunNextFlowAction: () => void;
  onOpenValidation: () => void;
};

export function LabLoopPanel({
  labMode,
  selectedExperimentId,
  batteryLinked,
  variantCount,
  runCount,
  metricCount,
  beliefCount,
  labAutoRunEnabled,
  showManualControls,
  currentFlowStep,
  activeFlowSteps,
  labLoopSteps,
  lastRun,
  variantLabelById,
  latestBelief,
  latestBeliefSummary,
  nextFlowAction,
  showValidationCheckpoint,
  onLabAutoRunEnabledChange,
  onShowManualControlsChange,
  onSwitchToManual,
  onOpenBeliefsTimeline,
  onUseLatestBelief,
  onRunNextFlowAction,
  onOpenValidation,
}: Props) {
  return (
    <section className="panel__card panel__card--primary lab-loop">
      <div className="panel__header">
        <h3>Lab Loop</h3>
        <div className="lab-loop__badges">
          <span className="panel__badge">{labMode === "lab" ? "Lab mode" : "Manual mode"}</span>
          {selectedExperimentId ? (
            <span className="panel__badge panel__badge--secondary">Experiment active</span>
          ) : null}
          {batteryLinked ? (
            <span className="panel__badge panel__badge--secondary">Battery linked</span>
          ) : null}
        </div>
      </div>
      <p className="lab-loop__meta">
        {variantCount} variants · {runCount} runs · {metricCount} metrics · {beliefCount} beliefs
      </p>
      <p className="lab-loop__hint">
        The lab loop turns test ideas into evidence and updates brand beliefs with every run.
      </p>
      {labMode === "lab" ? (
        <section className="panel__notice panel__notice--info lab-contract">
          <strong>Lab mode contract:</strong> Automation handles the default path (battery,
          queries, baseline/test-idea variants, and optional auto-run).
          <div className="panel__actions">
            <label className="panel__toggle">
              <input
                type="checkbox"
                checked={labAutoRunEnabled}
                onChange={(event) => onLabAutoRunEnabledChange(event.target.checked)}
              />
              <span>Auto-run baseline + test idea after experiment creation</span>
            </label>
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={() => onShowManualControlsChange(!showManualControls)}
            >
              {showManualControls ? "Hide manual controls" : "Show manual controls"}
            </button>
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onSwitchToManual}
            >
              Switch to Manual for this experiment
            </button>
          </div>
        </section>
      ) : null}
      <FlowStatusPanel
        labMode={labMode}
        currentFlowStep={currentFlowStep}
        activeFlowSteps={activeFlowSteps}
        labLoopSteps={labLoopSteps}
        lastRun={lastRun}
        variantLabelById={variantLabelById}
        latestBelief={latestBelief}
        latestBeliefSummary={latestBeliefSummary}
        nextFlowAction={nextFlowAction}
        showValidationCheckpoint={showValidationCheckpoint}
        onOpenBeliefsTimeline={onOpenBeliefsTimeline}
        onUseLatestBelief={onUseLatestBelief}
        onRunNextFlowAction={onRunNextFlowAction}
        onOpenValidation={onOpenValidation}
      />
    </section>
  );
}
