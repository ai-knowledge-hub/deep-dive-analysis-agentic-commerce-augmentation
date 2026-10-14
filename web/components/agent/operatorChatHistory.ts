import type { OperatorConversationResponse } from "../../lib/operatorConversationTypes";
import type { WorkspaceHistory } from "../../lib/workspace";
import type { ChatMessage } from "./operatorChatTypes";

function recordedTurnId(message: ChatMessage): number | null {
  const match = /^history-(\d+)$/.exec(message.id);
  const id = match ? Number(match[1]) : NaN;
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function chronologicalMessages(messages: ChatMessage[]): ChatMessage[] {
  const recorded: Array<{ message: ChatMessage; turnId: number }> = [];
  const pending: ChatMessage[] = [];
  for (const message of messages) {
    const turnId = recordedTurnId(message);
    if (turnId === null) pending.push(message);
    else recorded.push({ message, turnId });
  }
  // Durable turn IDs order every loaded page. Pending messages keep their
  // local order after recorded history until the server assigns turn IDs.
  recorded.sort((left, right) => left.turnId - right.turnId);
  return [...recorded.map(({ message }) => message), ...pending];
}

export function restoreWorkspaceMessages(history: WorkspaceHistory | null): ChatMessage[] {
  return (history?.turns ?? []).map((turn) => {
    const saved = turn.metadata?.operator_response;
    const response = saved && turn.speaker === "agent"
      && saved.session_id === history?.session_id && saved.run_id === history.run_id
      ? { ...saved, turn_id: turn.id } : undefined;
    return { id: `history-${turn.id}`, role: turn.speaker === "user" ? "user" : "assistant", content: turn.content, response };
  });
}

export function mergeRecordedMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const existing = new Map(current.map((message) => [message.id, message]));
  const restored = incoming.map((message) => ({
    ...message, response: existing.get(message.id)?.response ?? message.response,
  }));
  const restoredIds = new Set(restored.map((message) => message.id));
  return chronologicalMessages([...restored, ...current.filter((message) => !restoredIds.has(message.id))]);
}

export function recordLiveAnswer(current: ChatMessage[], requestId: number, response: OperatorConversationResponse): ChatMessage[] {
  const recorded = current.map((message) => message.id === `assistant-${requestId}`
    ? { ...message, id: response.turn_id ? `history-${response.turn_id}` : message.id, content: response.answer, response }
    : message.id === `user-${requestId}` && response.user_turn_id
      ? { ...message, id: `history-${response.user_turn_id}` } : message);
  return chronologicalMessages([...new Map(recorded.map((message) => [message.id, message])).values()]);
}
