export type CreationProposal = {
  proposal_id: string; proposal_digest: string; expires_at: string; session_id: string;
  preflight: { scope: { product: string; experiment: string }; execution_posture: string;
    parameters: { objective: { goal: string }; experiment_id: string; budgets: { max_actions: number; max_variant_runs: number; max_cost_usd: number } };
    plan: Array<{ capability_name: string; rationale: string }> };
};
export type CreationReceipt = { receipt_id: string; receipt_digest: string; run_id: string; acknowledgement: string; replayed?: boolean };
export type CreationDecision = { proposal: CreationProposal; receipt: CreationReceipt };
