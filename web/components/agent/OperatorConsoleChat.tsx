"use client";

import React from "react";
import { useEffect, useMemo, useState } from "react";
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

function actionRiskLabel(action: AgentAction | null): string {
  if (!action) return "No action selected";
  if (
    action.capability_name === "publish_copy_revision" ||
    action.capability_name === "promote_variant_prod"
  ) {
    return "High risk";
  }
  if (
    action.capability_name === "promote_variant_lab" ||
    action.capability_name === "request_synthetic_validation" ||
    action.capability_name === "run_variant"
  ) {
    return "Medium risk";
  }
  return "Low risk";
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
    const proposedActions = actions.filter(
      (item) => String(item.status || "").toLowerCase() === "proposed",
    );
    const approvedActions = actions.filter(
      (item) => String(item.status || "").toLowerCase() === "approved",
    );
    const executedActions = actions.filter(
      (item) => String(item.status || "").toLowerCase() === "executed",
    );
    const failedActions = actions.filter(
      (item) => String(item.status || "").toLowerCase() === "failed",
    );
    const policyEvents = events.filter((item) => Boolean(item.is_policy_event));
    const failedEvents = events.filter(
      (item) => String(item.status || "").toLowerCase() === "failed",
    );
    const latestEvent = events.at(-1) ?? null;
    const latestFailureEvent = [...events]
      .reverse()
      .find((item) => String(item.status || "").toLowerCase() === "failed") ?? null;
    const latestPolicyEvent = [...events]
      .reverse()
      .find((item) => Boolean(item.is_policy_event)) ?? null;
    const validationLinkedActions = actions.filter((item) => Boolean(item.validation_job_id));
    return {
      proposedActions,
      approvedActions,
      executedActions,
      failedActions,
      policyEvents,
      failedEvents,
      latestEvent,
      latestFailureEvent,
      latestPolicyEvent,
      validationLinkedActions,
    };
  }, [actions, events]);

  useEffect(() => {
    if (!run) {
      setMessages([]);
      return;
    }
    setMessages([
      {
        id: `assistant-seed-${run.id}-${selectedAction?.id ?? "none"}`,
        role: "assistant",
        content: [
          `${formatRunLabel(run)} is ready for review.`,
          selectedAction
            ? `Current selection is ${selectedAction.capability_name} (${selectedAction.status ?? "unknown"}).`
            : "No action is selected yet.",
          "Use the quick prompts to explain the state, understand failures, or decide the safest next step.",
        ].join(" "),
      },
    ]);
  }, [run, selectedAction]);

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
    if (derived.proposedActions.length > 0) {
      parts.push(`${derived.proposedActions.length} proposed action${derived.proposedActions.length === 1 ? "" : "s"} are waiting in queue.`);
    }
    if (nextRecommendedAction.action) {
      parts.push(
        `Next suggested step is ${nextRecommendedAction.action.capability_name}.`,
      );
    }
    if (derived.policyEvents.length > 0) {
      parts.push(`${derived.policyEvents.length} policy event${derived.policyEvents.length === 1 ? "" : "s"} are on the timeline.`);
    }
    if (selectedAction) {
      parts.push(
        `Selected action is ${selectedAction.capability_name} with ${actionRiskLabel(selectedAction).toLowerCase()} profile.`,
      );
    }
    return parts.join(" ");
  }, [
    derived.failedActions.length,
    derived.policyEvents.length,
    derived.proposedActions.length,
    nextRecommendedAction.action,
    run,
    selectedAction,
  ]);

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
          `Queue mix is ${derived.proposedActions.length} proposed, ${derived.approvedActions.length} approved, ${derived.executedActions.length} executed, and ${derived.failedActions.length} failed.`,
          run.run_mode === "plan_only"
            ? "It is still in plan-only mode, so approvals can be prepared but step execution is intentionally blocked."
            : "It is in an executable mode, so approved actions can continue through stepwise runtime execution.",
          derived.latestEvent?.note
            ? `Latest timeline signal: ${derived.latestEvent.note}`
            : "",
        ].join(" ");
      case "summarize_failures":
        if (derived.failedActions.length === 0 && derived.failedEvents.length === 0) {
          return "There are no failed actions or failed timeline events on this run right now. The main focus should be proposed actions and policy state.";
        }
        return [
          `There are ${derived.failedActions.length} failed action${derived.failedActions.length === 1 ? "" : "s"} and ${derived.failedEvents.length} failed timeline event${derived.failedEvents.length === 1 ? "" : "s"}.`,
          derived.failedActions.length > 0
            ? `Most recent failed capabilities are ${derived.failedActions
                .slice(0, 3)
                .map((item) => item.capability_name)
                .join(", ")}.`
            : "",
          derived.latestFailureEvent?.note
            ? `Latest failure note: ${derived.latestFailureEvent.note}`
            : "",
          "Use the failure-focused timeline before retrying anything so you can separate runtime breakage from policy blocks.",
        ]
          .filter(Boolean)
          .join(" ");
      case "blocked_action":
        if (!selectedAction) {
          return "No action is selected. Click an action in the queue and I’ll explain its rationale, guardrails, and linked artifacts.";
        }
        if (String(selectedAction.status || "").toLowerCase() !== "proposed") {
          return [
            `${selectedAction.capability_name} is currently ${selectedAction.status}. It is not blocked in the proposal stage anymore.`,
            `Risk profile is ${actionRiskLabel(selectedAction).toLowerCase()}.`,
            selectedAction.rationale
              ? `Recorded rationale: ${selectedAction.rationale}`
              : "",
            "The next question is whether its output is complete and whether downstream execution is still safe.",
          ]
            .filter(Boolean)
            .join(" ");
        }
        if (nextRecommendedAction.guardrails.length === 0) {
          return [
            `${selectedAction.capability_name} is proposed and not currently blocked by a budget guardrail.`,
            `Risk profile is ${actionRiskLabel(selectedAction).toLowerCase()}.`,
            selectedAction.rationale
              ? `Recorded rationale: ${selectedAction.rationale}`
              : "",
            "If you approve it, the run can continue according to its current execution mode.",
          ]
            .filter(Boolean)
            .join(" ");
        }
        return [
          `${selectedAction.capability_name} is being held by guardrails.`,
          `Risk profile is ${actionRiskLabel(selectedAction).toLowerCase()}.`,
          `Main reason: ${nextRecommendedAction.guardrails[0]}.`,
          derived.latestPolicyEvent?.note
            ? `Latest policy note: ${derived.latestPolicyEvent.note}`
            : "",
          "Review budget, policy state, and the latest timeline note before approving.",
        ]
          .filter(Boolean)
          .join(" ");
      case "recommend_next":
        if (!nextRecommendedAction.action) {
          return [
            nextRecommendedAction.hint,
            derived.approvedActions.length > 0
              ? "There are already approved actions in queue, so the decision is whether to resume or step the run."
              : "",
            derived.latestPolicyEvent?.note
              ? `Latest policy note: ${derived.latestPolicyEvent.note}`
              : "",
          ]
            .filter(Boolean)
            .join(" ");
        }
        return [
          `Recommended next step is ${nextRecommendedAction.action.capability_name}.`,
          nextRecommendedAction.hint,
          `Risk profile is ${actionRiskLabel(nextRecommendedAction.action).toLowerCase()}.`,
          nextRecommendedAction.action.rationale
            ? `Reasoning: ${nextRecommendedAction.action.rationale}`
            : "",
          run.status === "failed"
            ? "Do not continue blindly from a failed state. Confirm recovery path first."
            : "",
        ]
          .filter(Boolean)
          .join(" ");
      case "open_context":
        if (run.experiment_id) {
          return "The most useful related context for this run is the linked experiment. Open it when you need to compare the run against the originating hypothesis, variants, and outcome framing.";
        }
        if (derived.validationLinkedActions.length > 0) {
          return "This run has validation-linked actions. Opening the validation workspace is the best next context jump because it tells you whether observed evidence supports the next move.";
        }
        return "The best context jump here is the failure-focused timeline. That is where the operator can understand what changed, what is blocked, and whether the next intervention should be approval, pause, or escalation.";
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

      {run ? (
        <div className="agent-ops-summary">
          <span className="panel__badge panel__badge--secondary">
            Proposed: {derived.proposedActions.length}
          </span>
          <span className="panel__badge panel__badge--secondary">
            Approved: {derived.approvedActions.length}
          </span>
          <span className="panel__badge panel__badge--secondary">
            Failed: {derived.failedActions.length}
          </span>
          <span className="panel__badge panel__badge--secondary">
            Policy: {derived.policyEvents.length}
          </span>
          {selectedAction ? (
            <span className="panel__badge panel__badge--warning">
              Selection: {selectedAction.capability_name}
            </span>
          ) : null}
        </div>
      ) : null}

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
          {selectedAction ? "Explain selected action" : "Explain blocked action"}
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
