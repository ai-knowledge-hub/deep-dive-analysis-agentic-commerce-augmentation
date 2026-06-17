import type { AgentRegistryAuditEvent } from "../../lib/types";

export type RegistryAuditDiffRow = { label: string; value: string };

export function formatDateCompact(value?: string | null): string {
  if (!value) return "unknown date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "unknown date";
  return parsed.toLocaleDateString();
}

export function summarizeRegistryAuditDiff(event: AgentRegistryAuditEvent): string {
  if (event.event_type === "registry_ownership_approved") {
    const receipt = event.diff.approval_receipt;
    const toolId = String(event.diff.tool_id || receipt?.tool_id || "registry tool");
    return `Ownership approval record for ${toolId}`;
  }
  if (event.event_type === "registry_pin_backfill_applied") {
    const runs = event.diff.runs?.updated ?? 0;
    const actions = event.diff.actions?.updated ?? 0;
    return `Backfilled ${runs} runs · ${actions} actions`;
  }
  if (event.event_type === "registry_harness_profile_updated") {
    return `Execution posture update · ${changedFieldCount(event)} fields changed`;
  }
  if (event.event_type === "registry_agent_profile_default_updated") {
    return `Agent profile default update · ${changedFieldCount(event)} fields changed`;
  }
  const sections = [
    ["skills", event.diff.skills],
    ["tools", event.diff.tools],
    ["capabilities", event.diff.capabilities],
    ["policies", event.diff.policy_profiles],
  ] as const;
  const changes = sections.flatMap(([label, section]) => {
    const added = section?.added?.length ?? 0;
    const removed = section?.removed?.length ?? 0;
    const changed = section?.changed?.length ?? 0;
    const total = added + removed + changed;
    return total > 0 ? [`${label}: +${added} -${removed} ~${changed}`] : [];
  });
  if (event.diff.skill_ids_by_tool_changed) {
    changes.push("tool-skill map changed");
  }
  return changes.length > 0 ? changes.join(" · ") : "No structural diff recorded";
}

export function registryAuditDiffRows(event: AgentRegistryAuditEvent): RegistryAuditDiffRow[] {
  if (event.event_type === "registry_ownership_approved") {
    const receipt = event.diff.approval_receipt;
    const toolId = String(event.diff.tool_id || receipt?.tool_id || "unknown tool");
    return [
      { label: "Tool", value: toolId },
      {
        label: "Approval record",
        value: String(receipt?.receipt_id || "approval metadata unavailable"),
      },
      {
        label: "Actor",
        value: String(receipt?.actor_user_id || "unknown actor"),
      },
    ];
  }
  if (event.event_type === "registry_pin_backfill_applied") {
    return [
      {
        label: "Runs",
        value: `${event.diff.runs?.updated ?? 0}/${event.diff.runs?.matched ?? 0} updated`,
      },
      {
        label: "Actions",
        value: `${event.diff.actions?.updated ?? 0}/${event.diff.actions?.matched ?? 0} updated`,
      },
      {
        label: "Client",
        value: String(event.diff.client_id || "unknown client"),
      },
    ];
  }
  if (
    event.event_type === "registry_harness_profile_updated" ||
    event.event_type === "registry_agent_profile_default_updated"
  ) {
    const changed = Array.isArray(event.diff.changed_fields)
      ? event.diff.changed_fields.join(", ")
      : "unknown";
    return [
      {
        label: "Target",
        value: String(event.diff.harness_id || event.diff.agent_profile_id || "registry posture"),
      },
      {
        label: "Actor",
        value: String(event.diff.actor_principal_id || event.source || "signed principal"),
      },
      {
        label: "Changed",
        value: changed || "none",
      },
    ];
  }
  const sections = [
    ["Skills", event.diff.skills],
    ["Tools", event.diff.tools],
    ["Capabilities", event.diff.capabilities],
    ["Policies", event.diff.policy_profiles],
  ] as const;
  const rows: RegistryAuditDiffRow[] = sections.flatMap(([label, section]) => {
    const values = [
      ...(section?.added ?? []).map((item) => `+${item}`),
      ...(section?.removed ?? []).map((item) => `-${item}`),
      ...(section?.changed ?? []).map((item) => `~${item}`),
    ];
    return values.length > 0 ? [{ label, value: values.slice(0, 5).join(", ") }] : [];
  });
  if (event.diff.skill_ids_by_tool_changed) {
    rows.push({ label: "Tool-skill map", value: "Changed" });
  }
  return rows.length > 0 ? rows : [{ label: "Diff", value: "No structural diff recorded" }];
}

export function approvalReceiptForEvent(
  event: AgentRegistryAuditEvent,
): Record<string, unknown> | null {
  const receipt = event.diff.approval_receipt;
  return receipt && typeof receipt === "object" ? receipt : null;
}

function changedFieldCount(event: AgentRegistryAuditEvent): number {
  const changed = event.diff.changed_fields;
  return Array.isArray(changed) ? changed.length : 0;
}
