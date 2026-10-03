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
  contract: "workflow.operator-command-proposal.v1" | "workflow.operator-command-proposal.v2";
  proposal_id: string;
  proposal_digest: string;
  tenant_id: string;
  principal_id: string;
  run_id: string;
  command_type: "pause" | "resume";
  predicted_run_status?: "planned" | "running";
  parameters: Record<string, never>;
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
  contract: "workflow.operator-command-receipt.v1" | "workflow.operator-command-receipt.v2";
  receipt_id: string;
  proposal_id: string;
  proposal_digest: string;
  run_id: string;
  command_type: "pause" | "resume";
  outcome: "paused" | "planned" | "running";
  resulting_run_status: "paused" | "planned" | "running";
  run_mode?: "plan_only" | "auto_execute_safe";
  event_ids: {
    command: string;
    lifecycle: string;
    stopping_condition?: string | null;
  };
  acknowledgement: "control_plane_paused" | "control_plane_resume_eligible";
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
