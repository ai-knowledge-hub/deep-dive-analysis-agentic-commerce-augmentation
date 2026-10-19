import React from "react";
import {
  steps,
  type Conversation,
  type Decision,
  type Inspector,
} from "./model";
import { PreviewIcon, ScoutMark } from "./PreviewIcons";
export function PreviewInspector({
  panel,
  work,
  close,
  mobile,
  inert,
}: {
  panel: Inspector;
  work: Conversation;
  close: () => void;
  mobile: boolean;
  inert: boolean;
}) {
  if (!panel) return null;
  const titles = {
    plan: "The agreed work",
    evidence: "Comparison evidence",
    assistant: "Meet Scout",
    setup: "Experiment setup",
  };
  return (
    <aside
      className="preview-inspector"
      aria-label={titles[panel]}
      role={mobile ? "dialog" : undefined}
      aria-modal={mobile ? true : undefined}
      {...(inert ? { inert: "" } : {})}
      tabIndex={-1}
    >
      <header>
        <span>{titles[panel]}</span>
        <button
          className="preview-icon-button"
          onClick={close}
          aria-label="Close details"
        >
          <PreviewIcon name="close" />
        </button>
      </header>
      <div className="preview-inspector-content">
        {panel === "assistant" && (
          <>
            <ScoutMark />
            <h2>
              A little context.
              <br />A clear next step.
            </h2>
            <p>
              Scout helps you compare and evaluate existing product experiments.
            </p>
            <dl>
              <dt>Supported work</dt>
              <dd>
                One experiment, one candidate comparison, validation and a
                recommendation.
              </dd>
              <dt>Your decisions</dt>
              <dd>
                Create the run, then approve or reject each individual step.
              </dd>
              <dt>Identity</dt>
              <dd>
                A commerce assistant presented as one role. This preview adds no
                independent agent memory or cloud computer.
              </dd>
            </dl>
          </>
        )}
        {panel === "plan" && (
          <>
            <p className="preview-eyebrow">Autumn comparison · Trail shoe</p>
            <h2>
              Nine steps.
              <br />
              One bounded experiment.
            </h2>
            <p>
              Every step needs its own approval. Completed steps in this preview
              are illustrative records.
            </p>
            <ol className="preview-step-list">
              {steps.map((step, index) => (
                <li key={step.label}>
                  <span className={index < work.completed ? "is-complete" : ""}>
                    {index < work.completed ? (
                      <PreviewIcon name="check" />
                    ) : (
                      String(index + 1).padStart(2, "0")
                    )}
                  </span>
                  <div>
                    <strong>{step.label}</strong>
                    <small>
                      {index < work.completed
                        ? "Approved and finished · sample record"
                        : index === work.completed && work.activeStep
                          ? "Approved · result pending"
                          : "Not executed"}
                    </small>
                  </div>
                </li>
              ))}
            </ol>
            <div className="preview-inspector-note">
              <strong>Recorded decision</strong>
              <p>
                Creation grants no action approval. The example limit is one
                candidate evaluation, 12 actions and $5 recorded cost; recorded
                cost is not a billing guarantee.
              </p>
            </div>
          </>
        )}
        {panel === "evidence" && (
          <>
            <p className="preview-eyebrow">
              Sample evidence · captured 14 Oct 2026
            </p>
            <h2>
              The comparison,
              <br />
              with its limits.
            </h2>
            <div className="preview-evidence-record">
              <span>01 · Fixed comparison inputs</span>
              <strong>
                {work.completed >= 1
                  ? "Same questions. Same conditions."
                  : "Comparison inputs not yet frozen"}
              </strong>
              <p>
                {work.completed >= 1
                  ? "The control and candidate use the same recorded example query set."
                  : "A query set is planned. No frozen inputs are recorded for this sample run yet."}
              </p>
            </div>
            <div className="preview-evidence-record">
              <span>02 · Candidate description</span>
              <strong>
                {work.completed >= 4
                  ? "Make the use case clearer."
                  : "Candidate not yet prepared"}
              </strong>
              {work.completed >= 4 ? (
                <>
                  <blockquote>
                    Grip and comfort for everyday day hikes.
                  </blockquote>
                  <p>
                    A candidate inside the experiment. No live description has
                    been published.
                  </p>
                </>
              ) : (
                <p>
                  Candidate text becomes available after its preparation step
                  finishes.
                </p>
              )}
            </div>
            <div className="preview-evidence-record">
              <span>03 · Synthetic validation</span>
              <strong>
                {["failed", "partial"].includes(work.scene)
                  ? "An outcome remains unresolved"
                  : work.scene === "outcome"
                    ? "Illustrative completed result"
                    : "Result not yet established"}
              </strong>
              <p>
                {work.scene === "outcome"
                  ? "Model-generated comparison evidence, not observed customer behaviour."
                  : "This view cannot establish validation success from a pending or unknown result."}
              </p>
            </div>
            <div className="preview-inspector-note">
              <strong>What this does not establish</strong>
              <p>
                Customer conversion, commercial uplift and performance in the
                real world have not been measured.
              </p>
            </div>
          </>
        )}
        {panel === "setup" && (
          <>
            <p className="preview-eyebrow">Before creating work</p>
            <h2>
              A fair baseline
              <br />
              comes first.
            </h2>
            <p>
              The selected experiment requires a control variant and an enabled
              query battery with at most 100 queries.
            </p>
            <p>
              Preparation and confirmation both recheck these prerequisites.
              This preview cannot edit live setup.
            </p>
            <a className="preview-secondary" href="/lab">
              Open advanced workspace <PreviewIcon name="chevron" />
            </a>
          </>
        )}
      </div>
    </aside>
  );
}
const decisionCopy = {
  approve: {
    title: "Approve this step?",
    action: "Confirm approval",
    body: "This authorises one step in the reviewed experiment. Execution and its result are separate. No live product content is published.",
  },
  reject: {
    title: "Reject this step?",
    action: "Confirm rejection",
    body: "The proposed step will not execute. Remaining work may stay unresolved; rejection is not a completed business outcome.",
  },
  pause: {
    title: "Pause further work?",
    action: "Confirm pause",
    body: "This stops scheduling further work. A started step may still finish. Completed work and its evidence remain available.",
  },
  resume: {
    title: "Resume this run?",
    action: "Confirm resume",
    body: "Continue only within the existing plan and limits. Resuming gives no new step approval and does not resolve unknown effects.",
  },
  cancel: {
    title: "Cancel this run?",
    action: "Confirm cancellation",
    body: "This ends a settled run. It cannot be resumed, and cancellation reverses no completed effects. Continuing requires a separately reviewed new run.",
  },
};
export function PreviewDecision({
  decision,
  work,
  close,
  confirm,
}: {
  decision: Decision;
  work: Conversation;
  close: () => void;
  confirm: () => void;
}) {
  if (!decision) return null;
  const copy = decisionCopy[decision];
  return (
    <div className="preview-modal-backdrop">
      <section
        className="preview-decision-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="preview-decision-title"
        tabIndex={-1}
      >
        <p className="preview-eyebrow">Review your decision · sample work</p>
        <h2 id="preview-decision-title">{copy.title}</h2>
        {decision === "approve" && (
          <strong>{steps[work.completed]?.label}</strong>
        )}
        <p>{copy.body}</p>
        <div className="preview-decision-target">
          Trail shoe <span>·</span> Autumn comparison
        </div>
        <p className="preview-note">
          Design preview: confirmation changes sample state only. No command or
          provider call is sent.
        </p>
        <div className="preview-artifact-actions">
          <button className="preview-primary" onClick={confirm}>
            {copy.action}
          </button>
          <button className="preview-text-button" onClick={close}>
            Go back
          </button>
        </div>
      </section>
    </div>
  );
}
