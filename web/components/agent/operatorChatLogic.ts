import type { AgentAction, AgentRun, AgentRunCommandResponse, AgentRunCommandType } from "../../lib/types";
import {
  formatOperatorActionName,
  formatOperatorIdentifier,
  softenOperatorText,
} from "../../lib/operatorDisplayLanguage";
import type { PromptId } from "./operatorChatTypes";

export function formatRunLabel(run: AgentRun | null): string {
  if (!run) return "No run selected";
  return run.experiment_id
    ? `Run for experiment ${run.experiment_id.slice(0, 8)}`
    : `Run ${run.id.slice(0, 8)}`;
}

export function formatPromptLabel(promptId: PromptId): string {
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

export function actionRiskLabel(action: AgentAction | null): string {
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

function outputString(outputs: Record<string, unknown> | undefined, key: string): string | null {
  const value = outputs?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function buildArtifactGuidance(action: AgentAction): string[] {
  const outputs = action.outputs;
  const metricId =
    outputString(outputs, "metric_id") ||
    outputString(outputs, "new_metric_id") ||
    outputString(outputs, "source_metric_id");
  const revisionId =
    outputString(outputs, "revision_id") ||
    outputString(outputs, "copy_revision_id") ||
    outputString(outputs, "published_revision_id");
  const validationJobId =
    action.validation_job_id || outputString(outputs, "validation_job_id");
  const variantId = action.variant_id || outputString(outputs, "variant_id");
  const hypothesisId = action.hypothesis_id || outputString(outputs, "hypothesis_id");

  const guidance: string[] = [];
  if (metricId) {
    guidance.push(`Review metric ${metricId} in the experiment evidence before approving downstream promotion.`);
  }
  if (variantId) {
    guidance.push(`Compare variant ${variantId} against the control and latest confidence update.`);
  }
  if (validationJobId) {
    guidance.push(`Open validation job ${validationJobId} to inspect synthetic/observed agreement.`);
  }
  if (revisionId) {
    guidance.push(`Inspect copy revision ${revisionId} and confirm the published text/audit event.`);
  }
  if (hypothesisId) {
    guidance.push(`Check test idea ${hypothesisId} to see which assumption this action supports or challenges.`);
  }
  if (action.snapshot_version != null) {
    guidance.push(`Use evidence version ${action.snapshot_version} when comparing retrieval-backed results.`);
  }
  if (action.error) {
    guidance.push(`Failure note: ${action.error}`);
  }
  if (guidance.length === 0 && Object.keys(outputs ?? {}).length > 0) {
    guidance.push("Inspect the action results for linked work and decision details.");
  }
  return guidance;
}

export function buildCommandOutcome(
  commandType: AgentRunCommandType,
  response?: AgentRunCommandResponse | void,
): string {
  if (!response) {
    return `Command receipt recorded: ${commandType}. I refreshed the execution context so you can review the resulting run state and timeline.`;
  }
  const parts = [`Command completed: ${commandType}.`];
  if (response.message) {
    parts.push(softenOperatorText(response.message));
  }
  if (response.action) {
    parts.push(
      `Action ${formatOperatorActionName(response.action.capability_name ?? response.action.id)} is now ${response.action.status ?? "updated"}.`,
    );
    if (response.action.retry_count && response.action.retry_count > 0) {
      parts.push(`Retry count is ${response.action.retry_count}.`);
    }
    if (response.action.rollback_guidance) {
      parts.push(`Recovery guidance: ${softenOperatorText(response.action.rollback_guidance)}`);
    }
    const compensatingAction = response.action.compensating_actions?.[0];
    if (compensatingAction?.label) {
      parts.push(`Recovery action: ${softenOperatorText(compensatingAction.label)}.`);
    }
    const guidance = buildArtifactGuidance(response.action);
    if (guidance.length > 0) {
      parts.push(`Next inspection: ${guidance.slice(0, 3).join(" ")}`);
    }
  }
  if (response.run) {
    parts.push(
      `Run is ${response.run.status ?? "unknown"} in ${formatOperatorIdentifier(response.run.state)} state.`,
    );
  }
  if (response.preflight?.risk_level) {
    parts.push(`Safety-check risk was ${response.preflight.risk_level}.`);
  }
  return softenOperatorText(parts.join(" "));
}

export function preferredRecoveryCapability(capabilities: string[]): string {
  return capabilities.includes("recommend_next_action")
    ? "recommend_next_action"
    : capabilities[0] ?? "";
}
