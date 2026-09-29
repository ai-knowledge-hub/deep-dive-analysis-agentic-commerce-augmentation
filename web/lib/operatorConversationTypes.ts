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
  contract: "operator-conversation-response.v1";
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
};
