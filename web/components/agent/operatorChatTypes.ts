import type { OperatorConversationResponse } from "../../lib/operatorConversationTypes";

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
  response?: OperatorConversationResponse;
};
