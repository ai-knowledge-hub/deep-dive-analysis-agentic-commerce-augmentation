import { ConversationResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request(path: string, init?: RequestInit): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }
  return response.json();
}

export async function startConversation(message: string): Promise<ConversationResponse> {
  return request("/conversation/start", {
    method: "POST",
    body: JSON.stringify({ opening_message: message }),
  });
}

export async function sendConversationMessage(
  sessionId: string,
  message: string,
): Promise<ConversationResponse> {
  return request(`/conversation/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}
