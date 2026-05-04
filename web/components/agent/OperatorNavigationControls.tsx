import React from "react";
import type { AgentRun } from "../../lib/types";
import type { PromptId } from "./operatorChatTypes";

type Props = {
  run: AgentRun | null;
  proposedCount: number;
  policyCount: number;
  validationLinkedCount: number;
  onPrompt: (promptId: PromptId) => void;
  onOpenExperiment?: () => void;
  onOpenValidation?: () => void;
  onOpenInterventionsForRun?: () => void;
  onFocusFailures?: () => void;
  onFocusApprovals?: () => void;
  onFocusPolicy?: () => void;
  onFocusValidationLinked?: () => void;
};

export function OperatorNavigationControls({
  run,
  proposedCount,
  policyCount,
  validationLinkedCount,
  onPrompt,
  onOpenExperiment,
  onOpenValidation,
  onOpenInterventionsForRun,
  onFocusFailures,
  onFocusApprovals,
  onFocusPolicy,
  onFocusValidationLinked,
}: Props) {
  return (
    <div className="panel__actions">
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("open_context");
          onOpenExperiment?.();
        }}
        disabled={!run?.experiment_id}
      >
        Open experiment context
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("open_context");
          onOpenValidation?.();
        }}
        disabled={validationLinkedCount === 0}
      >
        Open validation
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("recommend_next");
          onOpenInterventionsForRun?.();
        }}
        disabled={!run}
      >
        Open interventions
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("summarize_failures");
          onFocusFailures?.();
        }}
        disabled={!run}
      >
        Focus failures
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("blocked_action");
          onFocusApprovals?.();
        }}
        disabled={proposedCount === 0}
      >
        Focus approvals
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("summarize_failures");
          onFocusPolicy?.();
        }}
        disabled={policyCount === 0}
      >
        Focus policy events
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("open_context");
          onFocusValidationLinked?.();
        }}
        disabled={validationLinkedCount === 0}
      >
        Focus validation-linked
      </button>
    </div>
  );
}
