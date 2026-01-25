import {
  ConversationResponse,
  EvidenceAnalyzeResponse,
  EvidenceProduct,
  RecommendationVerifyResponse,
  RepresentationOptimizeResponse,
  SessionListResponse,
  ResearchRefreshResponse,
  SimulationProduct,
  SimulationRunResponse,
  SimulationOptimizeResponse,
  SimulationRetestResponse,
  SimulationRunListResponse,
  SimulationRunDetailResponse,
  SimulationLessonListResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CLIENT_ID_STORAGE_KEY = "client_id";

function getClientId(): string | undefined {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(CLIENT_ID_STORAGE_KEY);
    if (stored) {
      return stored;
    }
  }
  return process.env.NEXT_PUBLIC_CLIENT_ID ?? undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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

export async function startConversation(
  message: string,
  userId?: string | null,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  return request<ConversationResponse>("/conversation/start", {
    method: "POST",
    body: JSON.stringify({
      opening_message: message,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function sendConversationMessage(
  sessionId: string,
  message: string,
  userId?: string | null,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  return request<ConversationResponse>(`/conversation/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({
      message,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function getConversationSnapshot(
  sessionId: string,
  userId?: string | null,
): Promise<ConversationResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<ConversationResponse>(`/conversation/${sessionId}${suffix}`);
}

export async function listConversationSessions(
  userId: string,
): Promise<SessionListResponse> {
  const params = new URLSearchParams();
  params.set("user_id", userId);
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  return request<SessionListResponse>(`/conversation/sessions?${params.toString()}`);
}

export async function refreshResearch(
  sessionId: string,
  userId?: string | null,
  query?: string,
): Promise<ResearchRefreshResponse> {
  const clientId = getClientId();
  return request<ResearchRefreshResponse>(`/conversation/${sessionId}/research`, {
    method: "POST",
    body: JSON.stringify({
      user_id: userId ?? undefined,
      query,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function deleteConversationSession(
  sessionId: string,
  userId?: string | null,
): Promise<{ status: string }> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<{ status: string }>(`/conversation/${sessionId}${suffix}`, {
    method: "DELETE",
  });
}

export async function runSimulation(
  query: string,
  products: SimulationProduct[],
  userId?: string | null,
  sessionId?: string | null,
): Promise<SimulationRunResponse> {
  const clientId = getClientId();
  return request<SimulationRunResponse>("/simulation/run", {
    method: "POST",
    body: JSON.stringify({
      query,
      products,
      user_id: userId ?? undefined,
      session_id: sessionId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function optimizeSimulation(
  runId: string,
  productId: string,
  tone?: string | null,
  userId?: string | null,
): Promise<SimulationOptimizeResponse> {
  const clientId = getClientId();
  return request<SimulationOptimizeResponse>("/simulation/optimize", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      product_id: productId,
      tone: tone ?? undefined,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function retestSimulation(
  runId: string,
  optimizedProducts: SimulationProduct[],
  userId?: string | null,
): Promise<SimulationRetestResponse> {
  const clientId = getClientId();
  return request<SimulationRetestResponse>("/simulation/retest", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      optimized_products: optimizedProducts,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function listSimulationRuns(
  userId?: string | null,
  limit: number = 20,
): Promise<SimulationRunListResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  params.set("limit", String(limit));
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  return request<SimulationRunListResponse>(`/simulation/runs?${query}`);
}

export async function getSimulationRun(
  runId: string,
  userId?: string | null,
): Promise<SimulationRunDetailResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<SimulationRunDetailResponse>(`/simulation/runs/${runId}${suffix}`);
}

export async function listSimulationLessons(
  userId?: string | null,
  limit: number = 50,
): Promise<SimulationLessonListResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  params.set("limit", String(limit));
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  return request<SimulationLessonListResponse>(`/simulation/lessons?${query}`);
}

export async function updateSimulationTone(
  runId: string,
  tone: string,
  userId?: string | null,
): Promise<{ run_id: string; tone?: string | null }> {
  const clientId = getClientId();
  return request<{ run_id: string; tone?: string | null }>("/simulation/tone", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      tone,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function requestBrandTone(
  runId?: string | null,
  userId?: string | null,
): Promise<{ status: string; message: string }> {
  const clientId = getClientId();
  return request<{ status: string; message: string }>("/simulation/tone/from-brand", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId ?? undefined,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function analyzeEvidence(query: string): Promise<EvidenceAnalyzeResponse> {
  const clientId = getClientId();
  return request<EvidenceAnalyzeResponse>("/evidence/analyze", {
    method: "POST",
    body: JSON.stringify({ query, client_id: clientId ?? undefined }),
  });
}

export async function optimizeRepresentation(
  evidence_products: EvidenceProduct[],
  query?: string,
  tone?: string | null,
): Promise<RepresentationOptimizeResponse> {
  const clientId = getClientId();
  return request<RepresentationOptimizeResponse>("/representation/optimize", {
    method: "POST",
    body: JSON.stringify({
      query,
      evidence_products,
      tone: tone ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function verifyRecommendation(
  query: string,
  evidence_products: EvidenceProduct[],
  optimized?: RepresentationOptimizeResponse["optimized"],
): Promise<RecommendationVerifyResponse> {
  const clientId = getClientId();
  return request<RecommendationVerifyResponse>("/recommendation/verify", {
    method: "POST",
    body: JSON.stringify({
      query,
      evidence_products,
      optimized,
      client_id: clientId ?? undefined,
    }),
  });
}
