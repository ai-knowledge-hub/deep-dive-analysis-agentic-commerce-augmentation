import {
  AdminBrand,
  AdminBrandListResponse,
  AdminCanonicalAutofillResponse,
  AdminClient,
  AdminClientListResponse,
  AdminClientUser,
  AdminClientUserListResponse,
  AdminPlatformProfileResponse,
  AdminProduct,
  AdminProductListResponse,
  AdminSkillHistoryResponse,
  AdminSkillResponse,
  AnalyticsEventResponse,
  AudienceSegment,
  AudienceSegmentListResponse,
  BrandBeliefListResponse,
  BrandBeliefResponse,
  BrandPredictionAccuracyResponse,
  EvidenceAnalyzeResponse,
  EvidenceProduct,
  EvidenceSignalResponse,
  Experiment,
  ExperimentExecutionStateResponse,
  ExperimentHypothesisListResponse,
  ExperimentListResponse,
  ExperimentMetricListResponse,
  ExperimentRecommendationListResponse,
  ExperimentRunListResponse,
  ExperimentRunResponse,
  ExperimentValidationResponse,
  ExperimentValidationSummaryResponse,
  ExperimentVariant,
  ExperimentVariantListResponse,
  LoopGeneratedVariantResponse,
  LoopMaintenanceRunHistoryResponse,
  LoopMaintenanceRunResponse,
  NextTestRecommendationResponse,
  OverviewChangesResponse,
  OverviewSummaryResponse,
  OverviewTimeseriesResponse,
  QueryBattery,
  QueryBatteryEvalSummaryResponse,
  QueryBatteryListResponse,
  QueryBatteryMetricsResponse,
  QueryBatteryOntologyUpdatesResponse,
  QueryBatteryQuery,
  QueryBatteryQueryListResponse,
  RecommendationVerifyResponse,
  RepresentationOptimizeResponse,
  SimulationAttachResponse,
  SimulationLessonListResponse,
  SimulationOptimizeResponse,
  SimulationProduct,
  SimulationRetestResponse,
  SimulationRunDetailResponse,
  SimulationRunListResponse,
  SimulationRunResponse,
} from "./types";
import { getBrandId, getClientId, getProductId, request } from "./core";

export async function listBatteries(
  userId?: string | null,
  productId?: string | null,
): Promise<QueryBatteryListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (productId) params.set("product_id", productId);
  return request<QueryBatteryListResponse>(`/batteries?${params.toString()}`);
}

export async function listProductsByBrand(
  brandId: string,
  userId?: string | null,
): Promise<{ products: AdminProduct[] }> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  params.set("brand_id", brandId);
  return request<{ products: AdminProduct[] }>(`/products/by-brand?${params.toString()}`);
}

export async function updateProductCopy(
  payload: {
    product_id: string;
    description: string;
    source_url?: string | null;
  },
  userId?: string | null,
): Promise<{ product?: AdminProduct }> {
  const clientId = getClientId();
  return request<{ product?: AdminProduct }>("/products/update-copy", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function getBrand(
  brandId: string,
  userId?: string | null,
): Promise<{ brand?: AdminBrand }> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<{ brand?: AdminBrand }>(`/brands/${brandId}${suffix}`);
}

export async function createBattery(payload: {
  name: string;
  product_id: string;
  brand_id?: string | null;
  purpose?: string | null;
  generation_mode?: string | null;
  status?: string | null;
  user_id?: string | null;
}): Promise<{ battery: QueryBattery }> {
  const clientId = getClientId();
  return request<{ battery: QueryBattery }>("/batteries", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      client_id: clientId ?? undefined,
      brand_id: payload.brand_id ?? undefined,
      purpose: payload.purpose ?? undefined,
      generation_mode: payload.generation_mode ?? undefined,
      status: payload.status ?? undefined,
      user_id: payload.user_id ?? undefined,
    }),
  });
}

export async function updateBattery(
  batteryId: string,
  payload: {
    name?: string | null;
    purpose?: string | null;
    generation_mode?: string | null;
    status?: string | null;
    user_id?: string | null;
  },
): Promise<{ battery: QueryBattery }> {
  const clientId = getClientId();
  return request<{ battery: QueryBattery }>(`/batteries/${batteryId}`, {
    method: "PATCH",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: payload.user_id ?? undefined,
      name: payload.name ?? undefined,
      purpose: payload.purpose ?? undefined,
      generation_mode: payload.generation_mode ?? undefined,
      status: payload.status ?? undefined,
    }),
  });
}

export async function listBatteryQueries(
  batteryId: string,
  userId?: string | null,
): Promise<QueryBatteryQueryListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<QueryBatteryQueryListResponse>(
    `/batteries/${batteryId}/queries?${params.toString()}`,
  );
}

export async function updateBatteryQuery(
  batteryId: string,
  queryId: string,
  payload: {
    query_text?: string | null;
    query_type?: string | null;
    intent_archetype?: string | null;
    constraints?: Record<string, unknown> | null;
    weight?: number | null;
    enabled?: boolean | null;
    user_id?: string | null;
  },
): Promise<{ query: QueryBatteryQuery }> {
  const clientId = getClientId();
  return request<{ query: QueryBatteryQuery }>(
    `/batteries/${batteryId}/queries/${queryId}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        client_id: clientId ?? undefined,
        user_id: payload.user_id ?? undefined,
        query_text: payload.query_text ?? undefined,
        query_type: payload.query_type ?? undefined,
        intent_archetype: payload.intent_archetype ?? undefined,
        constraints: payload.constraints ?? undefined,
        weight: payload.weight ?? undefined,
        enabled: payload.enabled ?? undefined,
      }),
    },
  );
}

export async function deleteBatteryQuery(
  batteryId: string,
  queryId: string,
  userId?: string | null,
): Promise<{ status: string }> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<{ status: string }>(
    `/batteries/${batteryId}/queries/${queryId}?${params.toString()}`,
    { method: "DELETE" },
  );
}

export async function getBatteryMetrics(
  batteryId: string,
  userId?: string | null,
): Promise<QueryBatteryMetricsResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<QueryBatteryMetricsResponse>(
    `/batteries/${batteryId}/metrics?${params.toString()}`,
  );
}

export async function getOverviewSummary(
  scope: "client" | "brand" | "product" = "client",
  rangeDays = 30,
  userId?: string | null,
): Promise<OverviewSummaryResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  params.set("scope", scope);
  params.set("range_days", String(rangeDays));
  return request<OverviewSummaryResponse>(`/overview/summary?${params.toString()}`);
}

export async function getOverviewTimeseries(
  scope: "client" | "brand" | "product" = "client",
  rangeDays = 30,
  userId?: string | null,
): Promise<OverviewTimeseriesResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  params.set("scope", scope);
  params.set("range_days", String(rangeDays));
  return request<OverviewTimeseriesResponse>(
    `/overview/timeseries?${params.toString()}`,
  );
}

export async function getOverviewChanges(
  scope: "client" | "brand" | "product" = "client",
  rangeDays = 30,
  userId?: string | null,
): Promise<OverviewChangesResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  params.set("scope", scope);
  params.set("range_days", String(rangeDays));
  return request<OverviewChangesResponse>(`/overview/changes?${params.toString()}`);
}

export async function getBatteryEvalSummary(
  batteryId: string,
  userId?: string | null,
): Promise<QueryBatteryEvalSummaryResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<QueryBatteryEvalSummaryResponse>(
    `/batteries/${batteryId}/eval-summary?${params.toString()}`,
  );
}

export async function getBatteryOntologyUpdates(
  batteryId: string,
  userId?: string | null,
): Promise<QueryBatteryOntologyUpdatesResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<QueryBatteryOntologyUpdatesResponse>(
    `/batteries/${batteryId}/ontology-updates?${params.toString()}`,
  );
}

export async function generateBatteryQueries(
  batteryId: string,
  payload: {
    source: string;
    seed_queries?: string[];
    seed_features?: string[];
    seed_use_cases?: string[];
    limit?: number;
    user_id?: string | null;
    use_llm?: boolean;
    persist?: boolean;
  },
): Promise<QueryBatteryQueryListResponse> {
  const clientId = getClientId();
  return request<QueryBatteryQueryListResponse>(`/batteries/${batteryId}/generate`, {
    method: "POST",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: payload.user_id ?? undefined,
      source: payload.source,
      seed_queries: payload.seed_queries,
      seed_features: payload.seed_features,
      seed_use_cases: payload.seed_use_cases,
      limit: payload.limit ?? 15,
      use_llm: payload.use_llm ?? undefined,
      persist: payload.persist ?? true,
    }),
  });
}

export async function listBatteryAudienceSegments(
  batteryId: string,
  userId?: string | null,
): Promise<AudienceSegmentListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<AudienceSegmentListResponse>(
    `/batteries/${batteryId}/audience-segments?${params.toString()}`,
  );
}

export async function updateBatteryAudienceSegment(
  batteryId: string,
  segmentId: string,
  payload: {
    active: boolean;
    user_id?: string | null;
  },
): Promise<{ segment: AudienceSegment }> {
  const clientId = getClientId();
  return request<{ segment: AudienceSegment }>(
    `/batteries/${batteryId}/audience-segments/${segmentId}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        client_id: clientId ?? undefined,
        user_id: payload.user_id ?? undefined,
        active: payload.active,
      }),
    },
  );
}

export async function addBatteryQuery(
  batteryId: string,
  payload: {
    query_text: string;
    query_type?: string | null;
    intent_archetype?: string | null;
    constraints?: Record<string, unknown> | null;
    weight?: number | null;
    enabled?: boolean | null;
    user_id?: string | null;
  },
): Promise<{ query: QueryBatteryQuery }> {
  const clientId = getClientId();
  return request<{ query: QueryBatteryQuery }>(`/batteries/${batteryId}/queries`, {
    method: "POST",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: payload.user_id ?? undefined,
      query_text: payload.query_text,
      query_type: payload.query_type ?? undefined,
      intent_archetype: payload.intent_archetype ?? undefined,
      constraints: payload.constraints ?? undefined,
      weight: payload.weight ?? undefined,
      enabled: payload.enabled ?? undefined,
    }),
  });
}

export async function listExperiments(
  userId?: string | null,
  productId?: string | null,
): Promise<ExperimentListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (productId) params.set("product_id", productId);
  return request<ExperimentListResponse>(`/experiments?${params.toString()}`);
}

export async function listBrandBeliefs(
  brandId: string,
  userId?: string | null,
  limit?: number,
): Promise<BrandBeliefListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (typeof limit === "number") params.set("limit", String(limit));
  params.set("brand_id", brandId);
  return request<BrandBeliefListResponse>(`/beliefs?${params.toString()}`);
}

export async function getLatestBrandBelief(
  brandId: string,
  userId?: string | null,
): Promise<BrandBeliefResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  params.set("brand_id", brandId);
  return request<BrandBeliefResponse>(`/beliefs/latest?${params.toString()}`);
}

export async function createExperiment(payload: {
  name: string;
  product_id: string;
  battery_id?: string | null;
  brand_id?: string | null;
  hypothesis?: Record<string, unknown>;
  competitor_policy?: Record<string, unknown>;
  status?: string | null;
  user_id?: string | null;
}): Promise<{ experiment: Experiment }> {
  const clientId = getClientId();
  return request<{ experiment: Experiment }>("/experiments", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      client_id: clientId ?? undefined,
      brand_id: payload.brand_id ?? undefined,
      battery_id: payload.battery_id ?? undefined,
      hypothesis: payload.hypothesis ?? {},
      competitor_policy: payload.competitor_policy ?? {},
      status: payload.status ?? undefined,
      user_id: payload.user_id ?? undefined,
    }),
  });
}

export async function updateExperiment(
  experimentId: string,
  payload: {
    name?: string | null;
    status?: string | null;
    hypothesis?: Record<string, unknown> | null;
    competitor_policy?: Record<string, unknown> | null;
    user_id?: string | null;
  },
): Promise<{ experiment: Experiment }> {
  const clientId = getClientId();
  return request<{ experiment: Experiment }>(`/experiments/${experimentId}`, {
    method: "PATCH",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: payload.user_id ?? undefined,
      name: payload.name ?? undefined,
      status: payload.status ?? undefined,
      hypothesis: payload.hypothesis ?? undefined,
      competitor_policy: payload.competitor_policy ?? undefined,
    }),
  });
}

export async function listExperimentVariants(
  experimentId: string,
  userId?: string | null,
): Promise<ExperimentVariantListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<ExperimentVariantListResponse>(
    `/experiments/${experimentId}/variants?${params.toString()}`,
  );
}

export async function createExperimentVariant(
  experimentId: string,
  payload: {
    label: string;
    type: string;
    payload?: Record<string, unknown>;
    hypothesis_id?: string | null;
    provenance?: Record<string, unknown>;
    user_id?: string | null;
  },
): Promise<{ variant: ExperimentVariant }> {
  const clientId = getClientId();
  return request<{ variant: ExperimentVariant }>(
    `/experiments/${experimentId}/variants`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId ?? undefined,
        user_id: payload.user_id ?? undefined,
        label: payload.label,
        type: payload.type,
        payload: payload.payload ?? {},
        hypothesis_id: payload.hypothesis_id ?? undefined,
        provenance: payload.provenance ?? undefined,
      }),
    },
  );
}

export async function generateExperimentVariants(
  experimentId: string,
  payload: {
    max_candidates?: number;
    user_id?: string | null;
    mode?: "loop_evidence" | "cold_start";
    strategy?: "bottom_up" | "top_down" | "both";
  } = {},
): Promise<LoopGeneratedVariantResponse> {
  const clientId = getClientId();
  return request<LoopGeneratedVariantResponse>(
    `/experiments/${experimentId}/variants/generate`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId ?? undefined,
        user_id: payload.user_id ?? undefined,
        max_candidates: payload.max_candidates ?? 3,
        mode: payload.mode ?? "loop_evidence",
        strategy: payload.strategy ?? "both",
      }),
    },
  );
}

export async function listExperimentRuns(
  experimentId: string,
  userId?: string | null,
  variantId?: string | null,
): Promise<ExperimentRunListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (variantId) params.set("variant_id", variantId);
  return request<ExperimentRunListResponse>(
    `/experiments/${experimentId}/runs?${params.toString()}`,
  );
}

export async function deleteExperimentRun(
  experimentId: string,
  runId: string,
  userId?: string | null,
): Promise<{ deleted: boolean; run_id: string }> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<{ deleted: boolean; run_id: string }>(
    `/experiments/${experimentId}/runs/${runId}?${params.toString()}`,
    { method: "DELETE" },
  );
}

export async function listExperimentMetrics(
  experimentId: string,
  userId?: string | null,
  variantId?: string | null,
): Promise<ExperimentMetricListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (variantId) params.set("variant_id", variantId);
  return request<ExperimentMetricListResponse>(
    `/experiments/${experimentId}/metrics?${params.toString()}`,
  );
}

export async function logExperimentValidation(
  experimentId: string,
  payload: {
    variant_id?: string | null;
    platform?: string | null;
    query_text?: string | null;
    observed_products?: string[];
    observed_winner_variant_id?: string | null;
    observed_position?: number | null;
    notes?: string | null;
    created_at?: string | null;
    user_id?: string | null;
  },
): Promise<ExperimentValidationResponse> {
  const clientId = getClientId();
  return request<ExperimentValidationResponse>(
    `/experiments/${experimentId}/validations`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId ?? undefined,
        user_id: payload.user_id ?? undefined,
        variant_id: payload.variant_id ?? undefined,
        platform: payload.platform ?? undefined,
        query_text: payload.query_text ?? undefined,
        observed_products: payload.observed_products ?? [],
        observed_winner_variant_id: payload.observed_winner_variant_id ?? undefined,
        observed_position: payload.observed_position ?? undefined,
        notes: payload.notes ?? undefined,
        created_at: payload.created_at ?? undefined,
      }),
    },
  );
}

export async function getExperimentValidationSummary(
  experimentId: string,
  userId?: string | null,
): Promise<ExperimentValidationSummaryResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<ExperimentValidationSummaryResponse>(
    `/experiments/${experimentId}/validation-summary?${params.toString()}`,
  );
}

export async function getBrandPredictionAccuracy(
  brandId: string,
  userId?: string | null,
): Promise<BrandPredictionAccuracyResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<BrandPredictionAccuracyResponse>(
    `/brands/${brandId}/prediction-accuracy?${params.toString()}`,
  );
}

export async function logAnalyticsEvent(payload: {
  brand_id?: string | null;
  product_id?: string | null;
  variant_id?: string | null;
  experiment_id?: string | null;
  event_type: string;
  source?: string | null;
  event_timestamp?: string | null;
  metadata?: Record<string, unknown>;
  user_id?: string | null;
}): Promise<AnalyticsEventResponse> {
  const clientId = getClientId();
  return request<AnalyticsEventResponse>("/analytics/events", {
    method: "POST",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: payload.user_id ?? undefined,
      brand_id: payload.brand_id ?? undefined,
      product_id: payload.product_id ?? undefined,
      variant_id: payload.variant_id ?? undefined,
      experiment_id: payload.experiment_id ?? undefined,
      event_type: payload.event_type,
      source: payload.source ?? undefined,
      event_timestamp: payload.event_timestamp ?? undefined,
      metadata: payload.metadata ?? {},
    }),
  });
}

export async function getNextTestRecommendation(
  experimentId: string,
  userId?: string | null,
): Promise<NextTestRecommendationResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<NextTestRecommendationResponse>(
    `/experiments/${experimentId}/next-test?${params.toString()}`,
  );
}

export async function listExperimentRecommendations(
  experimentId: string,
  userId?: string | null,
  limit = 25,
): Promise<ExperimentRecommendationListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  if (limit) params.set("limit", String(limit));
  return request<ExperimentRecommendationListResponse>(
    `/experiments/${experimentId}/recommendations?${params.toString()}`,
  );
}

export async function getExperimentExecutionState(
  experimentId: string,
  userId?: string | null,
): Promise<ExperimentExecutionStateResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<ExperimentExecutionStateResponse>(
    `/experiments/${experimentId}/execution-state?${params.toString()}`,
  );
}

export async function listExperimentHypotheses(
  experimentId: string,
  userId?: string | null,
): Promise<ExperimentHypothesisListResponse> {
  const params = new URLSearchParams();
  const clientId = getClientId();
  if (clientId) params.set("client_id", clientId);
  if (userId) params.set("user_id", userId);
  return request<ExperimentHypothesisListResponse>(
    `/experiments/${experimentId}/hypotheses?${params.toString()}`,
  );
}

export async function runExperiment(
  experimentId: string,
  variantId: string,
  userId?: string | null,
  options?: {
    execution_mode?: "simulation" | "retrieval_backed";
    retrieval_max_results?: number;
  },
): Promise<ExperimentRunResponse> {
  const clientId = getClientId();
  return request<ExperimentRunResponse>(`/experiments/${experimentId}/run`, {
    method: "POST",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: userId ?? undefined,
      variant_id: variantId,
      execution_mode: options?.execution_mode ?? "simulation",
      retrieval_max_results: options?.retrieval_max_results ?? 5,
    }),
  });
}

export async function updateExperimentSchedule(
  experimentId: string,
  payload: {
    enabled: boolean;
    interval_minutes?: number | null;
    user_id?: string | null;
  },
): Promise<{ schedule: { experiment_id: string; next_run_at?: string | null } }> {
  const clientId = getClientId();
  return request<{ schedule: { experiment_id: string; next_run_at?: string | null } }>(
    `/experiments/${experimentId}/schedule`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId ?? undefined,
        user_id: payload.user_id ?? undefined,
        enabled: payload.enabled,
        interval_minutes: payload.interval_minutes ?? undefined,
      }),
    },
  );
}

export async function backfillExperiment(
  experimentId: string,
  userId?: string | null,
): Promise<{
  experiment_id: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
}> {
  const clientId = getClientId();
  return request<{
    experiment_id: string;
    last_run_at?: string | null;
    next_run_at?: string | null;
  }>(`/experiments/${experimentId}/backfill`, {
    method: "POST",
    body: JSON.stringify({
      client_id: clientId ?? undefined,
      user_id: userId ?? undefined,
    }),
  });
}

export async function runSimulation(
  query: string,
  products: SimulationProduct[],
  userId?: string | null,
  sessionId?: string | null,
): Promise<SimulationRunResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  const productId = getProductId();
  return request<SimulationRunResponse>("/simulation/run", {
    method: "POST",
    body: JSON.stringify({
      query,
      products,
      user_id: userId ?? undefined,
      session_id: sessionId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
      product_id: productId ?? undefined,
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
  const brandId = getBrandId();
  return request<SimulationOptimizeResponse>("/simulation/optimize", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      product_id: productId,
      tone: tone ?? undefined,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
    }),
  });
}

export async function retestSimulation(
  runId: string,
  optimizedProducts: SimulationProduct[],
  userId?: string | null,
): Promise<SimulationRetestResponse> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return request<SimulationRetestResponse>("/simulation/retest", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      optimized_products: optimizedProducts,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
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

export async function attachSimulationProduct(
  runId: string,
  productId: string,
  brandId?: string | null,
  userId?: string | null,
): Promise<SimulationAttachResponse> {
  const clientId = getClientId();
  return request<SimulationAttachResponse>("/simulation/attach", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      product_id: productId,
      brand_id: brandId ?? undefined,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
  });
}

export async function updateSimulationTone(
  runId: string,
  tone: string,
  userId?: string | null,
): Promise<{ run_id: string; tone?: string | null }> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return request<{ run_id: string; tone?: string | null }>("/simulation/tone", {
    method: "POST",
    body: JSON.stringify({
      run_id: runId,
      tone,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
    }),
  });
}

export async function requestBrandTone(
  runId?: string | null,
  userId?: string | null,
): Promise<{ status: string; message: string; tone?: string }> {
  const clientId = getClientId();
  const brandId = getBrandId();
  return request<{ status: string; message: string; tone?: string }>(
    "/simulation/tone/from-brand",
    {
    method: "POST",
    body: JSON.stringify({
      run_id: runId ?? undefined,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
      brand_id: brandId ?? undefined,
    }),
    },
  );
}

export async function listAdminClients(
  userId?: string | null,
): Promise<AdminClientListResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<AdminClientListResponse>(`/clients${suffix}`);
}

export async function createAdminClient(
  payload: {
    id: string;
    name: string;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<{ client: AdminClient }> {
  return request<{ client: AdminClient }>("/clients", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
    }),
  });
}

export async function listAdminBrands(
  clientId: string,
  userId?: string | null,
): Promise<AdminBrandListResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<AdminBrandListResponse>(`/clients/${clientId}/brands${suffix}`);
}

export async function createAdminBrand(
  clientId: string,
  payload: {
    id: string;
    name: string;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<{ brand: AdminBrand }> {
  return request<{ brand: AdminBrand }>(`/clients/${clientId}/brands`, {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
    }),
  });
}

export async function listAdminProducts(
  brandId: string,
  userId?: string | null,
): Promise<AdminProductListResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<AdminProductListResponse>(`/brands/${brandId}/products${suffix}`);
}

export async function createAdminProduct(
  brandId: string,
  payload: {
    id: string;
    name: string;
    description?: string;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<{ product: AdminProduct }> {
  return request<{ product: AdminProduct }>(`/brands/${brandId}/products`, {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
    }),
  });
}

export async function updateAdminProduct(
  brandId: string,
  productId: string,
  payload: {
    name?: string;
    description?: string;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<{ product: AdminProduct | null }> {
  return request<{ product: AdminProduct | null }>(
    `/brands/${brandId}/products/${productId}`,
    {
      method: "PUT",
      body: JSON.stringify({
        ...payload,
        user_id: userId ?? undefined,
      }),
    },
  );
}

export async function autofillAdminProductCanonicalSpec(
  brandId: string,
  productId: string,
  payload: {
    mode?: "preview" | "apply";
    source_priority?: string[];
  },
  userId?: string | null,
): Promise<AdminCanonicalAutofillResponse> {
  return request<AdminCanonicalAutofillResponse>(
    `/brands/${brandId}/products/${productId}/canonical-spec/autofill`,
    {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        user_id: userId ?? undefined,
      }),
    },
  );
}

export async function listAdminClientUsers(
  clientId: string,
  userId?: string | null,
): Promise<AdminClientUserListResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<AdminClientUserListResponse>(`/clients/${clientId}/users${suffix}`);
}

export async function addAdminClientUser(
  clientId: string,
  payload: {
    member_user_id: string;
    role?: string;
  },
  userId?: string | null,
): Promise<{ user: AdminClientUser }> {
  return request<{ user: AdminClientUser }>(`/clients/${clientId}/users`, {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
    }),
  });
}

export async function getAdminPlatformProfile(
  userId?: string | null,
): Promise<AdminPlatformProfileResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<AdminPlatformProfileResponse>(`/platform-profile${suffix}`);
}

export async function updateAdminPlatformProfile(
  payload: {
    name: string;
    version: string;
    profile: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<AdminPlatformProfileResponse> {
  return request<AdminPlatformProfileResponse>("/platform-profile", {
    method: "PUT",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
    }),
  });
}

export async function getAdminSkill(
  name: string,
  userId?: string | null,
): Promise<AdminSkillResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<AdminSkillResponse>(`/skills/${name}${suffix}`);
}

export async function updateAdminSkill(
  name: string,
  payload: {
    description: string;
    version: string;
    content: string;
    enabled: boolean;
    metadata?: Record<string, unknown>;
  },
  userId?: string | null,
): Promise<AdminSkillResponse> {
  return request<AdminSkillResponse>(`/skills/${name}`, {
    method: "PUT",
    body: JSON.stringify({
      ...payload,
      name,
      user_id: userId ?? undefined,
    }),
  });
}

export async function listAdminSkillHistory(
  name: string,
  userId?: string | null,
  limit: number = 10,
): Promise<AdminSkillHistoryResponse> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  if (limit) params.set("limit", String(limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<AdminSkillHistoryResponse>(`/skills/${name}/history${suffix}`);
}

export async function runAdminLoopMaintenance(
  payload: {
    client_id?: string;
    lookback_days?: number;
    min_confidence?: number;
  },
  userId?: string | null,
): Promise<LoopMaintenanceRunResponse> {
  return request<LoopMaintenanceRunResponse>("/ops/loop-maintenance", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
    }),
  });
}

export async function listAdminLoopMaintenanceRuns(
  payload: {
    client_id: string;
    limit?: number;
  },
  userId?: string | null,
): Promise<LoopMaintenanceRunHistoryResponse> {
  const params = new URLSearchParams();
  params.set("client_id", payload.client_id);
  if (payload.limit) params.set("limit", String(payload.limit));
  if (userId) params.set("user_id", userId);
  return request<LoopMaintenanceRunHistoryResponse>(
    `/ops/loop-maintenance/history?${params.toString()}`,
  );
}

export async function analyzeEvidence(query: string): Promise<EvidenceAnalyzeResponse> {
  const clientId = getClientId();
  return request<EvidenceAnalyzeResponse>("/evidence/analyze", {
    method: "POST",
    body: JSON.stringify({ query, client_id: clientId ?? undefined }),
  });
}

export async function extractEvidenceSignals(
  payload: {
    goal: string;
    product: { id?: string; name?: string; description?: string };
    winner?: { id?: string; name?: string; description?: string };
  },
  userId?: string | null,
): Promise<EvidenceSignalResponse> {
  const clientId = getClientId();
  return request<EvidenceSignalResponse>("/evidence/signals", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      user_id: userId ?? undefined,
      client_id: clientId ?? undefined,
    }),
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
