"use client";

import React from "react";
import type { AgentAction } from "../../lib/types";
import type { PromptId } from "./OperatorConsoleChat.types";

type Props = {
  selectedAction: AgentAction | null;
  hasNextRecommendedAction: boolean;
  onSendPrompt: (promptId: PromptId) => void;
  onJumpToNextAction?: () => void;
};

export function OperatorPromptControls({
  selectedAction,
  hasNextRecommendedAction,
  onSendPrompt,
  onJumpToNextAction,
}: Props) {
  return (
    <div className="panel__actions">
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onSendPrompt("explain_run")}
      >
        Explain run
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onSendPrompt("summarize_failures")}
      >
        Summarize failures
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onSendPrompt("blocked_action")}
      >
        {selectedAction ? "Explain selected action" : "Explain blocked action"}
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => onSendPrompt("recommend_next")}
      >
        Recommend next step
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => {
          onSendPrompt("recommend_next");
          onJumpToNextAction?.();
        }}
        disabled={!hasNextRecommendedAction}
      >
        Jump to next action
      </button>
    </div>
  );
}
