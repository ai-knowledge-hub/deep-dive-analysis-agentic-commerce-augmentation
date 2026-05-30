"use client";

import React, { useMemo } from "react";
import type { AgentAction, AgentRun } from "../../lib/types";

type NextRecommendedAction = {
  action: AgentAction | null;
  guardrails: string[];
  hint: string;
};

type Guide = {
  title: string;
  summary: string;
  cta: string;
  tone: "attention" | "default";
  action: "approve" | "interventions" | "start" | "select";
};

type Props = {
  selectedRun: AgentRun | null;
  nextRecommendedAction: NextRecommendedAction;
  loading: boolean;
  onApprove: (actionId: string) => void;
  onOpenInterventions: () => void;
  onStart: () => void;
  onReviewAction: (actionId: string) => void;
};

function buildGuide(
  selectedRun: AgentRun | null,
  nextRecommendedAction: NextRecommendedAction,
): Guide {
  if (!selectedRun) {
    return {
      title: "Select a run",
      summary: "Choose the highest-priority run from the rail to see the next action.",
      cta: "Select a run",
      tone: "default",
      action: "select",
    };
  }

  if (nextRecommendedAction.action && nextRecommendedAction.guardrails.length > 0) {
    return {
      title: "Intervention needed",
      summary: nextRecommendedAction.guardrails[0],
      cta: "Open interventions",
      tone: "attention",
      action: "interventions",
    };
  }

  if (nextRecommendedAction.action) {
    return {
      title: "Approve the next action",
      summary:
        nextRecommendedAction.action.rationale ||
        "The next proposed action is ready for operator approval.",
      cta: "Approve next action",
      tone: "attention",
      action: "approve",
    };
  }

  return {
    title: "Continue supervision",
    summary: nextRecommendedAction.hint,
    cta: "Start or step run",
    tone: "default",
    action: "start",
  };
}

export function RunStartGuide({
  selectedRun,
  nextRecommendedAction,
  loading,
  onApprove,
  onOpenInterventions,
  onStart,
  onReviewAction,
}: Props) {
  const guide = useMemo(
    () => buildGuide(selectedRun, nextRecommendedAction),
    [nextRecommendedAction, selectedRun],
  );
  const recommendedActionId = nextRecommendedAction.action?.id ?? null;

  return (
    <section className="control-surface control-grid__full agent-start-guide">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Start here</span>
          <h3 className="control-section__title">{guide.title}</h3>
          <div className="control-section__summary">
            Runs keeps one operator decision above the execution detail.
          </div>
        </div>
        <span
          className={`control-chip ${
            guide.tone === "attention" ? "control-chip--attention" : ""
          }`}
        >
          {selectedRun?.status ?? "No run"}
        </span>
      </div>
      <div className="panel__notice panel__notice--info">{guide.summary}</div>
      <div className="panel__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={loading || !selectedRun || (guide.action === "approve" && !recommendedActionId)}
          onClick={() => {
            if (guide.action === "approve" && recommendedActionId) {
              onApprove(recommendedActionId);
            } else if (guide.action === "interventions") {
              onOpenInterventions();
            } else if (guide.action === "start") {
              onStart();
            }
          }}
        >
          {guide.cta}
        </button>
        {recommendedActionId ? (
          <button
            type="button"
            className="button button--ghost"
            onClick={() => onReviewAction(recommendedActionId)}
            disabled={loading}
          >
            Review action detail
          </button>
        ) : null}
      </div>
    </section>
  );
}
