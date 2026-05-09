import type {
  AgentAction,
  AgentCompensatingAction,
  AgentRun,
  AgentRunEvent,
  AgentRuntimeHarnessProfile,
} from "../../lib/types";

export type Priority = "critical" | "high" | "medium" | "low";
export type RiskLevel = "high" | "medium" | "low";

export type InterventionDetail = {
  run: AgentRun;
  actions: AgentAction[];
  events: AgentRunEvent[];
  harness: AgentRuntimeHarnessProfile | null;
  latestPolicyEvent: AgentRunEvent | null;
  latestFailureEvent: AgentRunEvent | null;
  proposedActions: AgentAction[];
  approvedActions: AgentAction[];
};

export type HarnessAwareIntervention = {
  harness: AgentRuntimeHarnessProfile | null;
};

export type ApprovalItem = {
  kind: "approval";
  run: AgentRun;
  harness: AgentRuntimeHarnessProfile | null;
  action: AgentAction;
  priority: Priority;
  risk: RiskLevel;
  summary: string;
  reason: string;
};

export type RetryItem = {
  kind: "retry";
  run: AgentRun;
  harness: AgentRuntimeHarnessProfile | null;
  control: "start" | "step";
  priority: Priority;
  risk: RiskLevel;
  title: string;
  summary: string;
};

export type PauseItem = {
  kind: "pause";
  run: AgentRun;
  harness: AgentRuntimeHarnessProfile | null;
  priority: Priority;
  risk: RiskLevel;
  summary: string;
};

export type EscalationItem = {
  kind: "escalation";
  run: AgentRun;
  harness: AgentRuntimeHarnessProfile | null;
  priority: Priority;
  risk: RiskLevel;
  title: string;
  summary: string;
  latestEvent?: AgentRunEvent | null;
};

export type CommandItem = {
  kind: "command";
  run: AgentRun;
  harness: AgentRuntimeHarnessProfile | null;
  event: AgentRunEvent;
  priority: Priority;
  risk: RiskLevel;
  title: string;
  summary: string;
  rollbackGuidance?: string | null;
  compensatingActions?: AgentCompensatingAction[];
};
