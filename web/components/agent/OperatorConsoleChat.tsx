"use client";

import React from "react";
import { useMemo, useState } from "react";
import type { AgentAction, AgentRun, AgentRunEvent } from "../../lib/types";

type PromptId =
  | "brief"
  | "explain_run"
  | "summarize_failures"
  | "blocked_action"
  | "recommend_next"
  | "open_context";

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

type Props = {
  run: AgentRun | null;
  actions: AgentAction[];
  events: AgentRunEvent[];
  selectedAction: AgentAction | null;
  nextRecommendedAction: {
    action: AgentAction | null;
    guardrails: string[];
    hint: string;
  };
  onOpenExperiment?: () => void;
  onOpenValidation?: () => void;
  onFocusFailures?: () => void;
};

function formatRunLabel(run: AgentRun | null): string {
  if (!run) return "No run selected";
  return run.experiment_id
    ? `Run for experiment ${run.experiment_id.slice(0, 8)}`
    : `Run ${run.id.slice(0, 8)}`;
}

function formatPromptLabel(promptId: PromptId): string {
  switch (promptId) {
    case "brief":
      return "What needs attention?";
    case "explain_run":
      return "Explain this run";
    case "summarize_failures":
      return "Summarize failures";
    case "blocked_action":
      return "Why is this blocked?";
    case "recommend_next":
      return "What should we do next?";
    case "open_context":
      return "Open related context";
  }
}

export function OperatorConsoleChat({
  run,
  actions,
  events,
  selectedAction,
  nextRecommendedAction,
  onOpenExperiment,
  onOpenValidation,
  onFocusFailures,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const derived = useMemo(() => {
    const failedActions = actions.filter(
      (item) => String(item.status || "").toLowerCase() === "failed",
    );
    const blockedProposed = actions.filter(
      (item) => String(item.status || "").toLowerCase() === "proposed",
    ).length;
    const policyEvents = events.filter((item) => Boolean(item.is_policy_event));
    return {
      failedActions,
      blockedProposed,
      policyEvents,
    };
  }, [actions, events]);

  const briefing = useMemo(() => {
    if (!run) {
      return "Select a run to get a guided briefing. I can then explain failures, blocked actions, and the safest next step.";
    }
    const parts = [
      `${formatRunLabel(run)} is ${run.status ?? "unknown"} in ${run.state ?? "unknown"} state.`,
    ];
    if (derived.failedActions.length > 0) {
      parts.push(`${derived.failedActions.length} action failure${derived.failedActions.length === 1 ? "" : "s"} need review.`);
    }
    if (nextRecommendedAction.action) {
      parts.push(
        `Next suggested step is ${nextRecommendedAction.action.capability_name}.`,
      );
    }
    if (derived.policyEvents.length > 0) {
      parts.push(`${derived.policyEvents.length} policy event${derived.policyEvents.length === 1 ? "" : "s"} are on the timeline.`);
    }
    return parts.join(" ");
  }, [derived.failedActions.length, derived.policyEvents.length, nextRecommendedAction.action, run]);

  function buildAssistantResponse(promptId: PromptId): string {
    if (!run) {
      return "No run is selected yet. Pick a run from the rail and I’ll walk you through its state, outputs, and risks.";
    }
    switch (promptId) {
      case "brief":
        return briefing;
      case "explain_run":
        return [
          `${formatRunLabel(run)} is currently ${run.status ?? "unknown"} and has progressed to ${run.state ?? "unknown"}.`,
          `This run has ${actions.length} recorded action${actions.length === 1 ? "" : "s"} and ${events.length} timeline event${events.length === 1 ? "" : "s"}.`,
          run.run_mode === "plan_only"
            ? "It is still in plan-only mode, so approvals can be prepared but step execution is intentionally blocked."
            : "It is in an executable mode, so approved actions can continue through stepwise runtime execution.",
        ].join(" ");
      case "summarize_failures":
        if (derived.failedActions.length === 0) {
          return "There are no failed actions on this run right now. The main focus should be proposed actions and policy state.";
        }
        return `There are ${derived.failedActions.length} failed action${derived.failedActions.length === 1 ? "" : "s"}. Most recent failures are ${derived.failedActions
          .slice(0, 3)
          .map((item) => item.capability_name)
          .join(", ")}. Use the timeline filter to focus on failed or policy events before retrying anything.`;
      case "blocked_action":
        if (!selectedAction) {
          return "No action is selected. Click an action in the queue and I’ll explain its rationale, guardrails, and linked artifacts.";
        }
        if (String(selectedAction.status || "").toLowerCase() !== "proposed") {
          return `${selectedAction.capability_name} is currently ${selectedAction.status}. It is not blocked in the proposal stage anymore, so the next question is whether its output is safe and complete.`;
        }
        if (nextRecommendedAction.guardrails.length === 0) {
          return `${selectedAction.capability_name} is proposed and not currently blocked by a budget guardrail. If you approve it, the run can continue according to its current execution mode.`;
        }
        return `${selectedAction.capability_name} is being held by guardrails. Main reason: ${nextRecommendedAction.guardrails[0]}. Review budget and policy state before approving.`;
      case "recommend_next":
        if (!nextRecommendedAction.action) {
          return nextRecommendedAction.hint;
        }
        return [
          `Recommended next step is ${nextRecommendedAction.action.capability_name}.`,
          nextRecommendedAction.hint,
          nextRecommendedAction.action.rationale
            ? `Reasoning: ${nextRecommendedAction.action.rationale}`
            : "",
        ]
          .filter(Boolean)
          .join(" ");
      case "open_context":
        if (run.experiment_id) {
          return "The most useful related context for this run is the linked experiment. You can open the experiment workspace or filter the timeline to failures and policy events first.";
        }
        if (actions.some((item) => item.validation_job_id)) {
          return "This run has validation-linked actions. Opening the validation workspace is the best next context jump.";
        }
        return "The best context jump here is usually the failure-focused timeline, because that is where the operator can understand what changed and what is blocked.";
    }
  }

  function sendPrompt(promptId: PromptId) {
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}-${promptId}`,
      role: "user",
      content: formatPromptLabel(promptId),
    };
    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}-${promptId}`,
      role: "assistant",
      content: buildAssistantResponse(promptId),
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
  }

  return (
    <section className="panel__card panel__card--secondary">
      <div className="panel__header">
        <div className="panel__meta panel__meta--stack">
          <h3>Operator chat</h3>
          <div className="panel__subtitle">
            Chat-led guidance over the selected execution workspace.
          </div>
        </div>
        <span className="panel__badge panel__badge--secondary">
          {run ? "Context aware" : "Awaiting run"}
        </span>
      </div>

      <div className="panel__notice panel__notice--info">{briefing}</div>

      <div className="panel__actions">
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => sendPrompt("explain_run")}
        >
          Explain run
        </button>
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => sendPrompt("summarize_failures")}
        >
          Summarize failures
        </button>
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => sendPrompt("blocked_action")}
        >
          Explain blocked action
        </button>
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => sendPrompt("recommend_next")}
        >
          Recommend next step
        </button>
      </div>

      <div className="operator-chat__thread">
        {messages.length === 0 ? (
          <div className="panel__muted">
            Ask through the quick prompts first. This first slice focuses on explain,
            summarize, navigate, and recommendation flows.
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`operator-chat__message operator-chat__message--${message.role}`}
            >
              <div className="operator-chat__role">
                {message.role === "assistant" ? "Execution agent" : "Operator"}
              </div>
              <div>{message.content}</div>
            </div>
          ))
        )}
      </div>

      <div className="panel__actions">
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => {
            sendPrompt("open_context");
            onOpenExperiment?.();
          }}
          disabled={!run?.experiment_id}
        >
          Open experiment
        </button>
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => {
            sendPrompt("open_context");
            onOpenValidation?.();
          }}
          disabled={!actions.some((item) => item.validation_job_id)}
        >
          Open validation
        </button>
        <button
          type="button"
          className="button button--ghost button--sm"
          onClick={() => {
            sendPrompt("summarize_failures");
            onFocusFailures?.();
          }}
          disabled={!run}
        >
          Focus failures
        </button>
      </div>
    </section>
  );
}
