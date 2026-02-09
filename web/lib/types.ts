export type GoalClarificationState = {
  query: string;
  turns: { speaker: string; content: string }[];
  extracted_goals: string[];
  ready_for_products: boolean;
  metadata: Record<string, unknown>;
};

export type Product = {
  id: string;
  name: string;
  brand_id?: string;
  price?: number;
  confidence?: number;
  source?: string;
  merchant_name?: string;
  offer_url?: string;
  capabilities_enabled?: string[];
  alignment_score?: number;
  alignment_reasoning?: string;
  low_confidence?: boolean;
  description?: string;
  intentionality_profile?: {
    product_id?: string;
    capabilities_enabled?: string[];
    goals_served?: string[];
    prerequisites?: string[];
    outcomes_expected?: string[];
    context_fit?: Record<string, number>;
  };
  reasoning?: string;
};

export type EvidenceProduct = {
  id: string;
  name: string;
  description: string;
  source: string;
  url?: string;
  price?: number;
  confidence?: number;
  raw_text?: string;
  metadata?: Record<string, unknown>;
};

export type EvidenceAnalyzeResponse = {
  intent?: ConversationResponse["intent"];
  goals: string[];
  evidence_products: EvidenceProduct[];
  signal_extraction?: EvidenceSignalExtraction;
  profiles: {
    product_id?: string;
    capabilities_enabled?: string[];
    goals_served?: string[];
    prerequisites?: string[];
    outcomes_expected?: string[];
    context_fit?: Record<string, number>;
  }[];
  alignment_scores: {
    product_id: string;
    score: number;
    matched_capabilities?: string[];
    alignment_reasoning?: string;
    confidence?: number;
    low_confidence?: boolean;
  }[];
};

export type RepresentationOptimizeResponse = {
  intent?: ConversationResponse["intent"];
  goals: string[];
  optimized: {
    id: string;
    name: string;
    before: string;
    after: string;
    capabilities: string[];
    outcomes: string[];
    goals: string[];
  }[];
  alignment_deltas: {
    product_id: string;
    before: number;
    after: number;
    delta: number;
  }[];
};

export type RecommendationVerifyResponse = {
  intent?: ConversationResponse["intent"];
  goals: string[];
  predicted: string[];
  actual: string[];
  lift: number;
  baseline_alignment: {
    product_id: string;
    score: number;
  }[];
  optimized_alignment: {
    product_id: string;
    score: number;
  }[];
};

export type SimulationProduct = {
  id: string;
  name: string;
  description: string;
  source?: string;
  brand_id?: string;
  url?: string;
  price?: number;
  confidence?: number;
  metadata?: Record<string, unknown>;
};

export type SimulationGapReport = {
  product_id: string;
  goal: string;
  score: number;
  matched_signals: string[];
  missing_signals: string[];
  severity: string;
  summary: string;
  winner_id?: string | null;
  winner_signals?: string[];
  competitor_summary?: string | null;
};

export type ProtocolReadinessIssue = {
  field: string;
  severity: "info" | "warning" | "error";
  message: string;
  fix?: string | null;
};

export type ProtocolReadinessReport = {
  product_id: string;
  protocol: "ucp" | "acp";
  issues: ProtocolReadinessIssue[];
};

export type OverviewSummaryResponse = {
  scope: string;
  range_days: number;
  kpis: {
    experiments: {
      latest_win_rate?: number | null;
      latest_avg_score?: number | null;
      last_updated?: string | null;
    };
    validation: {
      accuracy?: number | null;
      verified_runs?: number | null;
      required_runs?: number | null;
      unlock_ready?: boolean | null;
    };
    simulation: {
      avg_lift?: number | null;
      runs?: number | null;
      lessons?: number | null;
    };
    evidence: {
      avg_lift?: number | null;
      evidence_items?: number | null;
    };
    battery_health: {
      enabled_queries?: number | null;
      redundancy_rate?: number | null;
      coverage_score?: number | null;
    };
    protocol_readiness: {
      score?: number | null;
    };
  };
};

export type OverviewTimeseriesResponse = {
  range_days: number;
  series: {
    win_rate: { date: string; value: number }[];
    avg_score: { date: string; value: number }[];
    validation_accuracy: { date: string; value: number }[];
    simulation_lift: { date: string; value: number }[];
    evidence_lift: { date: string; value: number }[];
    belief_count: { date: string; value: number }[];
  };
};

export type OverviewChangesResponse = {
  latest_experiment: {
    id?: string | null;
    name?: string | null;
    winner_label?: string | null;
    lift?: number | null;
    created_at?: string | null;
  } | null;
  latest_simulation_lesson:
    | {
        summary?: string | null;
        confidence?: number | null;
        created_at?: string | null;
      }
    | null;
  top_gap_signals: { signal: string; count: number }[];
  next_test: Record<string, unknown> | null;
};

export type SimulationRunResponse = {
  run_id: string;
  result: {
    intent?: ConversationResponse["intent"];
    goals: string[];
    scores: {
      product_id: string;
      score: number;
      alignment_reasoning?: string;
      matched_capabilities?: string[];
      confidence?: number;
      low_confidence?: boolean;
    }[];
    winner_id?: string | null;
    scores_keyword?: {
      product_id: string;
      score: number;
      alignment_reasoning?: string;
      matched_capabilities?: string[];
      confidence?: number;
      low_confidence?: boolean;
    }[];
    winner_id_keyword?: string | null;
    gap_analysis: SimulationGapReport[];
    profiles: {
      product_id?: string;
      capabilities_enabled?: string[];
      goals_served?: string[];
      prerequisites?: string[];
      outcomes_expected?: string[];
      context_fit?: Record<string, number>;
    }[];
    lessons?: string[];
    tone?: {
      summary: string;
      markers?: Record<string, string | number>;
    };
    protocol_readiness?: ProtocolReadinessReport[];
  };
};

export type SimulationOptimizeResponse = {
  run_id: string;
  optimized: {
    id: string;
    name: string;
    before: string;
    after: string;
  };
  gap: SimulationGapReport;
  copy_revision?: CopyRevision;
};

export type SimulationRetestResponse = {
  run_id: string;
  result: SimulationRunResponse["result"];
};

export type SimulationRunSummary = {
  id: string;
  query: string;
  created_at?: string;
  winner_id?: string | null;
  protocol_readiness_score?: number | null;
  brand_id?: string | null;
  product_id?: string | null;
};

export type SimulationRunListResponse = {
  runs: SimulationRunSummary[];
};

export type SimulationRunDetailResponse = {
  run: {
    id: string;
    query: string;
    created_at?: string;
    brand_id?: string | null;
    product_id?: string | null;
    products: SimulationProduct[];
    scenario?: Record<string, unknown>;
    result: SimulationRunResponse["result"];
    retest?: SimulationRunResponse["result"] | null;
  };
};

export type AdminPlatformProfile = {
  id: string;
  name: string;
  version: string;
  profile: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

export type AdminPlatformProfileResponse = {
  profile: AdminPlatformProfile;
};

export type AdminSkill = {
  id: string;
  name: string;
  description: string;
  version: string;
  content: string;
  enabled: boolean;
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

export type AdminSkillResponse = {
  skill: AdminSkill | null;
};

export type AdminSkillHistoryItem = {
  id: number;
  skill_id: string;
  name: string;
  description?: string;
  version?: string;
  content: string;
  enabled: boolean;
  metadata?: Record<string, unknown>;
  changed_at?: string;
};

export type AdminSkillHistoryResponse = {
  history: AdminSkillHistoryItem[];
};

export type SimulationAttachResponse = {
  run_id: string;
  product_id?: string | null;
  brand_id?: string | null;
};

export type SimulationLesson = {
  id: number;
  run_id: string;
  user_id?: string | null;
  lesson: string;
  created_at?: string;
};

export type SimulationLessonListResponse = {
  lessons: SimulationLesson[];
};

export type AdminClient = {
  id: string;
  name: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type AdminBrand = {
  id: string;
  client_id: string;
  name: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type AdminProduct = {
  id: string;
  brand_id: string;
  name: string;
  description?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type AdminClientUser = {
  id: number;
  client_id: string;
  user_id: string;
  role?: string | null;
  created_at?: string;
};

export type AdminClientListResponse = {
  clients: AdminClient[];
};

export type AdminBrandListResponse = {
  brands: AdminBrand[];
};

export type AdminProductListResponse = {
  products: AdminProduct[];
};

export type AdminClientUserListResponse = {
  users: AdminClientUser[];
};

export type AdminCanonicalAutofillResult = {
  product_id: string;
  canonical_spec: Record<string, unknown>;
  raw: Record<string, unknown>;
  normalized: Record<string, unknown>;
  mapping: Record<string, unknown>;
  product?: AdminProduct | null;
};

export type AdminCanonicalAutofillResponse = {
  result: AdminCanonicalAutofillResult;
};

export type EvidenceSignalExtraction = {
  intent_signals: string[];
  winner_signals: string[];
  missing_signals: string[];
};

export type EvidenceSignalResponse = {
  signals: EvidenceSignalExtraction;
};

export type ConversationResponse = {
  session_id: string;
  user_id: string;
  snapshot?: {
    session: {
      id: string;
      user_id?: string;
      created_at?: string;
      state?: Record<string, unknown>;
    };
    turns?: {
      id?: number;
      session_id?: string;
      speaker: "user" | "agent";
      content: string;
      created_at?: string;
      metadata?: Record<string, unknown>;
    }[];
    goals?: string[];
    semantic_goals?: string[];
    latest_episode?: Record<string, unknown> | null;
  };
  intent?: {
    primary_goal?: string;
    secondary_goals?: string[];
    underlying_needs?: string[];
    context_signals?: string[];
    confidence?: number;
    domain?: string;
  };
  baseline_alignment?: number;
  plan?: {
    query?: string;
    products?: Product[];
    research_results?: Product[];
    clarifications?: string[];
    alignment?: {
      goal_alignment?: {
        score?: number;
        baseline_score?: number;
        aligned_goals?: string[];
        misaligned_goals?: string[];
      };
      research?: {
        per_item?: {
          product_id?: string;
          score?: number;
          alignment_reasoning?: string;
        }[];
      };
    };
  };
  clarification?: string;
  goal_state?: GoalClarificationState;
  product_explanations?: {
    id?: string;
    name?: string;
    reasoning?: string;
    capabilities_enabled?: string[];
    confidence?: number;
  }[];
  explanation?: string;
  lab_operator?: {
    action?: string;
    message?: string;
    hypothesis?: Record<string, unknown>;
    variant_payload?: Record<string, unknown>;
    metrics?: Record<string, unknown>;
    belief_summary?: string | null;
    evidence?: Record<string, unknown> | null;
    experiment_id?: string;
    variant_id?: string | null;
  };
  intentionality_profiles?: {
    product_id?: string;
    capabilities_enabled?: string[];
    goals_served?: string[];
    prerequisites?: string[];
    outcomes_expected?: string[];
    context_fit?: Record<string, number>;
  }[];
};

export type SessionSummary = {
  id: string;
  client_id?: string;
  created_at?: string;
  preview?: string;
  last_turn_at?: string;
};

export type SessionListResponse = {
  sessions: SessionSummary[];
};

export type ResearchRefreshResponse = {
  query?: string;
  goals?: string[];
  research_results: Product[];
  updated_at?: string;
};

export type QueryBattery = {
  id: string;
  client_id: string;
  brand_id?: string | null;
  product_id: string;
  name: string;
  purpose?: string | null;
  generation_mode?: string | null;
  status?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type QueryBatteryQuery = {
  id: string;
  battery_id: string;
  query_text: string;
  query_type?: string | null;
  intent_archetype?: string | null;
  constraints?: Record<string, unknown>;
  weight?: number;
  enabled?: boolean;
  created_at?: string;
};

export type QueryBatteryCandidate = {
  query_text: string;
  query_type?: string | null;
  intent_archetype?: string | null;
  constraints?: Record<string, unknown> | null;
  weight?: number | null;
};

export type AudienceSegment = {
  id: string;
  label: string;
  description?: string | null;
  active: boolean;
  confidence?: number | null;
  support?: number | null;
  support_ratio?: number | null;
  signals?: string[];
  sample_queries?: string[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type QueryBatteryListResponse = {
  batteries: QueryBattery[];
};

export type QueryBatteryQueryListResponse = {
  queries: QueryBatteryQuery[];
  candidates?: QueryBatteryCandidate[];
  report?: {
    accepted_count: number;
    rejected_count: number;
    generated_count?: number;
    generated_preview?: { query_text: string; query_type?: string | null }[];
    required_category?: string | null;
    category_confidence?: number | null;
    category_candidates?: { category: string; score: number }[];
    clarification_required?: boolean;
    clarification_prompt?: string | null;
    regeneration_count?: number;
    acceptance_rate?: number;
    rejected?: { query_text: string; reason: string }[];
    audience_segments_generated?: number;
    audience_segment_labels?: string[];
    audience_segments_source?: "behavioral" | "canonical_fallback";
    audience_segments_fallback_reason?: string | null;
  };
};

export type AudienceSegmentListResponse = {
  segments: AudienceSegment[];
};

export type QueryBatteryMetrics = {
  total_queries: number;
  enabled_queries: number;
  unique_queries: number;
  redundancy_rate: number;
  avg_weight?: number | null;
  avg_words?: number | null;
  enabled_ratio?: number;
  type_diversity?: number;
  archetype_diversity?: number;
  quality_score?: number;
  quality_issues?: string[];
  type_breakdown: Record<string, number>;
  archetype_breakdown: Record<string, number>;
};

export type QueryBatteryMetricsResponse = {
  metrics: QueryBatteryMetrics;
};

export type QueryBatteryEvalSummary = {
  battery_id: string;
  generation_events: number;
  acceptance_rate: number;
  regeneration_rate: number;
  clarification_rate: number;
  downstream_avg_win_rate_robust?: number | null;
  validation_accuracy: number;
  verified_runs: number;
  evidence_strength_breakdown: Record<string, number>;
};

export type QueryBatteryEvalSummaryResponse = {
  summary: QueryBatteryEvalSummary;
};

export type QueryBatteryOntologyUpdatesResponse = {
  updates: {
    battery_id: string;
    rejected_sample_count: number;
    typo_updates: { token: string; suggested: string; count: number }[];
    synonym_updates: { token: string; suggested: string; count: number }[];
    recommended_review_cadence: string;
  };
};

export type Experiment = {
  id: string;
  client_id: string;
  brand_id?: string | null;
  product_id: string;
  battery_id?: string | null;
  name: string;
  hypothesis?: Record<string, unknown>;
  competitor_policy?: Record<string, unknown>;
  status?: string | null;
  schedule_enabled?: boolean;
  schedule_interval_minutes?: number | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type ExperimentVariant = {
  id: string;
  experiment_id: string;
  label: string;
  type: string;
  payload?: Record<string, unknown>;
  created_at?: string;
};

export type ExperimentRun = {
  id: string;
  experiment_id: string;
  variant_id: string;
  query_id: string;
  simulation_run_id?: string | null;
  created_at?: string;
};

export type ExperimentMetric = {
  id: string;
  experiment_id: string;
  variant_id?: string | null;
  metrics?: Record<string, unknown>;
  created_at?: string;
};

export type BrandBelief = {
  id: string;
  client_id: string;
  brand_id: string;
  product_id?: string | null;
  hypothesis: Record<string, unknown>;
  evidence: Record<string, unknown>;
  recommendation?: string | null;
  confidence?: number | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ExperimentListResponse = {
  experiments: Experiment[];
};

export type ExperimentVariantListResponse = {
  variants: ExperimentVariant[];
};

export type ExperimentRunListResponse = {
  runs: ExperimentRun[];
};

export type ExperimentMetricListResponse = {
  metrics: ExperimentMetric[];
};

export type BrandBeliefListResponse = {
  beliefs: BrandBelief[];
};

export type BrandBeliefResponse = {
  belief: BrandBelief | null;
};

export type NextTestRecommendation = {
  experiment_id: string;
  action: "run_variant" | "create_variant" | "none";
  reason: string;
  variant_id?: string | null;
  confidence?: number | null;
  suggested_label?: string | null;
  suggested_type?: string | null;
  suggested_payload?: Record<string, unknown> | null;
  statistical_analysis?: Record<string, unknown> | null;
  ml_prediction?: {
    hypothesis_type: string;
    predicted_lift: number;
    confidence: number;
    rationale: string;
    similar_experiments?: string[];
  } | null;
  exploration_score?: number | null;
  exploitation_score?: number | null;
};

export type NextTestRecommendationResponse = {
  recommendation: NextTestRecommendation;
};

export type ExperimentRecommendation = {
  id: string;
  experiment_id: string;
  recommendation: NextTestRecommendation;
  created_at?: string;
};

export type ExperimentRecommendationListResponse = {
  recommendations: ExperimentRecommendation[];
};

export type ExperimentRunResponse = {
  experiment_id: string;
  variant_id: string;
  runs: {
    query_id: string;
    query_text?: string;
    run_id?: string;
    winner_id?: string | null;
    winner_id_keyword?: string | null;
    score?: number | null;
    score_keyword?: number | null;
    protocol_readiness_score?: number | null;
    judge_results?: { provider: string; winner_id?: string | null; raw?: string }[];
    judge_consensus_winner?: string | null;
  }[];
  metrics: Record<string, unknown>;
};

export type LoopGeneratedVariantCandidate = {
  label: string;
  description: string;
  rationale: string;
  payload: Record<string, unknown>;
  confidence: number;
};

export type LoopGeneratedVariantResponse = {
  experiment_id: string;
  product_id?: string | null;
  generation_mode?: "loop_evidence" | "cold_start";
  generation_strategy?: "bottom_up" | "top_down" | "both";
  summary: Record<string, unknown>;
  evidence: Record<string, unknown>;
  candidates: LoopGeneratedVariantCandidate[];
  used_fallback?: boolean;
  requested_by?: string | null;
};

export type ExperimentValidation = {
  id: string;
  experiment_id: string;
  variant_id?: string | null;
  client_id: string;
  brand_id?: string | null;
  product_id?: string | null;
  platform?: string | null;
  query_text?: string | null;
  observed_products?: string[];
  observed_winner_variant_id?: string | null;
  observed_position?: number | null;
  notes?: string | null;
  is_correct?: boolean | null;
  created_at?: string | null;
};

export type ValidationSummary = {
  total_logged: number;
  observed_signals_logged?: number;
  verified_runs: number;
  observed_runs_verified?: number;
  correct_runs: number;
  observed_correct_runs?: number;
  accuracy: number;
  observed_accuracy?: number;
  unlock_ready: boolean;
  observed_unlock_ready?: boolean;
  progress: number;
  observed_progress?: number;
  accuracy_target: number;
  target_accuracy?: number;
};

export type ExperimentValidationResponse = {
  validation: ExperimentValidation;
  summary: ValidationSummary;
};

export type ExperimentValidationSummaryResponse = {
  summary: ValidationSummary;
};

export type BrandPredictionAccuracyResponse = {
  summary: ValidationSummary;
};

export type ValidationJob = {
  id: string;
  client_id: string;
  brand_id?: string | null;
  product_id?: string | null;
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
  status: string;
  integration_type?: string | null;
  provider_run_id?: string | null;
  callback_verified?: boolean | null;
  input_payload?: Record<string, unknown>;
  requested_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  external_instructions?: string | null;
  external_payload_template?: Record<string, unknown> | null;
};

export type ValidationResult = {
  id: string;
  job_id: string;
  provider: string;
  model?: string | null;
  structured_result?: Record<string, unknown>;
  raw_response?: string | null;
  score?: number | null;
  winner_id?: string | null;
  evidence_strength?: string | null;
  latency_ms?: number | null;
  cost_usd?: number | null;
  source?: string | null;
  callback_verified?: boolean | null;
  created_at?: string | null;
};

export type ValidationJobResponse = {
  job: ValidationJob;
  result?: ValidationResult | null;
};

export type ValidationProviderRunResponse = {
  job: ValidationJob;
  provider_run_id?: string | null;
  launch_url?: string | null;
  setup_url?: string | null;
  setup_required?: boolean | null;
  instructions?: string | null;
  callback_url?: string | null;
  callback_token?: string | null;
  status?: string | null;
};

export type ValidationJobListResponse = {
  jobs: ValidationJob[];
};

export type CopyRevision = {
  id: string;
  client_id: string;
  brand_id?: string | null;
  product_id: string;
  source_type: string;
  source_id?: string | null;
  source_variant_id?: string | null;
  base_description: string;
  candidate_description: string;
  status: string;
  notes?: string | null;
  metadata?: Record<string, unknown>;
  created_by?: string | null;
  approved_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CopyRevisionListResponse = {
  revisions: CopyRevision[];
};

export type CopyRevisionResponse = {
  revision: CopyRevision;
};

export type HealthLLMResponse = {
  providers: Record<
    string,
    { configured: boolean; error?: string | null }
  >;
};

export type LLMProviderSummary = {
  configured: boolean;
  chat_configured?: boolean;
  validation_configured?: boolean;
  model?: string | null;
  validation_model?: string | null;
  is_active?: boolean;
};

export type LLMConfigSummaryResponse = {
  can_manage: boolean;
  active_provider?: string | null;
  providers: Record<string, LLMProviderSummary>;
};

export type AdminLLMConfig = {
  provider: string;
  configured: boolean;
  model?: string | null;
  validation_model?: string | null;
  is_active?: boolean;
  updated_at?: string | null;
};

export type AdminLLMConfigResponse = {
  active_provider?: string | null;
  providers: Record<string, LLMProviderSummary>;
  configs: AdminLLMConfig[];
};

export type LoopMaintenanceRunResponse = {
  lookback_days: number;
  min_confidence: number;
  results: Array<{
    client_id: string;
    calibration_profiles_updated: number;
    memory_artifacts_distilled: number;
  }>;
  history?: LoopMaintenanceRunHistoryItem[];
};

export type LoopMaintenanceRunHistoryItem = {
  id: string;
  client_id: string;
  lookback_days: number;
  min_confidence: number;
  calibration_profiles_updated: number;
  memory_artifacts_distilled: number;
  triggered_by?: string | null;
  created_at?: string | null;
};

export type LoopMaintenanceRunHistoryResponse = {
  runs: LoopMaintenanceRunHistoryItem[];
};

export type AnalyticsEvent = {
  id: string;
  client_id: string;
  brand_id?: string | null;
  product_id?: string | null;
  variant_id?: string | null;
  experiment_id?: string | null;
  event_type: string;
  source?: string | null;
  event_timestamp?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
};

export type AnalyticsEventResponse = {
  event: AnalyticsEvent;
};
