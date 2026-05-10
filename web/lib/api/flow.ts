import {
  AdminLLMConfigResponse,
  AdminProduct,
  AgentAction,
  AgentRunEventListResponse,
  AgentRunControlResponse,
  AgentRunCreateResponse,
  AgentRunDetailResponse,
  AgentRunListResponse,
  AgentRunCommandResponse,
  AgentRunCommandPreflightResponse,
  AgentRunCommandType,
  ExternalAgentJobOperatorDetail,
  AgentRegistryApprovalReceiptVerifyResponse,
  AgentRegistryAuditListResponse,
  AgentRegistryOwnershipUpdateResponse,
  AgentRegistryPinBackfillResponse,
  AgentRegistryReleaseDetailResponse,
  AgentRegistryReleaseListResponse,
  AgentRuntimeRegistryResponse,
  ConversationResponse,
  CopyRevisionListResponse,
  CopyRevisionResponse,
  HealthLLMResponse,
  LLMConfigSummaryResponse,
  ResearchRefreshResponse,
  SessionListResponse,
  SessionSummary,
  ValidationJobListResponse,
  ValidationJobResponse,
  ValidationProviderRunResponse,
} from "./types";
import {
  StreamHandlers,
  getBrandId,
  getClientId,
  getSessionsStorageKey,
  readCachedSessions,
  request,
  requestStream,
  requestStreamWithEvents,
  writeCachedSessions,
} from "./core";

export async function startConversation(
  message: string,
  userId?: string | null,
  metadata?: Record<string, unknown>,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return request<ConversationResponse>("/conversation/start", {
    method: "POST",
    body: JSON.stringify({
      opening_message: message,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
      metadata: metadata ?? undefined,
    }),
  });
}

export async function startConversationStream(
  message: string,
  userId?: string | null,
  metadata?: Record<string, unknown>,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return requestStream<ConversationResponse>("/conversation/start/stream", {
    method: "POST",
    body: JSON.stringify({
      opening_message: message,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
      metadata: metadata ?? undefined,
    }),
  });
}

export async function startConversationStreamWithEvents(
  message: string,
  userId: string | null | undefined,
  metadata: Record<string, unknown> | undefined,
  handlers: StreamHandlers<ConversationResponse>,
  signal?: AbortSignal,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return requestStreamWithEvents<ConversationResponse>(
    "/conversation/start/stream",
    {
      method: "POST",
      signal,
      body: JSON.stringify({
        opening_message: message,
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
        brand_id: brandId ?? undefined,
        metadata: metadata ?? undefined,
      }),
    },
    handlers,
  );
}

export async function sendConversationMessage(
  sessionId: string,
  message: string,
  userId?: string | null,
  metadata?: Record<string, unknown>,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return request<ConversationResponse>(`/conversation/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({
      message,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
      metadata: metadata ?? undefined,
    }),
  });
}

export async function sendConversationMessageStreamWithEvents(
  sessionId: string,
  message: string,
  userId: string | null | undefined,
  metadata: Record<string, unknown> | undefined,
  handlers: StreamHandlers<ConversationResponse>,
  signal?: AbortSignal,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return requestStreamWithEvents<ConversationResponse>(
    `/conversation/${sessionId}/stream`,
    {
      method: "POST",
      signal,
      body: JSON.stringify({
        message,
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
        brand_id: brandId ?? undefined,
        metadata: metadata ?? undefined,
      }),
    },
    handlers,
  );
}

export async function sendConversationMessageStream(
  sessionId: string,
  message: string,
  userId?: string | null,
  metadata?: Record<string, unknown>,
): Promise<ConversationResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return requestStream<ConversationResponse>(`/conversation/${sessionId}/stream`, {
    method: "POST",
    body: JSON.stringify({
      message,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
      metadata: metadata ?? undefined,
    }),
  });
}

export async function getConversationSnapshot(
  sessionId: string,
  userId?: string | null,
  clientIdOverride?: string | null,
): Promise<ConversationResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = clientIdOverride ?? getClientId();
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
  const cacheKey = getSessionsStorageKey(userId, clientId);
  const cached = readCachedSessions(cacheKey);
  try {
    const response = await request<SessionListResponse>(
      `/conversation/sessions?${params.toString()}`,
    );
    const merged = new Map<string, SessionSummary>();
    response.sessions.forEach((session) => merged.set(session.id, session));
    cached.forEach((session) => {
      if (!merged.has(session.id)) {
        merged.set(session.id, session);
      }
    });
    const sessions = Array.from(merged.values());
    writeCachedSessions(cacheKey, sessions);
    return { sessions };
  } catch (error) {
    if (cached.length > 0) {
      return { sessions: cached };
    }
    throw error;
  }
}

export async function refreshResearch(
  sessionId: string,
  userId?: string | null,
  query?: string,
): Promise<ResearchRefreshResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return request<ResearchRefreshResponse>(`/conversation/${sessionId}/research`, {
    method: "POST",
    body: JSON.stringify({
      user_id: userId ?? undefined,
      query,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
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

export async function deleteSimulationRun(
  runId: string,
  userId?: string | null,
  clientIdOverride?: string | null,
): Promise<{ deleted: boolean; run_id: string }> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = clientIdOverride ?? getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<{ deleted: boolean; run_id: string }>(
    `/simulation/runs/${runId}${suffix}`,
    {
      method: "DELETE",
    },
  );
}

export async function deleteExperiment(
  experimentId: string,
  userId?: string | null,
  clientIdOverride?: string | null,
): Promise<{ deleted: boolean; experiment_id: string }> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = clientIdOverride ?? getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<{ deleted: boolean; experiment_id: string }>(
    `/experiments/${experimentId}${suffix}`,
    {
      method: "DELETE",
    },
  );
}

export async function createValidationJob(
  payload: {
    entity_type: "experiment_run" | "simulation_run" | "battery" | "copy_revision";
    entity_id: string;
    provider: string;
    mode:
      | "in_app"
      | "external"
      | "in_app_byok"
      | "provider_openai_mcp"
      | "provider_gemini_function"
      | "manual_fallback";
    model?: string | null;
    prompt_version?: string | null;
    input_payload: Record<string, unknown>;
    brand_id?: string | null;
    product_id?: string | null;
  },
  userId?: string | null,
): Promise<ValidationJobResponse> {
  const clientId = getClientId();
  return request<ValidationJobResponse>("/validation/jobs", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function runValidationJob(
  jobId: string,
  userId?: string | null,
): Promise<ValidationJobResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  return request<ValidationJobResponse>(
    `/validation/jobs/${jobId}/run${query ? `?${query}` : ""}`,
    { method: "POST" },
  );
}

export async function submitValidationExternal(
  jobId: string,
  payload: {
    provider?: string | null;
    model?: string | null;
    structured_result: Record<string, unknown>;
    raw_response?: string | null;
  },
  userId?: string | null,
): Promise<ValidationJobResponse> {
  const clientId = getClientId();
  return request<ValidationJobResponse>(`/validation/jobs/${jobId}/external`, {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function startValidationProviderRun(
  jobId: string,
  payload: {
    callback_url?: string | null;
    return_url?: string | null;
  } = {},
  userId?: string | null,
): Promise<ValidationProviderRunResponse> {
  const clientId = getClientId();
  return request<ValidationProviderRunResponse>(
    `/validation/jobs/${jobId}/start-provider-run`,
    {
      method: "POST",
      body: JSON.stringify({
        callback_url: payload.callback_url ?? undefined,
        return_url: payload.return_url ?? undefined,
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
      }),
    },
  );
}

export async function submitValidationProviderCallback(
  jobId: string,
  payload: {
    provider?: string | null;
    model?: string | null;
    provider_run_id?: string | null;
    callback_verified?: boolean;
    callback_signature?: string | null;
    structured_result: Record<string, unknown>;
    raw_response?: string | null;
  },
  userId?: string | null,
): Promise<ValidationJobResponse> {
  const clientId = getClientId();
  return request<ValidationJobResponse>(
    `/validation/jobs/${jobId}/provider-callback`,
    {
      method: "POST",
      body: JSON.stringify({
        provider: payload.provider ?? undefined,
        model: payload.model ?? undefined,
        provider_run_id: payload.provider_run_id ?? undefined,
        callback_verified: payload.callback_verified ?? false,
        callback_signature: payload.callback_signature ?? undefined,
        structured_result: payload.structured_result,
        raw_response: payload.raw_response ?? undefined,
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
      }),
    },
  );
}

export async function getValidationJob(
  jobId: string,
  userId?: string | null,
): Promise<ValidationJobResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  return request<ValidationJobResponse>(
    `/validation/jobs/${jobId}${query ? `?${query}` : ""}`,
  );
}

export async function listValidationJobs(
  payload: {
    entity_type?: "experiment_run" | "simulation_run" | "battery" | "copy_revision";
    entity_id?: string;
    limit?: number;
  },
  userId?: string | null,
): Promise<ValidationJobListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.entity_type) params.set("entity_type", payload.entity_type);
  if (payload.entity_id) params.set("entity_id", payload.entity_id);
  if (payload.limit) params.set("limit", String(payload.limit));
  return request<ValidationJobListResponse>(
    `/validation/jobs?${params.toString()}`,
  );
}

export async function listCopyRevisions(
  payload: {
    user_id?: string | null;
    product_id?: string | null;
    source_type?: string | null;
    status?: string | null;
    limit?: number;
  } = {},
): Promise<CopyRevisionListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (payload.user_id) params.set("user_id", payload.user_id);
  if (payload.product_id) params.set("product_id", payload.product_id);
  if (payload.source_type) params.set("source_type", payload.source_type);
  if (payload.status) params.set("status", payload.status);
  if (payload.limit) params.set("limit", String(payload.limit));
  return request<CopyRevisionListResponse>(`/copy-revisions?${params.toString()}`);
}

export async function getCopyRevision(
  revisionId: string,
  userId?: string | null,
): Promise<CopyRevisionResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  return request<CopyRevisionResponse>(
    `/copy-revisions/${revisionId}${query ? `?${query}` : ""}`,
  );
}

export async function publishCopyRevision(
  revisionId: string,
  payload: { user_id?: string | null; notes?: string | null } = {},
): Promise<{ revision: CopyRevisionResponse["revision"]; product: AdminProduct | null }> {
  const clientId = getClientId();
  return request<{ revision: CopyRevisionResponse["revision"]; product: AdminProduct | null }>(
    `/copy-revisions/${revisionId}/publish`,
    {
      method: "POST",
      body: JSON.stringify({
        user_id: payload.user_id ?? undefined,
        client_id: clientId ?? undefined,
        notes: payload.notes ?? undefined,
      }),
    },
  );
}

export async function createAgentRun(
  payload: {
    brand_id?: string | null;
    product_id?: string | null;
    experiment_id?: string | null;
    objective?: Record<string, unknown>;
    allowed_capabilities?: string[];
    capability_versions?: Record<string, unknown>;
    budgets?: Record<string, unknown>;
    approval_policy?: Record<string, unknown>;
    requires_approval?: boolean;
    run_mode?: "plan_only" | "auto_execute_safe";
    state?: string | null;
    status?: string | null;
  },
  userId?: string | null,
): Promise<AgentRunCreateResponse> {
  const clientId = getClientId();
  return request<AgentRunCreateResponse>("/agent-runs", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function listAgentRuns(
  payload: {
    experiment_id?: string | null;
    product_id?: string | null;
    status?: string | null;
    limit?: number;
  } = {},
  userId?: string | null,
): Promise<AgentRunListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.experiment_id) params.set("experiment_id", payload.experiment_id);
  if (payload.product_id) params.set("product_id", payload.product_id);
  if (payload.status) params.set("status", payload.status);
  if (payload.limit) params.set("limit", String(payload.limit));
  return request<AgentRunListResponse>(
    `/agent-runs?${params.toString()}`,
  );
}

export async function getAgentRun(
  runId: string,
  payload: { limit?: number } = {},
  userId?: string | null,
): Promise<AgentRunDetailResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.limit) params.set("limit", String(payload.limit));
  return request<AgentRunDetailResponse>(
    `/agent-runs/${runId}${params.toString() ? `?${params.toString()}` : ""}`,
  );
}

export async function getAgentRunEvents(
  runId: string,
  payload: {
    limit?: number;
    event_type?: "all" | "failed" | "policy" | "executed" | "command";
    status?: "all" | "proposed" | "approved" | "executing" | "executed" | "failed" | "rejected";
    capability_name?: string | null;
    since?: string | null;
    until?: string | null;
    before?: string | null;
    after?: string | null;
    event_id?: string | null;
    around?: number;
  } = {},
  userId?: string | null,
): Promise<AgentRunEventListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.limit) params.set("limit", String(payload.limit));
  if (payload.event_type) params.set("event_type", payload.event_type);
  if (payload.status) params.set("status", payload.status);
  if (payload.capability_name) params.set("capability_name", payload.capability_name);
  if (payload.since) params.set("since", payload.since);
  if (payload.until) params.set("until", payload.until);
  if (payload.before) params.set("before", payload.before);
  if (payload.after) params.set("after", payload.after);
  if (payload.event_id) params.set("event_id", payload.event_id);
  if (payload.around) params.set("around", String(payload.around));
  return request<AgentRunEventListResponse>(
    `/agent-runs/${runId}/events${params.toString() ? `?${params.toString()}` : ""}`,
  );
}

export async function getExternalAgentJobForRun(
  runId: string,
  userId?: string | null,
): Promise<ExternalAgentJobOperatorDetail> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<ExternalAgentJobOperatorDetail>(
    `/external-agent/jobs/operator/by-run/${runId}${
      params.toString() ? `?${params.toString()}` : ""
    }`,
  );
}

export async function verifyExternalAgentJobReceiptForRun(
  runId: string,
  userId?: string | null,
): Promise<ExternalAgentJobOperatorDetail["verification"]> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<ExternalAgentJobOperatorDetail["verification"]>(
    `/external-agent/jobs/operator/by-run/${runId}/receipt/verify${
      params.toString() ? `?${params.toString()}` : ""
    }`,
    { method: "POST" },
  );
}

export async function listAgentRuntimeRegistry(
  userId?: string | null,
): Promise<AgentRuntimeRegistryResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<AgentRuntimeRegistryResponse>(
    `/agent-runs/registry${params.toString() ? `?${params.toString()}` : ""}`,
  );
}

export async function listAgentRuntimeRegistryAudit(
  payload: { registry_fingerprint?: string | null; limit?: number } = {},
  userId?: string | null,
): Promise<AgentRegistryAuditListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.registry_fingerprint) {
    params.set("registry_fingerprint", payload.registry_fingerprint);
  }
  if (payload.limit) params.set("limit", String(payload.limit));
  return request<AgentRegistryAuditListResponse>(
    `/agent-runs/registry/audit${params.toString() ? `?${params.toString()}` : ""}`,
  );
}

export async function listAgentRuntimeRegistryReleases(
  payload: { status?: "active" | "retired" | string | null; limit?: number } = {},
  userId?: string | null,
): Promise<AgentRegistryReleaseListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.status) params.set("status", payload.status);
  if (payload.limit) params.set("limit", String(payload.limit));
  return request<AgentRegistryReleaseListResponse>(
    `/agent-runs/registry/releases${params.toString() ? `?${params.toString()}` : ""}`,
  );
}

export async function getAgentRuntimeRegistryRelease(
  registryFingerprint: string,
  payload: { audit_limit?: number } = {},
  userId?: string | null,
): Promise<AgentRegistryReleaseDetailResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (payload.audit_limit) params.set("audit_limit", String(payload.audit_limit));
  return request<AgentRegistryReleaseDetailResponse>(
    `/agent-runs/registry/releases/${encodeURIComponent(registryFingerprint)}${
      params.toString() ? `?${params.toString()}` : ""
    }`,
  );
}

export async function updateAgentRuntimeRegistryOwnership(
  toolId: string,
  payload: {
    owner_principal_id: string;
    steward_team: string;
    dry_run?: boolean;
    preflight_confirmed?: boolean;
  },
  userId?: string | null,
): Promise<AgentRegistryOwnershipUpdateResponse> {
  return request<AgentRegistryOwnershipUpdateResponse>(
    `/agent-runs/registry/ownership/${encodeURIComponent(toolId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        user_id: userId ?? undefined,
        owner_principal_id: payload.owner_principal_id,
        steward_team: payload.steward_team,
        dry_run: payload.dry_run ?? true,
        preflight_confirmed: payload.preflight_confirmed ?? false,
      }),
    },
  );
}

export async function verifyAgentRuntimeRegistryApprovalReceipt(
  payload: {
    approval_receipt: Record<string, unknown>;
    registry_fingerprint?: string | null;
    audit_event_id?: string | null;
    require_audit_event?: boolean;
  },
): Promise<AgentRegistryApprovalReceiptVerifyResponse> {
  return request<AgentRegistryApprovalReceiptVerifyResponse>(
    "/agent-runs/registry/approval-receipts/verify",
    {
      method: "POST",
      body: JSON.stringify({
        approval_receipt: payload.approval_receipt,
        registry_fingerprint: payload.registry_fingerprint ?? undefined,
        audit_event_id: payload.audit_event_id ?? undefined,
        require_audit_event: payload.require_audit_event ?? false,
      }),
    },
  );
}

export async function backfillAgentRuntimeRegistryPins(
  payload: { dry_run?: boolean; limit?: number } = {},
  userId?: string | null,
): Promise<AgentRegistryPinBackfillResponse> {
  const clientId = getClientId();
  return request<AgentRegistryPinBackfillResponse>("/agent-runs/registry/backfill-pins", {
    method: "POST",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: userId ?? undefined,
      dry_run: payload.dry_run ?? true,
      limit: payload.limit ?? 200,
    }),
  });
}

export async function decideAgentAction(
  actionId: string,
  payload: { decision: "approve" | "reject" },
  userId?: string | null,
): Promise<{ action: AgentAction }> {
  const clientId = getClientId();
  return request<{ action: AgentAction }>(
    `/agent-runs/actions/${actionId}/decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: payload.decision,
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
      }),
    },
  );
}

export async function controlAgentRun(
  runId: string,
  action: "start" | "pause" | "cancel" | "step",
  userId?: string | null,
): Promise<AgentRunControlResponse> {
  const clientId = getClientId();
  return request<AgentRunControlResponse>(
    `/agent-runs/${runId}/${action}`,
    {
      method: "POST",
      body: JSON.stringify({
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
      }),
    },
  );
}

export async function issueAgentRunCommand(
  runId: string,
  payload: {
    command_type: AgentRunCommandType;
    action_id?: string | null;
    message?: string | null;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<AgentRunCommandResponse> {
  const clientId = getClientId();
  return request<AgentRunCommandResponse>(`/agent-runs/${runId}/commands`, {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function preflightAgentRunCommand(
  runId: string,
  payload: {
    command_type: AgentRunCommandType;
    action_id?: string | null;
    message?: string | null;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<AgentRunCommandPreflightResponse> {
  const clientId = getClientId();
  return request<AgentRunCommandPreflightResponse>(
    `/agent-runs/${runId}/commands/preflight`,
    {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        user_id: userId ?? undefined,
        client_id: clientId ?? undefined,
      }),
    },
  );
}

export async function getHealthLLM(): Promise<HealthLLMResponse> {
  return request<HealthLLMResponse>("/health/llm");
}

export async function getLlmConfig(userId?: string): Promise<LLMConfigSummaryResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  return request<LLMConfigSummaryResponse>(`/llm/config?${params.toString()}`);
}

export async function getAdminLlmConfig(
  userId: string,
): Promise<AdminLLMConfigResponse> {
  const params = new URLSearchParams();
  params.set("user_id", userId);
  return request<AdminLLMConfigResponse>(`/llm/config?${params.toString()}`);
}

export async function updateAdminLlmConfig(
  provider: string,
  payload: {
    user_id: string;
    api_key?: string;
    validation_api_key?: string;
    model?: string;
    validation_model?: string;
    activate?: boolean;
  },
): Promise<AdminLLMConfigResponse> {
  const response = await request<{ summary: AdminLLMConfigResponse }>(
    `/llm/config/${provider}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
  return response.summary;
}

export async function activateAdminLlmProvider(
  payload: { user_id: string; provider: string; model?: string },
): Promise<AdminLLMConfigResponse> {
  const response = await request<{ summary: AdminLLMConfigResponse }>(
    "/llm/config/activate",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return response.summary;
}
