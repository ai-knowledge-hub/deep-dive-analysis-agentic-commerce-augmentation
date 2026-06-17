"use client";

import React from "react";
import { useEffect, useMemo, useState } from "react";
import type {
  AgentAction,
  AgentRun,
  AgentRunCommandPreflight,
  AgentRunCommandResponse,
  AgentRunCommandType,
  AgentRunEvent,
  AgentRuntimeRegistryResponse,
  AgentRuntimeRecoveryTemplate,
  AgentRuntimeSkillSpec,
} from "../../lib/types";
import {
  formatOperatorActionName,
  formatOperatorIdentifier,
  softenOperatorText,
} from "../../lib/operatorDisplayLanguage";
import { OperatorChatPrompts } from "./OperatorChatPrompts";
import { OperatorChatSummary } from "./OperatorChatSummary";
import { OperatorChatThread } from "./OperatorChatThread";
import { OperatorCommandControls } from "./OperatorCommandControls";
import { OperatorNavigationControls } from "./OperatorNavigationControls";
import {
  actionRiskLabel,
  buildCommandOutcome,
  formatPromptLabel,
  formatRunLabel,
  preferredRecoveryCapability,
} from "./operatorChatLogic";
import type { ChatMessage, OperatorCommand, PromptId } from "./operatorChatTypes";

type Props = {
  run: AgentRun | null;
  actions: AgentAction[];
  events: AgentRunEvent[];
  runtimeRegistry?: AgentRuntimeRegistryResponse | null;
  selectedAction: AgentAction | null;
  nextRecommendedAction: {
    action: AgentAction | null;
    guardrails: string[];
    hint: string;
  };
  onOpenExperiment?: () => void;
  onOpenValidation?: () => void;
  onOpenInterventionsForRun?: () => void;
  onFocusFailures?: () => void;
  onFocusApprovals?: () => void;
  onFocusPolicy?: () => void;
  onFocusValidationLinked?: () => void;
  onJumpToNextAction?: () => void;
  onPreflightCommand?: (command: OperatorCommand) => Promise<AgentRunCommandPreflight>;
  onIssueCommand?: (
    command: OperatorCommand,
  ) => Promise<AgentRunCommandResponse | void> | AgentRunCommandResponse | void;
};

export function OperatorConsoleChat({
  run,
  actions,
  events,
  runtimeRegistry,
  selectedAction,
  nextRecommendedAction,
  onOpenExperiment,
  onOpenValidation,
  onOpenInterventionsForRun,
  onFocusFailures,
  onFocusApprovals,
  onFocusPolicy,
  onFocusValidationLinked,
  onJumpToNextAction,
  onPreflightCommand,
  onIssueCommand,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingCommandKey, setPendingCommandKey] = useState<string | null>(null);
  const [selectedRecoveryCapability, setSelectedRecoveryCapability] = useState("");
  const [selectedRecoverySkill, setSelectedRecoverySkill] = useState("");

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
    const recoveryCapabilities = Array.from(
      new Set((run?.allowed_capabilities ?? []).filter((item) => Boolean(item?.trim()))),
    );
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
      recoveryCapabilities,
    };
  }, [actions, events, run?.allowed_capabilities]);

  useEffect(() => {
    const preferred = preferredRecoveryCapability(derived.recoveryCapabilities);
    setSelectedRecoveryCapability((current) =>
      current && derived.recoveryCapabilities.includes(current) ? current : preferred,
    );
  }, [derived.recoveryCapabilities]);

  const activeRecoveryCapability =
    selectedRecoveryCapability || preferredRecoveryCapability(derived.recoveryCapabilities);

  const recoverySkillOptions = useMemo(() => {
    if (!runtimeRegistry || !activeRecoveryCapability) return [];
    const capability = runtimeRegistry.capabilities.find(
      (item) => item.name === activeRecoveryCapability,
    );
    const toolId = capability?.tool_id;
    if (!toolId) return [];
    const selection = runtimeRegistry.skill_selection_by_tool?.[toolId];
    const candidateIds = selection?.candidate_skill_ids ?? [];
    return candidateIds
      .map((skillId) => runtimeRegistry.skills.find((skill) => skill.id === skillId))
      .filter((skill): skill is AgentRuntimeSkillSpec => Boolean(skill));
  }, [activeRecoveryCapability, runtimeRegistry]);

  const defaultRecoverySkillId = useMemo(() => {
    if (!runtimeRegistry || !activeRecoveryCapability) return "";
    const capability = runtimeRegistry.capabilities.find(
      (item) => item.name === activeRecoveryCapability,
    );
    const toolId = capability?.tool_id;
    return toolId
      ? runtimeRegistry.skill_selection_by_tool?.[toolId]?.default_skill_id ?? ""
      : "";
  }, [activeRecoveryCapability, runtimeRegistry]);

  const activeRecoverySkill =
    selectedRecoverySkill || defaultRecoverySkillId || recoverySkillOptions[0]?.id || "";

  const activeRecoveryTemplate = useMemo<AgentRuntimeRecoveryTemplate | null>(() => {
    if (!runtimeRegistry || !activeRecoveryCapability) return null;
    return (
      runtimeRegistry.recovery_templates?.find(
        (template) => template.capability_name === activeRecoveryCapability,
      ) ?? null
    );
  }, [activeRecoveryCapability, runtimeRegistry]);

  useEffect(() => {
    setSelectedRecoverySkill((current) =>
      current && recoverySkillOptions.some((skill) => skill.id === current)
        ? current
        : defaultRecoverySkillId,
    );
  }, [defaultRecoverySkillId, recoverySkillOptions]);

  const recoverySkillMetadata =
    activeRecoverySkill && recoverySkillOptions.length > 0
      ? {
          skill_id: activeRecoverySkill,
          preferred_skill_id: activeRecoverySkill,
        }
      : {};

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
            ? `Current selection is ${formatOperatorActionName(selectedAction.capability_name)} (${selectedAction.status ?? "unknown"}).`
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
      `${formatRunLabel(run)} is ${run.status ?? "unknown"} in ${formatOperatorIdentifier(run.state)} state.`,
    ];
    if (derived.failedActions.length > 0) {
      parts.push(`${derived.failedActions.length} action failure${derived.failedActions.length === 1 ? "" : "s"} need review.`);
    }
    if (derived.proposedActions.length > 0) {
      parts.push(`${derived.proposedActions.length} proposed action${derived.proposedActions.length === 1 ? "" : "s"} are waiting in queue.`);
    }
    if (nextRecommendedAction.action) {
      parts.push(
        `Next suggested step is ${formatOperatorActionName(nextRecommendedAction.action.capability_name)}.`,
      );
    }
    if (derived.policyEvents.length > 0) {
      parts.push(`${derived.policyEvents.length} policy event${derived.policyEvents.length === 1 ? "" : "s"} are on the timeline.`);
    }
    if (selectedAction) {
      parts.push(
        `Selected action is ${formatOperatorActionName(selectedAction.capability_name)} with ${actionRiskLabel(selectedAction).toLowerCase()} profile.`,
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
          `${formatRunLabel(run)} is currently ${run.status ?? "unknown"} and has progressed to ${formatOperatorIdentifier(run.state)}.`,
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
                .map((item) => formatOperatorActionName(item.capability_name))
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
          return "No action is selected. Click an action in the queue and I’ll explain its rationale, guardrails, and linked work.";
        }
        if (String(selectedAction.status || "").toLowerCase() !== "proposed") {
          return [
            `${formatOperatorActionName(selectedAction.capability_name)} is currently ${selectedAction.status}. It is not blocked in the proposal stage anymore.`,
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
            `${formatOperatorActionName(selectedAction.capability_name)} is proposed and not currently blocked by a budget guardrail.`,
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
          `${formatOperatorActionName(selectedAction.capability_name)} is being held by guardrails.`,
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
          `Recommended next step is ${formatOperatorActionName(nextRecommendedAction.action.capability_name)}.`,
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
          return "The most useful related context for this run is the linked optimization test. Open it when you need to compare the run against the original assumption, variants, and outcome framing.";
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

  async function issueCommand(
    command_type: AgentRunCommandType,
    message: string,
    action_id?: string | null,
    metadata?: Record<string, unknown>,
  ) {
    const command: OperatorCommand = { command_type, action_id, message };
    if (metadata !== undefined) {
      command.metadata = metadata;
    }
    const commandKey = `${command_type}:${action_id ?? "run"}:${JSON.stringify(metadata ?? {})}`;
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}-${command_type}`,
      role: "user",
      content: message,
    };
    setMessages((current) => [...current, userMessage]);
    try {
      if (onPreflightCommand) {
        const preflight = await onPreflightCommand(command);
        setMessages((current) => [
          ...current,
          {
            id: `assistant-${Date.now()}-${command_type}-safety-check`,
            role: "assistant",
            content: [
              `Safety check: ${softenOperatorText(preflight.summary)}`,
              preflight.blockers.length > 0
                ? `Blocker: ${softenOperatorText(preflight.blockers[0])}`
                : "",
              preflight.warnings.length > 0
                ? `Warning: ${softenOperatorText(preflight.warnings[0])}`
                : "",
              `Recovery path: ${softenOperatorText(preflight.rollback_guidance)}`,
              preflight.requires_confirmation && pendingCommandKey !== commandKey
                ? "Click the command again to confirm."
                : "",
            ]
              .filter(Boolean)
              .join(" "),
          },
        ]);
        if (!preflight.allowed) {
          setPendingCommandKey(null);
          return;
        }
        if (preflight.requires_confirmation && pendingCommandKey !== commandKey) {
          setPendingCommandKey(commandKey);
          return;
        }
      }
      setPendingCommandKey(null);
      const response = await onIssueCommand?.(command);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}-${command_type}`,
          role: "assistant",
          content: buildCommandOutcome(command_type, response),
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}-${command_type}-error`,
          role: "assistant",
          content:
            error instanceof Error
              ? `Command failed: ${error.message}`
              : "Command failed before the runtime accepted it.",
        },
      ]);
    }
  }

  return (
    <section className="panel__card panel__card--secondary">
      <OperatorChatSummary
        run={run}
        briefing={briefing}
        proposedCount={derived.proposedActions.length}
        approvedCount={derived.approvedActions.length}
        failedCount={derived.failedActions.length}
        policyCount={derived.policyEvents.length}
        selectedAction={selectedAction}
      />
      <OperatorChatPrompts
        selectedAction={selectedAction}
        hasNextAction={Boolean(nextRecommendedAction.action)}
        onPrompt={sendPrompt}
        onJumpToNextAction={onJumpToNextAction}
      />
      <OperatorChatThread messages={messages} />
      <OperatorCommandControls
        run={run}
        selectedAction={selectedAction}
        recoveryCapabilities={derived.recoveryCapabilities}
        activeRecoveryCapability={activeRecoveryCapability}
        recoverySkillOptions={recoverySkillOptions}
        activeRecoverySkill={activeRecoverySkill}
        activeRecoveryTemplate={activeRecoveryTemplate}
        recoverySkillMetadata={recoverySkillMetadata}
        onRecoveryCapabilityChange={setSelectedRecoveryCapability}
        onRecoverySkillChange={setSelectedRecoverySkill}
        onIssueCommand={issueCommand}
      />
      <OperatorNavigationControls
        run={run}
        proposedCount={derived.proposedActions.length}
        policyCount={derived.policyEvents.length}
        validationLinkedCount={derived.validationLinkedActions.length}
        onPrompt={sendPrompt}
        onOpenExperiment={onOpenExperiment}
        onOpenValidation={onOpenValidation}
        onOpenInterventionsForRun={onOpenInterventionsForRun}
        onFocusFailures={onFocusFailures}
        onFocusApprovals={onFocusApprovals}
        onFocusPolicy={onFocusPolicy}
        onFocusValidationLinked={onFocusValidationLinked}
      />
    </section>
  );
}
