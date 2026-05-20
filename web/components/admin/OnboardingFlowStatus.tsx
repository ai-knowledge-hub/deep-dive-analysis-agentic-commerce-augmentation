export type OnboardingStep = {
  id: number;
  label: string;
  done: boolean;
};

export type OnboardingNextAction = {
  label: string;
  helper: string;
  action: "client" | "brand" | "product" | "intent" | "complete";
};

type OnboardingFlowStatusProps = {
  currentStep: number;
  steps: OnboardingStep[];
  nextAction: OnboardingNextAction;
  onRunNextAction: () => void;
};

export function OnboardingFlowStatus({
  currentStep,
  steps,
  nextAction,
  onRunNextAction,
}: OnboardingFlowStatusProps) {
  return (
    <>
      <section className="flow-rail admin-flow-rail">
        <div className="flow-rail__header">
          <h4>Onboarding steps</h4>
          <span className="panel__muted">
            Current step: {currentStep} / {steps.length}
          </span>
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
      </section>
      <section className="panel__notice panel__notice--info admin-next-action">
        <strong>Next recommended action:</strong> {nextAction.label}
        <p className="panel__muted">{nextAction.helper}</p>
        <div className="panel__actions panel__actions--priority">
          <button
            type="button"
            className="panel__action panel__action--prominent"
            onClick={onRunNextAction}
            disabled={nextAction.action === "complete"}
          >
            {nextAction.label}
          </button>
        </div>
      </section>
    </>
  );
}
