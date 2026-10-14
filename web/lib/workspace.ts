import type { AgentRun, AgentAction, AgentRunEvent } from "./types";
import type { OperatorConversationResponse } from "./operatorConversationTypes";
import type { CreationProposal, CreationReceipt } from "./runCreationTypes";
export type { CreationProposal, CreationReceipt, CreationDecision } from "./runCreationTypes";
export type WorkspaceTurn = { id: number; speaker: string; content: string; metadata: { workspace_result?: WorkspaceMessage; operator_response?: OperatorConversationResponse } };
export type WorkspaceMessage = { session_id: string; run_id: string | null; state: string; answer?: string; proposal?: CreationProposal;
  candidates?: Array<{ id: string; name: string; product_name?: string }>; has_more?: boolean; response?: OperatorConversationResponse };
export type WorkspaceHistory = { session_id: string; run_id: string | null; run: AgentRun | null; actions: AgentAction[]; events: AgentRunEvent[]; as_of?: string; actions_has_more?: boolean;
  confirmed_proposal?: CreationProposal | null; proposals: CreationProposal[]; receipt: CreationReceipt | null; turns: WorkspaceTurn[]; turns_has_more: boolean; turns_before_id?: number | null; has_more: boolean };
export type WorkspaceList = { conversations: Array<{ session_id: string; run_id: string | null; created_at: string; preview?: string }>; has_more: boolean };
export async function workspaceRequest<T>(clientId: string, payload: Record<string, unknown>, signal?: AbortSignal): Promise<T> {
  const response = await fetch("/api/operator-workspace", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, client_id: clientId }), signal });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Workspace request failed");
  return data as T;
}
