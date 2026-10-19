import React from "react";
import {
  attention,
  steps,
  type Conversation,
  type Decision,
  type Inspector,
} from "./model";
import { PreviewIcon, ScoutMark } from "./PreviewIcons";

type Props = {
  work: Conversation;
  inspect: (panel: Inspector) => void;
  decide: (decision: Decision) => void;
  create: () => void;
  choose: () => void;
};
export function PreviewArtifacts({
  work,
  inspect,
  decide,
  create,
  choose,
}: Props) {
  if (work.scene === "start") return null;
  if (work.scene === "clarification")
    return (
      <section className="preview-artifact" aria-label="Choose experiment">
        <p className="preview-eyebrow">One detail before we start</p>
        <h2>Which comparison should I use?</h2>
        <p>Choose the existing experiment for this product.</p>
        <button className="preview-scope-option" onClick={choose}>
          <span>
            <strong>Trail shoe · autumn comparison</strong>
            <small>One product · control baseline available</small>
          </span>
          <PreviewIcon name="chevron" />
        </button>
      </section>
    );
  if (work.scene === "plan")
    return (
      <section
        className="preview-artifact preview-plan"
        aria-label="Review plan"
      >
        <p className="preview-eyebrow">Proposed work</p>
        <h2>A fair comparison, then a recommendation.</h2>
        <p>
          Compare one candidate description with the control in your existing
          experiment.
        </p>
        <div className="preview-scope">
          <span>
            PRODUCT<strong>Trail shoe</strong>
          </span>
          <span>
            EXPERIMENT<strong>Autumn comparison</strong>
          </span>
        </div>
        <ol className="preview-plan-outline">
          <li>
            <span>01</span>Establish the baseline
          </li>
          <li>
            <span>02</span>Prepare and evaluate one candidate
          </li>
          <li>
            <span>03</span>Validate and recommend
          </li>
        </ol>
        <div className="preview-limits">
          One candidate evaluation <span>·</span> 12-action limit <span>·</span>{" "}
          $5 recorded-cost limit
        </div>
        <p className="preview-note">
          Creating a run approves no step. You’ll review each of the nine steps
          before it can execute.
        </p>
        <div className="preview-artifact-actions">
          <button className="preview-primary" onClick={create}>
            Confirm and create run <PreviewIcon name="chevron" />
          </button>
          <button
            className="preview-text-button"
            onClick={() => inspect("plan")}
          >
            View all nine steps
          </button>
        </div>
      </section>
    );
  if (work.scene === "outcome") return <PreviewOutcome inspect={inspect} />;
  if (["blocked", "failed", "partial", "cancelled"].includes(work.scene))
    return <PreviewInterruption work={work} inspect={inspect} />;
  const step = steps[work.completed];
  return (
    <>
      <div className="preview-progress" role="status">
        <span
          className={`preview-status-dot ${work.scene === "running" ? "is-working" : ""}`}
        />
        <strong>{attention(work)}</strong>
        <span>{work.completed} of 9 steps finished</span>
        <button className="preview-text-button" onClick={() => inspect("plan")}>
          View progress
        </button>
      </div>
      {work.scene === "approval" && step && (
        <section
          className="preview-artifact preview-approval"
          aria-label="Action review"
        >
          <p className="preview-eyebrow">
            Your decision · step {work.completed + 1} of 9
          </p>
          <h2>{step.label}</h2>
          <p>{step.detail}</p>
          <div className="preview-action-target">
            <PreviewIcon name="check" />
            <span>Trail shoe · Autumn comparison</span>
          </div>
          <p className="preview-note">
            Approval allows this step to start. It does not mean the step has
            executed, and it publishes nothing to your live product page.
          </p>
          <div className="preview-artifact-actions">
            <button
              className="preview-primary"
              onClick={() => decide("approve")}
            >
              Review approval <PreviewIcon name="chevron" />
            </button>
            <button
              className="preview-text-button"
              onClick={() => decide("reject")}
            >
              Reject this step
            </button>
            <button
              className="preview-text-button"
              onClick={() => inspect("evidence")}
            >
              Supporting evidence
            </button>
          </div>
        </section>
      )}
      {work.scene === "running" && (
        <div className="preview-running">
          <ScoutMark small />
          <div>
            <strong>{step?.label}</strong>
            <p>
              This sample step has been approved. Its result is still pending.
            </p>
          </div>
        </div>
      )}
      {work.scene === "paused" && (
        <section className="preview-artifact">
          <p className="preview-eyebrow">Paused</p>
          <h2>Pick up when you’re ready.</h2>
          <p>
            {work.activeStep
              ? "Further scheduling is paused. The started step may still finish."
              : "Completed work and its evidence are retained. Resuming grants no new action approval."}
          </p>
          <button className="preview-primary" onClick={() => decide("resume")}>
            Review resume <PreviewIcon name="chevron" />
          </button>
        </section>
      )}
      <div className="preview-control-row">
        {work.scene !== "paused" && (
          <button onClick={() => decide("pause")}>
            <PreviewIcon name="pause" />
            Pause further work
          </button>
        )}
        <button
          disabled={work.activeStep}
          title={
            work.activeStep
              ? "Wait for the current step to settle before cancelling"
              : undefined
          }
          onClick={() => decide("cancel")}
        >
          Cancel run
        </button>
        {work.activeStep && (
          <small>Cancellation is available when work has settled.</small>
        )}
      </div>
    </>
  );
}
function PreviewInterruption({
  work,
  inspect,
}: Pick<Props, "work" | "inspect">) {
  const copy = {
    blocked: {
      label: "Setup needed",
      title: "This experiment needs a control.",
      body: "A control variant and enabled query set are required before a comparison can be created.",
      action: "View setup requirements",
      panel: "setup" as const,
    },
    failed: {
      label: "Needs investigation",
      title: "The validation outcome is unknown.",
      body: "Earlier work is retained. Check the started validation step’s evidence before attempting another provider call.",
      action: "Inspect validation evidence",
      panel: "evidence" as const,
    },
    partial: {
      label: "Unresolved work",
      title: "There’s useful evidence, but no final outcome.",
      body: `${work.completed} of nine steps finished. Remaining work needs review; this is not a completed recommendation.`,
      action: "Review available evidence",
      panel: "evidence" as const,
    },
    cancelled: {
      label: "Cancelled",
      title: "This run has ended.",
      body: "Recorded work remains available. Cancellation reverses no effects; continuing requires a separately reviewed new run.",
      action: "Inspect recorded work",
      panel: "plan" as const,
    },
  };
  const state = copy[work.scene as keyof typeof copy];
  return (
    <section
      className="preview-artifact preview-interruption"
      aria-label={state.label}
    >
      <p className="preview-eyebrow">{state.label}</p>
      <h2>{state.title}</h2>
      <p>{state.body}</p>
      <button className="preview-primary" onClick={() => inspect(state.panel)}>
        {state.action}
        <PreviewIcon name="chevron" />
      </button>
    </section>
  );
}
export function PreviewOutcome({ inspect }: Pick<Props, "inspect">) {
  return (
    <section
      className="preview-artifact preview-outcome"
      aria-label="Comparison result"
    >
      <p className="preview-eyebrow">
        <PreviewIcon name="check" />
        Comparison finished · sample result
      </p>
      <h2>A clearer description is worth testing.</h2>
      <p>
        The candidate was selected more often in this sample experiment. Keep
        the recommendation separate from changes to your live product.
      </p>
      <div className="preview-comparison" aria-label="Sample selection rates">
        <div>
          <span>Control</span>
          <strong>
            54<span>%</span>
          </strong>
          <div className="preview-meter">
            <span style={{ width: "54%" }} />
          </div>
        </div>
        <div>
          <span>Candidate</span>
          <strong>
            67<span>%</span>
          </strong>
          <div className="preview-meter preview-meter--candidate">
            <span style={{ width: "67%" }} />
          </div>
        </div>
      </div>
      <p className="preview-chart-caption">
        Share of sample comparison answers selecting the product. These are
        illustrative values, not customer conversion measurements.
      </p>
      <div className="preview-result-facts">
        <p>
          <PreviewIcon name="check" />
          Nine sample steps finished with individual approvals.
        </p>
        <p>
          <PreviewIcon name="check" />
          Synthetic validation is represented in the sample evidence.
        </p>
        <p>
          <span className="preview-empty-dot" />
          Real customer impact has not been measured.
        </p>
      </div>
      <div className="preview-artifact-actions">
        <button className="preview-primary" onClick={() => inspect("evidence")}>
          Open comparison <PreviewIcon name="chevron" />
        </button>
        <button className="preview-text-button" onClick={() => inspect("plan")}>
          Review recorded work
        </button>
      </div>
    </section>
  );
}
