import type { AgentRunCommandType } from "../../lib/types";

export type PromptId =
  | "brief"
  | "explain_run"
  | "summarize_failures"
  | "blocked_action"
  | "recommend_next"
  | "open_context";

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

export type OperatorCommand = {
  command_type: AgentRunCommandType;
  action_id?: string | null;
  message?: string | null;
  metadata?: Record<string, unknown>;
};
