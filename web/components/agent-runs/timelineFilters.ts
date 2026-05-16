export const TIMELINE_PRESET_STORAGE_KEY = "agent_runs.timeline_preset.v1";

export type TimelineStatusFilter =
  | "all"
  | "proposed"
  | "approved"
  | "executing"
  | "executed"
  | "failed"
  | "rejected";
export type TimelineWindowFilter = "all" | "24h" | "7d";
export type TimelinePresetId =
  | "all_activity"
  | "commands_24h"
  | "policy_failures_24h"
  | "variant_execution_7d"
  | "validation_focus_7d"
  | "custom";
export type TimelineEventFilter = "all" | "failed" | "policy" | "executed" | "command";

export const TIMELINE_EVENT_TYPES = new Set([
  "all",
  "failed",
  "policy",
  "executed",
  "command",
]);
export const TIMELINE_STATUS_TYPES = new Set([
  "all",
  "proposed",
  "approved",
  "executing",
  "executed",
  "failed",
  "rejected",
]);
export const TIMELINE_WINDOWS = new Set(["all", "24h", "7d"]);
export const TIMELINE_PRESET_IDS = new Set([
  "all_activity",
  "commands_24h",
  "policy_failures_24h",
  "variant_execution_7d",
  "validation_focus_7d",
  "custom",
]);

export const TIMELINE_PRESETS: Array<{
  id: Exclude<TimelinePresetId, "custom">;
  label: string;
  eventType: TimelineEventFilter;
  status: TimelineStatusFilter;
  capabilityName: string;
  timeWindow: TimelineWindowFilter;
}> = [
  {
    id: "all_activity",
    label: "All activity",
    eventType: "all",
    status: "all",
    capabilityName: "all",
    timeWindow: "all",
  },
  {
    id: "commands_24h",
    label: "Commands (24h)",
    eventType: "command",
    status: "all",
    capabilityName: "all",
    timeWindow: "24h",
  },
  {
    id: "policy_failures_24h",
    label: "Policy failures (24h)",
    eventType: "policy",
    status: "failed",
    capabilityName: "all",
    timeWindow: "24h",
  },
  {
    id: "variant_execution_7d",
    label: "Variant execution (7d)",
    eventType: "executed",
    status: "executed",
    capabilityName: "run_variant",
    timeWindow: "7d",
  },
  {
    id: "validation_focus_7d",
    label: "Validation focus (7d)",
    eventType: "all",
    status: "all",
    capabilityName: "request_synthetic_validation",
    timeWindow: "7d",
  },
];

export function resolveSinceForWindow(windowId: TimelineWindowFilter): string | null {
  if (windowId === "all") return null;
  const now = Date.now();
  const deltaMs = windowId === "24h" ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
  return new Date(now - deltaMs).toISOString();
}
