import type {
  AgentCompensatingAction,
  AgentRunCommandType,
  AgentRunEvent,
} from "../../lib/types";

export type CompensatingProposalCommand = {
  command_type: Extract<AgentRunCommandType, "change_plan">;
  action_id?: string | null;
  message: string;
  metadata: Record<string, unknown>;
};

export type CompensatingProposalSource = {
  event: Pick<AgentRunEvent, "id" | "action_id" | "anchors">;
  experimentId?: string | null;
};

export function compensatingProposalKey(
  eventId: string,
  recommendation: AgentCompensatingAction | null | undefined,
): string | null {
  if (!recommendation?.capability_name) return null;
  return `compensate:${eventId}:${recommendation.capability_name}`;
}

export function compensatingProposalLabel(
  recommendation: AgentCompensatingAction,
): string {
  return (
    recommendation.label ??
    recommendation.capability_name ??
    "Review next safe action"
  );
}

function sourceActionId(event: Pick<AgentRunEvent, "action_id" | "anchors">): string | null {
  const source = event.anchors?.source_action_id;
  if (typeof source === "string" && source.trim()) return source;
  return event.action_id ?? null;
}

export function buildCompensatingProposalCommand(
  source: CompensatingProposalSource,
  recommendation: AgentCompensatingAction,
): CompensatingProposalCommand | null {
  if (!recommendation.capability_name) return null;
  return {
    command_type: "change_plan",
    action_id: sourceActionId(source.event),
    message:
      recommendation.label ||
      `Create compensating proposal for ${recommendation.capability_name}`,
    metadata: {
      recovery_strategy: "compensating_action",
      capability_name: recommendation.capability_name,
      source_event_id: source.event.id,
      compensating_priority: recommendation.priority,
      compensating_rationale: recommendation.rationale,
      inputs: source.experimentId ? { experiment_id: source.experimentId } : {},
    },
  };
}
