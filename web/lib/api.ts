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
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  return request<ConversationResponse>("/conversation/start", {
    method: "POST",
    body: JSON.stringify({ opening_message: message, user_id: userId ?? undefined }),
  });
}

export async function sendConversationMessage(
  sessionId: string,
  message: string,
  userId?: string | null,
): Promise<ConversationResponse> {
  return request<ConversationResponse>(`/conversation/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ message, user_id: userId ?? undefined }),
  });
}

export async function getConversationSnapshot(
  sessionId: string,
  userId?: string | null,
): Promise<ConversationResponse> {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<ConversationResponse>(`/conversation/${sessionId}${query}`);
}

export async function listConversationSessions(
  userId: string,
): Promise<SessionListResponse> {
  return request<SessionListResponse>(
    `/conversation/sessions?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function refreshResearch(
  sessionId: string,
  userId?: string | null,
  query?: string,
): Promise<ResearchRefreshResponse> {
  return request<ResearchRefreshResponse>(`/conversation/${sessionId}/research`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId ?? undefined, query }),
  });
}

export async function deleteConversationSession(
  sessionId: string,
  userId?: string | null,
): Promise<{ status: string }> {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<{ status: string }>(`/conversation/${sessionId}${query}`, {
    method: "DELETE",
  });
}

export async function runSimulation(
  query: string,
  products: SimulationProduct[],
  userId?: string | null,
  sessionId?: string | null,
): Promise<SimulationRunResponse> {
  return request<SimulationRunResponse>("/simulation/run", {
    method: "POST",
    body: JSON.stringify({
      query,
      products,
      user_id: userId ?? undefined,
      session_id: sessionId ?? undefined,
    }),
  });
}

export async function optimizeSimulation(
  runId: string,
  productId: string,
  tone?: string | null,
  userId?: string | null,
): Promise<SimulationOptimizeResponse> {
  return request<SimulationOptimizeResponse>("/simulation/optimize", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      product_id: productId,
      tone: tone ?? undefined,
      user_id: userId ?? undefined,
    }),
  });
}

export async function retestSimulation(
  runId: string,
  optimizedProducts: SimulationProduct[],
  userId?: string | null,
): Promise<SimulationRetestResponse> {
  return request<SimulationRetestResponse>("/simulation/retest", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      optimized_products: optimizedProducts,
      user_id: userId ?? undefined,
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
  const query = params.toString();
  return request<SimulationRunListResponse>(`/simulation/runs?${query}`);
}

export async function getSimulationRun(
  runId: string,
  userId?: string | null,
): Promise<SimulationRunDetailResponse> {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<SimulationRunDetailResponse>(`/simulation/runs/${runId}${query}`);
}

export async function updateSimulationTone(
  runId: string,
  tone: string,
  userId?: string | null,
): Promise<{ run_id: string; tone?: string | null }> {
  return request<{ run_id: string; tone?: string | null }>("/simulation/tone", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      tone,
      user_id: userId ?? undefined,
    }),
  });
}

export async function analyzeEvidence(query: string): Promise<EvidenceAnalyzeResponse> {
  return request<EvidenceAnalyzeResponse>("/evidence/analyze", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function optimizeRepresentation(
  evidence_products: EvidenceProduct[],
  query?: string,
): Promise<RepresentationOptimizeResponse> {
  return request<RepresentationOptimizeResponse>("/representation/optimize", {
    method: "POST",
    body: JSON.stringify({ query, evidence_products }),
  });
}

export async function verifyRecommendation(
  query: string,
  evidence_products: EvidenceProduct[],
  optimized?: RepresentationOptimizeResponse["optimized"],
): Promise<RecommendationVerifyResponse> {
  return request<RecommendationVerifyResponse>("/recommendation/verify", {
    method: "POST",
    body: JSON.stringify({ query, evidence_products, optimized }),
  });
}
