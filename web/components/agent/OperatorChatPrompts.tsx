import React from "react";
import type { AgentAction } from "../../lib/types";
import type { PromptId } from "./operatorChatTypes";

type Props = {
  selectedAction: AgentAction | null;
  hasNextAction: boolean;
  onPrompt: (promptId: PromptId) => void;
  onJumpToNextAction?: () => void;
};

export function OperatorChatPrompts({
  selectedAction,
  hasNextAction,
  onPrompt,
  onJumpToNextAction,
}: Props) {
  return (
    <div className="panel__actions">
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onPrompt("explain_run")}
      >
        Explain run
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onPrompt("summarize_failures")}
      >
        Summarize failures
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onPrompt("blocked_action")}
      >
        {selectedAction ? "Explain selected action" : "Explain blocked action"}
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onPrompt("recommend_next")}
      >
        Recommend next step
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onPrompt("recommend_next");
          onJumpToNextAction?.();
        }}
        disabled={!hasNextAction}
      >
        Jump to next action
      </button>
    </div>
  );
}
