import type { BrandBelief, ExperimentRun } from "../../lib/types";

export type FlowStep = {
  id: number;
  label: string;
  done: boolean;
};

export type LabLoopStep = {
  label: string;
  status: string;
  tone: string;
};

export type NextFlowActionView = {
  label: string;
  helper: string;
};

type FlowStatusPanelProps = {
  labMode: "lab" | "manual";
  currentFlowStep: number;
  activeFlowSteps: FlowStep[];
  labLoopSteps: LabLoopStep[];
  lastRun: ExperimentRun | null;
  latestBelief: BrandBelief | null;
  latestBeliefSummary: string;
  nextFlowAction: NextFlowActionView;
  showValidationCheckpoint: boolean;
  onOpenBeliefsTimeline: () => void;
  onUseLatestBelief: () => void;
  onRunNextFlowAction: () => void;
  onOpenValidation: () => void;
};

export function FlowStatusPanel({
  labMode,
  currentFlowStep,
  activeFlowSteps,
  labLoopSteps,
  lastRun,
  latestBelief,
  latestBeliefSummary,
  nextFlowAction,
  showValidationCheckpoint,
  onOpenBeliefsTimeline,
  onUseLatestBelief,
  onRunNextFlowAction,
  onOpenValidation,
}: FlowStatusPanelProps) {
  return (
    <>
      <div className="flow-rail">
        <div className="flow-rail__header">
          <h4>{labMode === "lab" ? "Lab Flow" : "Experiment Flow"}</h4>
          <span className="panel__muted">Current step: {currentFlowStep} / 8</span>
        </div>
        <div className="flow-rail__steps">
          {activeFlowSteps.map((step) => (
            <div
              key={step.id}
              className={`flow-rail__step ${
                step.done ? "is-done" : step.id === currentFlowStep ? "is-current" : ""
              }`}
            >
              <span className="flow-rail__index">{step.id}</span>
              <span className="flow-rail__label">{step.label}</span>
              <span className="flow-rail__status">
                {step.done ? "Done" : step.id === currentFlowStep ? "Current" : "Pending"}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="lab-loop__steps">
        {labLoopSteps.map((step) => (
          <div key={step.label} className="lab-loop__step">
            <span className={`lab-loop__status lab-loop__status--${step.tone}`}>
              {step.status}
            </span>
            <span className="lab-loop__label">{step.label}</span>
          </div>
        ))}
      </div>
      <div className="lab-loop__summary">
        <div className="lab-loop__summary-card">
          <div className="lab-loop__summary-title">Last run</div>
          <div className="lab-loop__summary-value">
            {lastRun?.created_at
              ? new Date(lastRun.created_at).toLocaleString()
              : "No runs yet"}
          </div>
          <div className="lab-loop__summary-meta">
            {lastRun?.variant_id ? `Variant: ${lastRun.variant_id}` : "Run a variant to start"}
          </div>
        </div>
        <div className="lab-loop__summary-card">
          <div className="lab-loop__summary-title">Last belief</div>
          <div className="lab-loop__summary-value">
            {latestBelief?.created_at
              ? new Date(latestBelief.created_at).toLocaleString()
              : "No beliefs yet"}
          </div>
          <button
            type="button"
            className="lab-loop__summary-meta lab-loop__summary-link"
            onClick={onOpenBeliefsTimeline}
            disabled={!latestBelief}
          >
            {latestBeliefSummary}
          </button>
          <div className="lab-loop__summary-actions">
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onOpenBeliefsTimeline}
              disabled={!latestBelief}
            >
              View timeline
            </button>
            <button
              type="button"
              className="panel__action panel__action--ghost"
              onClick={onUseLatestBelief}
              disabled={!latestBelief}
            >
              Use latest belief
            </button>
          </div>
        </div>
      </div>
      <section className="panel__notice panel__notice--info flow-next-action">
        <strong>Next recommended action:</strong> {nextFlowAction.label}
        <p className="panel__muted">{nextFlowAction.helper}</p>
        <div className="panel__actions panel__actions--priority">
          <button
            type="button"
            className="panel__action panel__action--prominent"
            onClick={onRunNextFlowAction}
          >
            {nextFlowAction.label}
          </button>
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={onOpenValidation}
          >
            Open Validation
          </button>
        </div>
      </section>
      {showValidationCheckpoint ? (
        <section className="panel__notice panel__notice--warning lab-checkpoint">
          <strong>Validation checkpoint (Step 7):</strong> Runs exist, but no
          validation evidence is logged yet.
          <p className="panel__muted">
            Complete synthetic and/or observed validation before trusting automated
            iteration decisions.
          </p>
          <div className="panel__actions panel__actions--priority">
            <button
              type="button"
              className="panel__action panel__action--prominent"
              onClick={onOpenValidation}
            >
              Go to Validation (Step 7)
            </button>
          </div>
        </section>
      ) : null}
    </>
  );
}
