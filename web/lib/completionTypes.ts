export type AgentRunCompletionProjectionState =
  | "not_governed"
  | "missing"
  | "current"
  | "lagging"
  | "leading"
  | "corrupt"
  | "stale";

export type AgentRunCompletion = {
  tenant_id: string;
  workflow_id: string;
  completion_authority_required: boolean;
  authority_state: "legacy" | "awaiting_decision" | "current" | "superseded" | string;
  active_graph_revision?: number;
  active_criteria_digest?: string;
  authoritative_decision: {
    decision_id: string;
    decision_digest: string;
    scope: { tenant_id: string; workflow_id: string; graph_revision: number };
    criteria_id: string;
    criteria_digest: string;
    status: "complete" | "incomplete";
    evaluated_at: string;
    authoritative_event_sequence: number;
    accepted_result_ids: string[];
    evidence_ids: string[];
    blockers: unknown[];
    missing_requirements: string[];
    partial_failures: {
      missing_result_task_ids: string[];
      partial_task_ids: string[];
      failed_task_ids: string[];
      canceled_task_ids: string[];
    };
    receipt_blockers: string[];
  } | null;
  accepted_results: Array<{
    result_id: string;
    task_id: string;
    attempt_id: string;
    outcome: string;
    validation_status: string;
    result_digest: string;
  }>;
  evidence: Array<{
    evidence_id: string;
    task_id: string;
    attempt_id: string;
    availability: string;
    source_type: string;
    source_id: string;
    receipt_status: string;
    evidence_digest: string;
  }>;
  projection: {
    state: AgentRunCompletionProjectionState;
    freshness: "not_governed" | "current" | "stale";
    display_status: "not_governed" | "complete" | "incomplete" | "stale";
    authoritative_event_sequence: number | null;
    decision_event_sequence: number | null;
    projected_event_sequence: number | null;
    projection_lag: number | null;
    projection_version: number | null;
  };
  repair: {
    eligible: boolean;
    reason: string;
    last_outcome: Record<string, unknown> | null;
  };
};

export type AgentRunCompletionResponse = { completion: AgentRunCompletion };

export type AgentRunCompletionRepairResponse = {
  command: {
    outcome: "repaired" | "replayed" | string;
    command_id: string;
    decision_id: string;
    decision_digest: string;
    projection_version: number;
    original_outcome?: string;
  };
  completion: AgentRunCompletion;
};
