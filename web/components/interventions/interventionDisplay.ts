import { softenOperatorText } from "../../lib/operatorDisplayLanguage";
import type { ApprovalItem } from "./interventionTypes";

export function formatActionLabel(value?: string | null): string {
  return softenOperatorText(String(value || "selected action").replaceAll("_", " "));
}

export function formatApprovalSummary(item: ApprovalItem): string {
  const actionName = formatActionLabel(item.action.capability_name);
  if (item.action.rationale) {
    return `${actionName} is waiting for approval. ${item.action.rationale}`;
  }
  return `${actionName} is waiting for operator approval before execution.`;
}
