type ValidationStep = {
  id: number;
  label: string;
  done: boolean;
};

type ValidationNextAction = {
  label: string;
  helper: string;
};

type ValidationFlowHeaderProps = {
  currentStep: number;
  steps: ValidationStep[];
  nextAction: ValidationNextAction;
  winnerLabel: string;
  scoreText: string;
  evidenceText: string;
  observedLogged: number;
  observedVerified: number;
  observedAccuracyText: string;
  observedUnlockReady: boolean;
  hasSyntheticResult: boolean;
  onRunNextAction: () => void;
  onOpenExperiments: () => void;
};

export function ValidationFlowHeader({
  currentStep,
  steps,
  nextAction,
  winnerLabel,
  scoreText,
  evidenceText,
  observedLogged,
  observedVerified,
  observedAccuracyText,
  observedUnlockReady,
  hasSyntheticResult,
  onRunNextAction,
  onOpenExperiments,
}: ValidationFlowHeaderProps) {
  return (
    <section className="panel__card panel__card--primary">
      <div className="flow-rail">
        <div className="flow-rail__header">
          <h4>Validation Flow</h4>
          <span className="panel__muted">Current step: {currentStep} / 5</span>
        </div>
        <div className="flow-rail__steps">
          {steps.map((step) => (
            <div
              key={step.id}
              className={`flow-rail__step ${
                step.done ? "is-done" : step.id === currentStep ? "is-current" : ""
              }`}
            >
              <span className="flow-rail__index">{step.id}</span>
              <span className="flow-rail__label">{step.label}</span>
              <span className="flow-rail__status">
                {step.done ? "Done" : step.id === currentStep ? "Current" : "Pending"}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="panel__separator" />
      <section className="panel__notice panel__notice--info flow-next-action">
        <strong>Next recommended action:</strong> {nextAction.label}
        <p className="panel__muted">{nextAction.helper}</p>
        <div className="panel__actions panel__actions--priority">
          <button
            type="button"
            className="panel__action panel__action--prominent"
            onClick={onRunNextAction}
          >
            {nextAction.label}
          </button>
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={onOpenExperiments}
          >
            Open Experiments
          </button>
        </div>
      </section>
      <div className="panel__separator" />
      <section className="panel__notice panel__notice--info outcome-snapshot">
        <div className="panel__meta">
          <strong>Validation outcome summary</strong>
          <span className="panel__badge panel__badge--secondary">Unified view</span>
        </div>
        <div className="outcome-snapshot__grid">
          <div className="outcome-snapshot__item">
            <span className="outcome-snapshot__label">Synthetic winner</span>
            <span className="outcome-snapshot__value">{winnerLabel}</span>
            <span className="panel__muted">
              Score: {scoreText} · Evidence: {evidenceText}
            </span>
          </div>
          <div className="outcome-snapshot__item">
            <span className="outcome-snapshot__label">Observed signals</span>
            <span className="outcome-snapshot__value">
              {observedLogged} logged · {observedVerified} verified
            </span>
            <span className="panel__muted">Accuracy: {observedAccuracyText}</span>
          </div>
          <div className="outcome-snapshot__item">
            <span className="outcome-snapshot__label">Readiness</span>
            <span className="outcome-snapshot__value">
              {observedUnlockReady ? "Ready for next variant" : "Needs more validation"}
            </span>
            <span className="panel__muted">
              Synthetic: {hasSyntheticResult ? "available" : "pending"} · Observed:{" "}
              {observedLogged > 0 ? "available" : "pending"}
            </span>
          </div>
        </div>
      </section>
    </section>
  );
}
