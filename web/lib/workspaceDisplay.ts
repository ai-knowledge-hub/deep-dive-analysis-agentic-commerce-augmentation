import { formatOperatorActionName } from "./operatorDisplayLanguage";
const STEP_LABELS: Record<string, string> = {
  freeze_retrieval_protocol: "Freeze comparison evidence", run_control_baseline: "Measure the baseline",
  seed_hypotheses: "Suggest improvement hypotheses", generate_variants: "Draft candidate variants",
  run_variant: "Evaluate one candidate", request_synthetic_validation: "Request synthetic validation",
  review_validation_readiness: "Review validation coverage", update_posterior_and_decisions: "Update evidence and decisions",
  recommend_next_action: "Recommend the next step",
};
export function workspaceActionLabel(name: string) {
  return STEP_LABELS[name] ?? formatOperatorActionName(name);
}
