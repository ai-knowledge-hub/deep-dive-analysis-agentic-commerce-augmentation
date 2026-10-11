import type { AgentRun } from "./types";

export type OperatorConversationFact = {
  id: string;
  category: string;
  text: string;
  source: string;
  trust?: "authoritative_projection" | "recorded_untrusted_content";
  provenance: {
    record_type: string;
    record_id: string;
  };
};

export type OperatorConversationResponse = {
  contract: "operator-conversation-response.v1" | "operator-conversation-response.v2";
  session_id: string;
  run_id: string;
  intent: string;
  answer: string;
  verified_facts: OperatorConversationFact[];
  inference: {
    kind: "validated_fact_selection";
    model_prose_exposed: false;
  };
  recommendation?: {
    kind: string;
    text: string;
    href?: string;
  } | null;
  evidence: Array<{
    kind: string;
    record: Record<string, unknown>;
    href: string;
  }>;
  navigation: Array<{ label: string; href: string }>;
  freshness: {
    state: "current" | "stale";
    data_state: "complete" | "partial" | "missing" | "unavailable" | "contradictory";
    snapshot_cursor?: string | null;
    latest_cursor?: string | null;
    snapshot_digest: string;
  };
  warnings: Array<{ code: string; message: string }>;
  snapshot: {
    contract: string;
    digest: string;
    fetched_at: string;
    scope: { tenant_id: string; principal_id: string };
    run: AgentRun;
    actions: Array<Record<string, unknown>>;
    events: Array<Record<string, unknown>>;
    event_page: Record<string, unknown>;
    approvals: Array<Record<string, unknown>>;
    effects: Array<Record<string, unknown>>;
    experiment?: Record<string, unknown> | null;
    validation_jobs: Array<Record<string, unknown>>;
    completion: Record<string, unknown>;
    completeness: Record<string, unknown>;
  };
  read_only: true;
  interaction_mode?: "read_only" | "proposal";
  command_proposal?: OperatorCommandProposal | null;
};

export type OperatorCommandProposal = {
  contract: "workflow.operator-command-proposal.v1" | "workflow.operator-command-proposal.v2" | "workflow.operator-command-proposal.v3" | "workflow.operator-command-proposal.v4" | "workflow.operator-command-proposal.v5" | "workflow.operator-command-proposal.v6";
  proposal_id: string;
  proposal_digest: string;
  tenant_id: string;
  principal_id: string;
  run_id: string;
  command_type: "pause" | "resume" | "cancel" | "approve" | "reject" | "retry" | "reconcile_effect";
  predicted_run_status?: "planned" | "running" | "canceled";
  parameters: { effect_execution_id?: string; reconciliation?: ReconciliationProof; action_id?: string; action_status?: string; retry_strategy?: "same_action"; retry_plan?: { strategy: "same_action"; capability_name: string; normalized_inputs: Record<string, unknown>; inputs_hash: string; side_effects: string[]; review_checklist: string[] }; review?: {
    capability_name: string; normalized_inputs: Record<string, unknown>; inputs_hash: string;
    side_effects: string[]; review_checklist: string[]; approval_id: string | null;
    approval_sequence: number | null; approval_envelope_digest: string | null;
    registry_authority: Record<string, unknown>;
  } };
  source: {
    active_graph_revision: number;
    run_mode?: "plan_only" | "auto_execute_safe";
    run_status: string;
    run_state: string;
    snapshot_digest: string;
    snapshot_cursor?: string | null;
    latest_event_id?: string | null;
    latest_event_timestamp?: string | null;
    harness_id?: string | null;
    policy_profile_id?: string | null;
    registry_version?: string | null;
    registry_fingerprint?: string | null;
  };
  preflight: {
    digest: string;
    result: {
      allowed: boolean;
      risk_level: string;
      blockers: string[];
      warnings: string[];
      summary: string;
    };
  };
  idempotency_key: string;
  issued_at: string;
  expires_at: string;
  consequences: string[];
};

export type OperatorCommandReceipt = {
  contract: "workflow.operator-command-receipt.v1" | "workflow.operator-command-receipt.v2" | "workflow.operator-command-receipt.v3" | "workflow.operator-command-receipt.v4" | "workflow.operator-command-receipt.v5" | "workflow.operator-command-receipt.v6";
  receipt_id: string;
  proposal_id: string;
  proposal_digest: string;
  run_id: string;
  command_type: "pause" | "resume" | "cancel" | "approve" | "reject" | "retry" | "reconcile_effect";
  outcome: "paused" | "planned" | "running" | "canceled" | "approved" | "rejected" | "proposed" | "succeeded";
  resulting_run_status: "paused" | "planned" | "running" | "canceled" | "cancelled" | "failed" | "completed";
  reconciliation?: ReconciliationProof; effect_execution_id?: string; action_status?: string; control_state_preserved?: boolean;
  source_action_id?: string; retry_strategy?: "same_action"; retry_count?: number; action_sequence?: number; effect_idempotency_key?: string;
  action_id?: string; approval_id?: string; approval_envelope_digest?: string; approval_sequence?: number; approval_command_id?: string;
  run_mode?: "plan_only" | "auto_execute_safe";
  event_ids: {
    command: string;
    lifecycle: string;
    stopping_condition?: string | null;
  };
  acknowledgement: "control_plane_paused" | "control_plane_resume_eligible" | "control_plane_canceled" | "exact_action_decision_recorded" | "retry_action_proposed" | "existing_effect_outcome_recorded";
  propagation_state: "runtime_propagation_not_certified";
  completed_at: string;
  receipt_digest: string;
  replayed?: boolean;
};

export type OperatorCommandRecord = {
  proposal: OperatorCommandProposal;
  receipt: OperatorCommandReceipt | null;
};

export type OperatorCommandRecordListResponse = {
  contract: "operator-command-record-list.v1";
  run_id: string;
  records: OperatorCommandRecord[];
  count: number;
  total_count: number;
  page: {
    limit: number;
    returned_count: number;
    total_count: number;
    has_more: boolean;
    next_cursor: string | null;
  };
  completeness: {
    state: "complete" | "partial";
    included_count: number;
    total_count: number;
    reason: "additional_pages_available" | "continuation_page" | null;
  };
};

export type OperatorCommandConfirmationResponse = {
  contract: "operator-command-confirmation.v1";
  run_id: string;
  proposal_id: string;
  command: Record<string, unknown>;
  receipt: OperatorCommandReceipt;
  run: AgentRun;
};


export type ReconciliationProof = {
  effect_execution_id: string; effect_status: string; approval_id: string; approval_envelope_digest: string;
  effect_idempotency_key: string; authorization_snapshot_digest: string; capability_name: string;
  receipt_id: string; outputs: Record<string, unknown>; outputs_hash: string; evidence_digest: string;
  evidence_id: string; result_id: string | null; verification_state: "verified";
  observed_outcome: "succeeded"; projected_action_status: "executed";
};
